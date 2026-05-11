"""
nyxel.interpreter
─────────────────
Tree-walk interpreter.  Executes the AST produced by the parser.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .ast import (
    Node,
    LetStmt, AssignStmt, IfStmt, RepeatStmt, RepeatRangeStmt,
    ForStmt, WhileStmt,
    TryStmt, DefStmt, ReturnStmt, BreakStmt, ContinueStmt, PassStmt,
    ExprStmt, PyBlockStmt, BringStmt, BringFromStmt, StructStmt, AddToStmt,
    NumExpr, StrExpr, BoolExpr, NoneExpr,
    ListExpr, DictExpr, VarExpr,
    BinOpExpr, UnaryExpr, CallExpr, IndexExpr, AttrExpr, PyBlockExpr,
    WhereExpr,
)
from .errors import (NyxError, _Return, _Break, _Continue,
                     suggest_attr, name_error_hint,
                     type_error_add_hint, index_error_hint)
from .runtime import (
    Environment, Param, NyxFunction, NyxObject, NyxStruct, NyxException,
    _wrap, _wrap_copy, _unwrap,
)
from .builtins import setup_builtins, _str as nyx_str


# ── Module loader ─────────────────────────────────────────────────────────────

class _ModuleMeta:
    """Metadata stored alongside a cached module."""
    __slots__ = ("path", "mtime", "namespace")
    def __init__(self, path: Path, mtime: float, namespace: "NyxObject"):
        self.path      = path
        self.mtime     = mtime
        self.namespace = namespace


class ModuleLoader:
    """
    Finds, executes, and caches  .nx  module files.

    Guarantees
    ──────────
    • Each module is executed at most once per loader lifetime.
    • If the source file changes on disk, the cache is invalidated
      and the module is re-executed on the next bring.
    • Circular imports are detected and reported immediately.
    • Module execution runs in a fully isolated Environment —
      the caller's globals never leak into the module.

    Search order:  ./  →  ./modules/  →  ./lib/
    """

    SEARCH_DIRS = [".", "modules", "lib"]

    def __init__(self):
        self._meta   : Dict[str, _ModuleMeta] = {}   # name → meta
        self._loading: Set[str]               = set() # cycle detection

    # ── public API ────────────────────────────────────────────────────────────

    def load(self, name: str, interpreter: "Interpreter") -> "NyxObject":
        path = self._find(name)
        if path is None:
            raise NyxError(
                "ImportError", f"Module '{name}' not found",
                hint=f"Create '{name}.nx' in ./, modules/, or lib/",
            )

        current_mtime = path.stat().st_mtime

        # Return cached version if file hasn't changed
        if name in self._meta:
            meta = self._meta[name]
            if meta.mtime == current_mtime:
                return meta.namespace
            # File changed — invalidate
            del self._meta[name]

        # Cycle detection
        if name in self._loading:
            raise NyxError(
                "ImportError", f"Circular import: '{name}' is already being loaded",
                hint="Modules cannot bring themselves (directly or indirectly)",
            )

        self._loading.add(name)
        try:
            namespace = self._execute(path, interpreter)
            self._meta[name] = _ModuleMeta(path, current_mtime, namespace)
            return namespace
        except NyxError as e:
            # Re-raise with module context added to the hint
            raise NyxError(
                e.kind,
                f"In module '{name}': {e.msg}",
                e.line, e.col, e.raw,
                e.hint,
            ) from None
        finally:
            self._loading.discard(name)

    def is_loaded(self, name: str) -> bool:
        return name in self._meta

    def loaded_modules(self) -> list:
        return list(self._meta.keys())

    # ── internals ─────────────────────────────────────────────────────────────

    def _execute(self, path: Path, parent_interp: "Interpreter") -> "NyxObject":
        """
        Run the module source code in an isolated environment.

        This way, we use our own Interpreter (which shares the ModuleLoader,
        so that even sub-modules will be cached), however with a completely
        fresh global scope – nothing is inherited from the caller's side.

        All symbols declared in the module become exports,
        yet there are no built-ins such as get, len, ... exported back.
        """
        source = path.read_text(encoding="utf-8")

        from .lexer  import lex
        from .parser import Parser

        tokens = lex(source, str(path))
        stmts  = Parser(tokens).parse()

        # Fresh interpreter, same loader (so cached modules are shared)
        mod_interp = Interpreter(_loader=self)

        # Snapshot of built-in names so we can exclude them from exports
        builtin_names = set(mod_interp.globals._v.keys())

        mod_interp.run(stmts)

        # Export only user-defined names
        exports = {
            k: v
            for k, v in mod_interp.globals._v.items()
            if k not in builtin_names
        }
        return NyxObject(exports)

    def _find(self, name: str) -> Optional[Path]:
        for d in self.SEARCH_DIRS:
            p = Path(d) / f"{name}.nx"
            if p.exists():
                return p
        return None


# ── Interpreter ───────────────────────────────────────────────────────────────

class Interpreter:

    def __init__(self, script_args: List[str] = None,
                 _loader: ModuleLoader = None):
        self.globals = Environment()
        self._loader = _loader or ModuleLoader()
        setup_builtins(self.globals, script_args or [], interpreter=self)

    # ── public ────────────────────────────────────────────────────────────────

    def run(self, stmts: List[Node], env: Optional[Environment] = None) -> None:
        """Execute a list of statement nodes, discarding return values."""
        if env is None:
            env = self.globals
        for stmt in stmts:
            self._exec(stmt, env)

    def run_repl(self, stmts: List[Node]) -> Optional[Any]:
        """
        Execute a list of statements in the REPL context.

        If the last statement is a bare expression (ExprStmt),
        return its value so the REPL can display it.
        All other statements return None.
        """
        env = self.globals
        if not stmts:
            return None

        for stmt in stmts[:-1]:
            self._exec(stmt, env)

        last = stmts[-1]
        if isinstance(last, ExprStmt):
            return self._eval(last.expr, env)

        self._exec(last, env)
        return None

    # ── statement dispatch ────────────────────────────────────────────────────

    def _exec(self, node: Node, env: Environment) -> None:
        nn = type(node).__name__

        if nn == "LetStmt":
            env.define(node.name, self._eval(node.expr, env))

        elif nn == "AssignStmt":
            val    = self._eval(node.expr, env)
            target = node.target
            if target[0] == "var":
                env.set(target[1], val)
            elif target[0] == "index":
                obj = self._eval(target[1], env)
                idx = self._eval(target[2], env)
                try:
                    obj[idx] = val
                except (TypeError, KeyError, IndexError) as e:
                    raise NyxError("IndexError",
                                   f"Can't set position {idx}",
                                   hint="Check the index is within the list's length")
            elif target[0] == "attr":
                obj = self._eval(target[1], env)
                try:
                    setattr(obj, target[2], val)
                except AttributeError as e:
                    raise NyxError("AttributeError",
                                   f"Can't set '{target[2]}' on this object",
                                   hint="Check the field name is correct")

        elif nn == "ExprStmt":
            self._eval(node.expr, env)

        elif nn == "PyBlockStmt":
            self._pyblock(node.code, env, capture=False)

        elif nn == "IfStmt":
            if self._eval(node.cond, env):
                self.run(node.body, Environment(env))
            else:
                for ec, eb in node.elifs:
                    if self._eval(ec, env):
                        self.run(eb, Environment(env)); return
                if node.else_body:
                    self.run(node.else_body, Environment(env))

        elif nn == "RepeatStmt":
            count = self._eval(node.count, env)
            if not isinstance(count, (int, float)):
                raise NyxError("TypeError",
                               f"repeat expects a number, got {type(count).__name__}",
                               hint="Write:  repeat 5:  or  repeat n:")
            n = int(count)
            for i in range(n):
                lenv = Environment(env)
                if node.as_var:
                    lenv.define(node.as_var, i)
                try:
                    self.run(node.body, lenv)
                except _Break:    break
                except _Continue: continue

        elif nn == "RepeatRangeStmt":
            start = self._eval(node.start, env)
            end   = self._eval(node.end,   env)
            if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
                raise NyxError("TypeError",
                               "repeat range start and end must be numbers",
                               hint="Write:  repeat i from 1 to 5:")
            for i in range(int(start), int(end) + 1):
                lenv = Environment(env)
                lenv.define(node.var, i)
                try:
                    self.run(node.body, lenv)
                except _Break:    break
                except _Continue: continue

        elif nn == "ForStmt":
            seq = self._eval(node.iterable, env)
            for item in seq:
                lenv = Environment(env)
                lenv.define(node.var, item)
                try:
                    self.run(node.body, lenv)
                except _Break:    break
                except _Continue: continue

        elif nn == "WhileStmt":
            while self._eval(node.cond, env):
                try:
                    self.run(node.body, Environment(env))
                except _Break:    break
                except _Continue: continue

        elif nn == "TryStmt":
            self._exec_try(node, env)

        elif nn == "DefStmt":
            # Convert raw (name, default_node) tuples from the parser into
            # typed Param namedtuples before storing on NyxFunction.
            params = [
                Param(name=p, default=d)
                for p, d in node.params
            ]
            env.define(node.name, NyxFunction(node.name, params, node.body, env))

        elif nn == "ReturnStmt":
            raise _Return(self._eval(node.expr, env))

        elif nn == "BreakStmt":    raise _Break()
        elif nn == "ContinueStmt": raise _Continue()
        elif nn == "PassStmt":     pass

        elif nn == "BringStmt":
            ns = self._loader.load(node.module_name, self)
            env.define(node.alias, ns)

        elif nn == "BringFromStmt":
            ns = self._loader.load(node.module_name, self)
            available = list(ns._raw().keys())
            for orig, alias in node.names:
                try:
                    val = ns.__getattr__(orig)
                except AttributeError:
                    hint = suggest_attr(orig, available)
                    raise NyxError(
                        "ImportError",
                        f"'{node.module_name}' has no name '{orig}'",
                        hint=hint,
                    )
                env.define(alias, val)

        elif nn == "AddToStmt":
            lst = env.get(node.list_name)
            if not isinstance(lst, list):
                raise NyxError(
                    "TypeError",
                    f"'{node.list_name}' is not a list",
                    hint=f"Make sure '{node.list_name}' was created as a list:  "
                         f"let {node.list_name} = []",
                )
            lst.append(self._eval(node.value_expr, env))

        elif nn == "StructStmt":
            defaults = {}
            for fname, default_expr in node.fields:
                if default_expr is not None:
                    defaults[fname] = self._eval(default_expr, env)
            field_names = [f for f, _ in node.fields]
            env.define(node.name, NyxStruct(node.name, field_names, defaults))

        else:
            raise NyxError("InternalError", f"Unknown statement node: {nn}")

    # ── try / catch / finally ─────────────────────────────────────────────────

    def _exec_try(self, node, env: Environment) -> None:
        caught_signal = None
        try:
            self.run(node.body, Environment(env))
        except (_Return, _Break, _Continue) as sig:
            # Control-flow signals must NOT be swallowed by catch
            caught_signal = sig
        except NyxError as e:
            if node.catch_body:
                cenv = Environment(env)
                if node.catch_var:
                    cenv.define(node.catch_var, NyxException(e.kind, e.msg))
                self.run(node.catch_body, cenv)
        except Exception as e:
            if node.catch_body:
                cenv = Environment(env)
                if node.catch_var:
                    cenv.define(node.catch_var,
                                NyxException(type(e).__name__, str(e)))
                self.run(node.catch_body, cenv)
        finally:
            if node.finally_body:
                self.run(node.finally_body, Environment(env))

        if caught_signal is not None:
            raise caught_signal

    # ── expression evaluation ─────────────────────────────────────────────────

    def _eval(self, node: Node, env: Environment) -> Any:
        nn = type(node).__name__

        if nn == "WhereExpr":
            collection = self._eval(node.collection, env)
            if not isinstance(collection, list):
                raise NyxError(
                    "TypeError",
                    f"'where' requires a list, got {_type_name(collection)}",
                    hint="Write:  let results = my_list where condition",
                )
            result = []
            for item in collection:
                item_env = Environment(env)

                # ── 'item' is the canonical name for the current element ──────
                # This is the ONE thing a beginner needs to know about 'where':
                #   files where not is_empty(item)
                #   names where item.length > 4
                # We also expose 'each' as an alias for the same reason.
                item_env.define("item", item)
                item_env.define("each", item)

                # ── Expose NyxObject fields by name too ───────────────────────
                # So  users where age >= 18  still works (age is a field of user)
                if isinstance(item, NyxObject):
                    for k, v in item._raw().items():
                        item_env.define(str(k), _wrap(v))

                # ── Expose .length for any item type ──────────────────────────
                # So  words where length > 4  works on a list of strings
                try:
                    item_env.define("length", len(item))
                except TypeError:
                    pass

                # ── Evaluate the condition — catch NameErrors with a hint ─────
                try:
                    passes = self._eval(node.condition, item_env)
                except NyxError as e:
                    if e.kind == "NameError":
                        # Re-raise with a teaching hint about 'item'
                        raise NyxError(
                            "NameError",
                            e.msg,
                            e.line, e.col, e.raw,
                            f"Inside 'where', use 'item' to refer to the current value.\n"
                            f"  Example:  my_list where item.length > 0\n"
                            f"  Example:  numbers where is_even(item)\n"
                            f"  Example:  users where item.age >= 18",
                        )
                    raise

                if passes:
                    result.append(item)
            return result

        if nn == "NumExpr":  return node.v
        if nn == "StrExpr":  return node.v
        if nn == "BoolExpr": return node.v
        if nn == "NoneExpr": return None
        if nn == "VarExpr":  return env.get(node.name)

        if nn == "ListExpr":
            return [self._eval(item, env) for item in node.items]

        if nn == "DictExpr":
            return NyxObject(
                {self._eval(k, env): self._eval(v, env) for k, v in node.pairs}
            )

        if nn == "PyBlockExpr":
            return self._pyblock(node.code, env, capture=True)

        if nn == "IndexExpr":
            obj = self._eval(node.obj, env)
            idx = self._eval(node.idx, env)
            try:
                raw = obj[idx]
                return _wrap(raw) if not isinstance(raw, (NyxObject, list)) else raw
            except (IndexError, KeyError):
                clen = len(obj) if hasattr(obj, "__len__") else 0
                hint = index_error_hint(idx, clen)
                raise NyxError("IndexError",
                               f"Index '{idx}' doesn't exist in this list",
                               hint=hint)
            except TypeError:
                raise NyxError("TypeError",
                               f"{_type_name(obj)} can't be accessed with [ ]",
                               hint="Only lists and dicts support index access")
es where item.length > 4
        if nn == "AttrExpr":
            obj  = self._eval(node.obj, env)
            attr = node.attr

            # ── Native dot-access properties ──────────────────────────────
            # These work on strings, lists, and dicts without any import.
            # They are resolved here, before dict-key lookup, so they always
            # win over user-defined fields with the same name.

            if attr == "length":
                try:
                    return len(obj)
                except TypeError:
                    raise NyxError("TypeError",
                                   f".length doesn't work on {_type_name(obj)}",
                                   hint=".length works on text, lists, and dicts")

            if attr == "is_empty":
                # Returns a zero-argument callable so  list.is_empty()  works
                def _is_empty_fn():
                    try:    return len(obj) == 0
                    except TypeError:
                        raise NyxError("TypeError",
                                       f".is_empty() doesn't work on {_type_name(obj)}")
                return _is_empty_fn

            # ── String method forwarding ───────────────────────────────────
            # Lets you write  name.upper()  instead of  upper(name) .
            # Only applies to str values — not dicts or lists.
            if isinstance(obj, str):
                STRING_METHODS = {
                    "upper":       lambda: obj.upper(),
                    "lower":       lambda: obj.lower(),
                    "strip":       lambda: obj.strip(),
                    "split":       lambda sep=None: obj.split(sep) if sep else obj.split(),
                    "replace":     lambda a, b: obj.replace(a, b),
                    "starts_with": lambda p: obj.startswith(p),
                    "ends_with":   lambda s: obj.endswith(s),
                    "contains":    lambda sub: sub in obj,
                    "to_int":      lambda: int(obj),
                    "to_float":    lambda: float(obj),
                    "to_upper":    lambda: obj.upper(),
                    "to_lower":    lambda: obj.lower(),
                }
                if attr in STRING_METHODS:
                    return STRING_METHODS[attr]
                raise NyxError("AttributeError",
                               f"Text has no property '{attr}'",
                               hint=f"Available text properties: {', '.join(STRING_METHODS.keys())}")

            # ── List method forwarding ────────────────────────────────────
            if isinstance(obj, list):
                LIST_METHODS = {
                    "sorted":    lambda: sorted(obj),
                    "reversed":  lambda: list(reversed(obj)),
                    "first":     lambda: obj[0] if obj else None,
                    "last":      lambda: obj[-1] if obj else None,
                    "copy":      lambda: list(obj),
                }
                if attr in LIST_METHODS:
                    return LIST_METHODS[attr]

            # ── NyxObject (dict) access ───────────────────────────────────
            if isinstance(obj, NyxObject):
                # 1. Try dict-key access (user data)
                d = obj._raw()
                if attr in d:
                    return _wrap(d[attr])
                # 2. Fall back to real Python methods (copy, keys, values, …)
                try:
                    return object.__getattribute__(obj, attr)
                except AttributeError:
                    pass
                # 3. Nothing found — give a helpful error with suggestions
                hint = suggest_attr(attr, list(d.keys()))
                raise NyxError("AttributeError",
                               f"'{attr}' doesn't exist on this object",
                               hint=hint)

            try:
                return _wrap(getattr(obj, attr))
            except AttributeError:
                raise NyxError("AttributeError",
                               f"Object has no property '{attr}'")

        if nn == "CallExpr":
            fn   = self._eval(node.func, env)
            args = [self._eval(a, env) for a in node.args]
            return self._call(fn, args)

        if nn == "UnaryExpr":
            v = self._eval(node.e, env)
            if node.op == "-":   return -v
            if node.op == "not": return not v

        if nn == "BinOpExpr":
            if node.op == "and":
                left = self._eval(node.l, env)
                return left and self._eval(node.r, env)
            if node.op == "or":
                left = self._eval(node.l, env)
                return left or self._eval(node.r, env)

            l = self._eval(node.l, env)
            r = self._eval(node.r, env)
            try:
                op = node.op
                if op == "+":
                    if isinstance(l, str) or isinstance(r, str):
                        return nyx_str(l) + nyx_str(r)
                    return l + r
                if op == "-":       return l - r
                if op == "*":       return l * r
                if op == "/":
                    if r == 0:
                        raise NyxError("MathError", "Division by zero",
                                       hint="Make sure the divisor is not zero")
                    return l / r
                if op == "//":
                    if r == 0:
                        raise NyxError("MathError", "Floor division by zero",
                                       hint="Make sure the divisor is not zero")
                    return l // r
                if op == "%":       return l % r
                if op == "**":      return l ** r
                if op == "==":      return l == r
                if op == "!=":      return l != r
                if op == "<":       return l < r
                if op == ">":       return l > r
                if op == "<=":      return l <= r
                if op == ">=":      return l >= r
                if op == "in":      return l in r
                if op == "not in":  return l not in r
            except NyxError: raise
            except TypeError:
                if node.op == "+":
                    raise NyxError("TypeError",
                                   f"Can't add {_type_name(l)} and {_type_name(r)} together",
                                   hint=type_error_add_hint(_type_name(l), _type_name(r)))
                raise NyxError("TypeError",
                               f"'{node.op}' doesn't work on "
                               f"{_type_name(l)} and {_type_name(r)}",
                               hint=f"Make sure both values are numbers before using '{node.op}'")
            except Exception as e:
                raise NyxError("RuntimeError",
                               f"Operator '{node.op}' failed: {e}",
                               hint="Check both values are the right type")

        raise NyxError("InternalError", f"Unknown expression node: {nn}")

    # ── function call ─────────────────────────────────────────────────────────

    def _call(self, fn: Any, args: List[Any]) -> Any:
        if isinstance(fn, NyxStruct):
            try:
                return fn(*args)
            except NyxError:
                raise
            except Exception as e:
                raise NyxError("TypeError",
                               f"{fn.name}() couldn't be created: {e}",
                               hint=f"Check the values you passed to {fn.name}()")

        if callable(fn) and not isinstance(fn, NyxFunction):
            try:
                result = fn(*args)
                return _wrap(result) if isinstance(result, dict) else result
            except NyxError:
                raise
            except SystemExit:
                raise
            except Exception as e:
                name = getattr(fn, "__name__", repr(fn))
                raise NyxError("RuntimeError",
                               f"{name}() failed: {e}",
                               hint=f"Check the values you passed to {name}()")

        if isinstance(fn, NyxFunction):
            min_args = fn.required_count
            max_args = len(fn.params)

            if len(args) < min_args or len(args) > max_args:
                if min_args == max_args:
                    msg = (f"{fn.name}() expects {max_args} argument(s), "
                           f"got {len(args)}")
                else:
                    msg = (f"{fn.name}() expects {min_args}–{max_args} "
                           f"argument(s), got {len(args)}")
                raise NyxError("TypeError", msg)

            fenv = Environment(fn.closure)
            for i, param in enumerate(fn.params):
                if i < len(args):
                    fenv.define(param.name, args[i])
                else:
                    fenv.define(param.name, self._eval(param.default, fn.closure))
            try:
                self.run(fn.body, fenv)
                return None
            except _Return as ret:
                return ret.value

        raise NyxError("TypeError", f"'{fn}' is not callable",
                       hint="Only functions and built-ins can be called with ()")

    # ── python: … end  block ─────────────────────────────────────────────────

    def _pyblock(self, code: str, env: Environment, *, capture: bool) -> Any:
        py_vars = {
            k: _unwrap(v)
            for k, v in env.flat().items()
            if not callable(v) and not isinstance(v, (NyxFunction, NyxStruct))
        }

        fn_src = "def __nyx_block__():\n" + textwrap.indent(
            code if code.strip() else "    pass", "    "
        )

        try:
            globals_dict = {"__builtins__": __builtins__, **py_vars}
            exec(fn_src, globals_dict)      # noqa: S102
            result = globals_dict["__nyx_block__"]()
            return _wrap(result) if capture else None
        except NyxError: raise
        except Exception as e:
            raise NyxError("PythonError",
                           f"Python block raised {type(e).__name__}: {e}",
                           hint="Check your python: … end code for Python errors")


# ── type helpers for better error messages ────────────────────────────────────

def _type_name(v: Any) -> str:
    if isinstance(v, bool):          return "bool"
    if isinstance(v, (int, float)):  return "number"
    if isinstance(v, str):           return "text"
    if isinstance(v, list):          return "list"
    if isinstance(v, NyxObject):     return "dict"
    return type(v).__name__
