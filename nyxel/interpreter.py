"""nyxel.interpreter — tree-walk interpreter."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .nyx_ast import (
    Node,
    LetStmt, AssignStmt, IfStmt, RepeatStmt, RepeatRangeStmt,
    ForStmt, WhileStmt,
    TryStmt, DefStmt, ReturnStmt, BreakStmt, ContinueStmt, PassStmt,
    ExprStmt, PyBlockStmt, BringStmt, BringFromStmt, StructStmt, AddToStmt,
    WindowStmt,
    NumExpr, StrExpr, BoolExpr, NoneExpr,
    ListExpr, DictExpr, VarExpr,
    BinOpExpr, UnaryExpr, CallExpr, IndexExpr, AttrExpr, PyBlockExpr,
    WhereExpr, WidgetExpr,
)
from .errors import (NyxError, _Return, _Break, _Continue,
                     suggest_attr, name_error_hint,
                     type_error_add_hint, index_error_hint)
from .runtime import (
    Environment, Param, NyxFunction, NyxObject, NyxStruct, NyxException,
    _wrap, _wrap_copy, _unwrap,
)
from .builtins import setup_builtins, _str as nyx_str


class _ModuleMeta:
    __slots__ = ("path", "mtime", "namespace")
    def __init__(self, path: Path, mtime: float, namespace: "NyxObject"):
        self.path      = path
        self.mtime     = mtime
        self.namespace = namespace


class ModuleLoader:
    """
    Finds, executes, and caches .nx module files.

    Each module is executed at most once per loader lifetime; re-executed on
    file change.  Circular imports are detected immediately.  Module execution
    runs in a fully isolated Environment.

    Search order:  ./  →  ./modules/  →  ./lib/
    """

    SEARCH_DIRS = [".", "modules", "lib"]

    def __init__(self):
        self._meta   : Dict[str, _ModuleMeta] = {}
        self._loading: Set[str]               = set()

    def load(self, name: str, interpreter: "Interpreter") -> "NyxObject":
        path = self._find(name)
        if path is None:
            raise NyxError("ImportError", f"Module '{name}' not found",
                           hint=f"Create '{name}.nx' in ./, modules/, or lib/")

        current_mtime = path.stat().st_mtime
        if name in self._meta:
            meta = self._meta[name]
            if meta.mtime == current_mtime:
                return meta.namespace
            del self._meta[name]

        if name in self._loading:
            raise NyxError("ImportError",
                           f"Circular import: '{name}' is already being loaded",
                           hint="Modules cannot bring themselves (directly or indirectly)")

        self._loading.add(name)
        try:
            namespace = self._execute(path, interpreter)
            self._meta[name] = _ModuleMeta(path, current_mtime, namespace)
            return namespace
        except NyxError as e:
            raise NyxError(e.kind, f"In module '{name}': {e.msg}",
                           e.line, e.col, e.raw, e.hint) from None
        finally:
            self._loading.discard(name)

    def is_loaded(self, name: str) -> bool:
        return name in self._meta

    def loaded_modules(self) -> list:
        return list(self._meta.keys())

    def _execute(self, path: Path, parent_interp: "Interpreter") -> "NyxObject":
        source = path.read_text(encoding="utf-8")
        from .lexer  import lex
        from .parser import Parser
        tokens = lex(source, str(path))
        stmts  = Parser(tokens).parse()
        mod_interp = Interpreter(_loader=self)
        builtin_names = set(mod_interp.globals._v.keys())
        mod_interp.run(stmts)
        exports = {k: v for k, v in mod_interp.globals._v.items()
                   if k not in builtin_names}
        return NyxObject(exports)

    def _find(self, name: str) -> Optional[Path]:
        for d in self.SEARCH_DIRS:
            p = Path(d) / f"{name}.nx"
            if p.exists():
                return p
        return None


class Interpreter:

    def __init__(self, script_args: List[str] = None, _loader: ModuleLoader = None):
        self.globals      = Environment()
        self._loader      = _loader or ModuleLoader()
        self._gui_window  = None   # set while inside a create window block
        setup_builtins(self.globals, script_args or [], interpreter=self)

    def run(self, stmts: List[Node], env: Optional[Environment] = None) -> None:
        if env is None:
            env = self.globals
        for stmt in stmts:
            self._exec(stmt, env)

    def run_repl(self, stmts: List[Node]) -> Optional[Any]:
        env = self.globals
        if not stmts:
            return None
        for stmt in stmts[:-1]:
            self._exec(stmt, env)
        last = stmts[-1]
        if type(last) is ExprStmt:
            return self._eval(last.expr, env)
        self._exec(last, env)
        return None

    # ── statement dispatch ────────────────────────────────────────────────────

    def _exec(self, node: Node, env: Environment) -> None:
        t = type(node)

        if t is ExprStmt:
            self._eval(node.expr, env)
            return

        if t is LetStmt:
            env.define(node.name, self._eval(node.expr, env))
            return

        if t is AssignStmt:
            val    = self._eval(node.expr, env)
            target = node.target
            if target[0] == "var":
                env.set(target[1], val)
            elif target[0] == "index":
                obj = self._eval(target[1], env)
                idx = self._eval(target[2], env)
                try:
                    obj[idx] = val
                except (TypeError, KeyError, IndexError):
                    raise NyxError("IndexError", f"Can't set position {idx}",
                                   hint="Check the index is within the list's length")
            elif target[0] == "attr":
                obj = self._eval(target[1], env)
                try:
                    setattr(obj, target[2], val)
                except AttributeError:
                    raise NyxError("AttributeError",
                                   f"Can't set '{target[2]}' on this object",
                                   hint="Check the field name is correct")
            return

        if t is IfStmt:
            if self._eval(node.cond, env):
                self.run(node.body, Environment(env))
            else:
                for ec, eb in node.elifs:
                    if self._eval(ec, env):
                        self.run(eb, Environment(env)); return
                if node.else_body:
                    self.run(node.else_body, Environment(env))
            return

        if t is ForStmt:
            seq  = self._eval(node.iterable, env)
            lenv = Environment(env)
            for item in seq:
                lenv._v.clear()
                lenv._v[node.var] = item
                try:
                    self.run(node.body, lenv)
                except _Break:    break
                except _Continue: continue
            return

        if t is WhileStmt:
            while self._eval(node.cond, env):
                try:
                    self.run(node.body, Environment(env))
                except _Break:    break
                except _Continue: continue
            return

        if t is RepeatStmt:
            count = self._eval(node.count, env)
            if not isinstance(count, (int, float)):
                raise NyxError("TypeError",
                               f"repeat expects a number, got {type(count).__name__}",
                               hint="Write:  repeat 5:  or  repeat n:")
            n    = int(count)
            lenv = Environment(env)
            for i in range(n):
                lenv._v.clear()
                if node.as_var:
                    lenv._v[node.as_var] = i
                try:
                    self.run(node.body, lenv)
                except _Break:    break
                except _Continue: continue
            return

        if t is RepeatRangeStmt:
            start = self._eval(node.start, env)
            end   = self._eval(node.end,   env)
            if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
                raise NyxError("TypeError",
                               "repeat range start and end must be numbers",
                               hint="Write:  repeat i from 1 to 5:")
            lenv = Environment(env)
            for i in range(int(start), int(end) + 1):
                lenv._v.clear()
                lenv._v[node.var] = i
                try:
                    self.run(node.body, lenv)
                except _Break:    break
                except _Continue: continue
            return

        if t is TryStmt:
            self._exec_try(node, env); return

        if t is DefStmt:
            params = [Param(name=p, default=d) for p, d in node.params]
            env.define(node.name, NyxFunction(node.name, params, node.body, env))
            return

        if t is ReturnStmt:
            raise _Return(self._eval(node.expr, env))

        if t is BreakStmt:    raise _Break()
        if t is ContinueStmt: raise _Continue()
        if t is PassStmt:     return

        if t is PyBlockStmt:
            self._pyblock(node.code, env, capture=False); return

        if t is AddToStmt:
            lst = env.get(node.list_name)
            if not isinstance(lst, list):
                raise NyxError("TypeError", f"'{node.list_name}' is not a list",
                               hint=f"Make sure '{node.list_name}' was created as a list:  "
                                    f"let {node.list_name} = []")
            lst.append(self._eval(node.value_expr, env))
            return

        if t is StructStmt:
            defaults = {}
            for fname, default_expr in node.fields:
                if default_expr is not None:
                    defaults[fname] = self._eval(default_expr, env)
            field_names = [f for f, _ in node.fields]
            env.define(node.name, NyxStruct(node.name, field_names, defaults))
            return

        if t is BringStmt:
            ns = self._loader.load(node.module_name, self)
            env.define(node.alias, ns); return

        if t is BringFromStmt:
            ns        = self._loader.load(node.module_name, self)
            available = list(ns._raw().keys())
            for orig, alias in node.names:
                try:
                    val = ns.__getattr__(orig)
                except AttributeError:
                    raise NyxError("ImportError",
                                   f"'{node.module_name}' has no name '{orig}'",
                                   hint=suggest_attr(orig, available))
                env.define(alias, val)
            return

        if t is WindowStmt:
            self._exec_window(node, env); return

        raise NyxError("InternalError", f"Unknown statement node: {type(node).__name__}")

    def _exec_window(self, node: WindowStmt, env: Environment) -> None:
        from .gui import NyxWindow
        title  = self._eval(node.title,  env)
        width  = int(self._eval(node.width,  env))
        height = int(self._eval(node.height, env))
        window = NyxWindow(title, width, height)
        prev   = self._gui_window
        self._gui_window = window
        try:
            # Run in the SAME env so widget variables (counter_label, etc.)
            # land in the same scope that the callbacks were closed over.
            self.run(node.body, env)
        finally:
            self._gui_window = prev
        try:
            window.run()
        except KeyboardInterrupt:
            pass

    def _exec_try(self, node, env: Environment) -> None:
        caught_signal = None
        try:
            self.run(node.body, Environment(env))
        except (_Return, _Break, _Continue) as sig:
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
    # Hot nodes are ordered first to minimise failed branch checks.

    def _eval(self, node: Node, env: Environment) -> Any:
        t = type(node)

        if t is NumExpr:  return node.v
        if t is VarExpr:  return env.get(node.name)
        if t is StrExpr:  return node.v
        if t is BoolExpr: return node.v

        if t is BinOpExpr:
            op = node.op
            if op == "and":
                return self._eval(node.l, env) and self._eval(node.r, env)
            if op == "or":
                return self._eval(node.l, env) or self._eval(node.r, env)
            l = self._eval(node.l, env)
            r = self._eval(node.r, env)
            try:
                if op == "+":
                    if isinstance(l, str) or isinstance(r, str):
                        return nyx_str(l) + nyx_str(r)
                    return l + r
                if op == "-":      return l - r
                if op == "*":      return l * r
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
                if op == "%":      return l % r
                if op == "**":     return l ** r
                if op == "==":     return l == r
                if op == "!=":     return l != r
                if op == "<":      return l < r
                if op == ">":      return l > r
                if op == "<=":     return l <= r
                if op == ">=":     return l >= r
                if op == "in":     return l in r
                if op == "not in": return l not in r
            except NyxError: raise
            except TypeError:
                if op == "+":
                    raise NyxError("TypeError",
                                   f"Can't add {_type_name(l)} and {_type_name(r)} together",
                                   hint=type_error_add_hint(_type_name(l), _type_name(r)))
                raise NyxError("TypeError",
                               f"'{op}' doesn't work on {_type_name(l)} and {_type_name(r)}",
                               hint=f"Make sure both values are numbers before using '{op}'")
            except Exception as e:
                raise NyxError("RuntimeError", f"Operator '{op}' failed: {e}")

        if t is CallExpr:
            fn   = self._eval(node.func, env)
            args = [self._eval(a, env) for a in node.args]
            return self._call(fn, args)

        if t is AttrExpr:
            obj  = self._eval(node.obj, env)
            attr = node.attr

            if attr == "length":
                try:
                    return len(obj)
                except TypeError:
                    raise NyxError("TypeError",
                                   f".length doesn't work on {_type_name(obj)}",
                                   hint=".length works on text, lists, and dicts")

            if attr == "is_empty":
                def _is_empty_fn():
                    try:    return len(obj) == 0
                    except TypeError:
                        raise NyxError("TypeError",
                                       f".is_empty() doesn't work on {_type_name(obj)}")
                return _is_empty_fn

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
                raise NyxError("AttributeError", f"Text has no property '{attr}'",
                               hint=f"Available text properties: {', '.join(STRING_METHODS.keys())}")

            if isinstance(obj, list):
                LIST_METHODS = {
                    "sorted":   lambda: sorted(obj),
                    "reversed": lambda: list(reversed(obj)),
                    "first":    lambda: obj[0] if obj else None,
                    "last":     lambda: obj[-1] if obj else None,
                    "copy":     lambda: list(obj),
                }
                if attr in LIST_METHODS:
                    return LIST_METHODS[attr]

            if isinstance(obj, NyxObject):
                d = obj._raw()
                if attr in d:
                    return _wrap(d[attr])
                try:
                    return object.__getattribute__(obj, attr)
                except AttributeError:
                    pass
                raise NyxError("AttributeError", f"'{attr}' doesn't exist on this object",
                               hint=suggest_attr(attr, list(d.keys())))

            # NyxWidget and other Python objects — forward via getattr
            try:
                return _wrap(getattr(obj, attr))
            except AttributeError:
                raise NyxError("AttributeError", f"Object has no property '{attr}'")

        if t is NoneExpr: return None

        if t is ListExpr:
            return [self._eval(item, env) for item in node.items]

        if t is IndexExpr:
            obj = self._eval(node.obj, env)
            idx = self._eval(node.idx, env)
            try:
                raw = obj[idx]
                return _wrap(raw) if not isinstance(raw, (NyxObject, list)) else raw
            except (IndexError, KeyError):
                clen = len(obj) if hasattr(obj, "__len__") else 0
                raise NyxError("IndexError",
                               f"Index '{idx}' doesn't exist in this list",
                               hint=index_error_hint(idx, clen))
            except TypeError:
                raise NyxError("TypeError",
                               f"{_type_name(obj)} can't be accessed with [ ]",
                               hint="Only lists and dicts support index access")

        if t is WhereExpr:
            return self._eval_where(node, env)

        if t is UnaryExpr:
            v = self._eval(node.e, env)
            if node.op == "-":   return -v
            if node.op == "not": return not v

        if t is DictExpr:
            return NyxObject(
                {self._eval(k, env): self._eval(v, env) for k, v in node.pairs}
            )

        if t is PyBlockExpr:
            return self._pyblock(node.code, env, capture=True)

        if t is WidgetExpr:
            return self._eval_widget(node, env)

        raise NyxError("InternalError", f"Unknown expression node: {type(node).__name__}")

    def _eval_where(self, node: WhereExpr, env: Environment) -> list:
        collection = self._eval(node.collection, env)
        if not isinstance(collection, list):
            raise NyxError("TypeError",
                           f"'where' requires a list, got {_type_name(collection)}",
                           hint="Write:  let results = my_list where condition")
        result   = []
        item_env = Environment(env)
        for item in collection:
            item_env._v.clear()
            item_env._v["item"] = item
            item_env._v["each"] = item
            if isinstance(item, NyxObject):
                for k, v in item._raw().items():
                    item_env._v[str(k)] = _wrap(v)
            try:
                item_env._v["length"] = len(item)
            except TypeError:
                pass
            try:
                passes = self._eval(node.condition, item_env)
            except NyxError as e:
                if e.kind == "NameError":
                    raise NyxError("NameError", e.msg, e.line, e.col, e.raw,
                                   f"Inside 'where', use 'item' to refer to the current value.\n"
                                   f"  Example:  my_list where item.length > 0\n"
                                   f"  Example:  numbers where is_even(item)\n"
                                   f"  Example:  users where item.age >= 18")
                raise
            if passes:
                result.append(item)
        return result

    def _eval_widget(self, node: WidgetExpr, env: Environment) -> Any:
        if self._gui_window is None:
            raise NyxError("GUIError",
                           f"'{node.kind}' must be used inside a create window block",
                           hint="Wrap your widgets in:  create window(\"Title\") size(800, 600):")
        from .gui import NyxWidgetBuilder
        args    = [self._eval(a, env) for a in node.args]
        builder = NyxWidgetBuilder(self._gui_window, node.kind, args, self)
        for mod_name, mod_args in node.modifiers:
            evaled = [self._eval(a, env) for a in mod_args]
            builder.apply_modifier(mod_name, evaled)
        return builder.build()

    # ── function call ─────────────────────────────────────────────────────────
    # NyxFunction is the hot path — check it first.

    def _call(self, fn: Any, args: List[Any]) -> Any:
        if isinstance(fn, NyxFunction):
            min_args = fn.required_count
            max_args = len(fn.params)
            if len(args) < min_args or len(args) > max_args:
                if min_args == max_args:
                    msg = f"{fn.name}() expects {max_args} argument(s), got {len(args)}"
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

        if isinstance(fn, NyxStruct):
            try:
                return fn(*args)
            except NyxError: raise
            except Exception as e:
                raise NyxError("TypeError", f"{fn.name}() couldn't be created: {e}",
                               hint=f"Check the values you passed to {fn.name}()")

        if callable(fn):
            try:
                result = fn(*args)
                return _wrap(result) if isinstance(result, dict) else result
            except NyxError: raise
            except SystemExit: raise
            except Exception as e:
                name = getattr(fn, "__name__", repr(fn))
                raise NyxError("RuntimeError", f"{name}() failed: {e}",
                               hint=f"Check the values you passed to {name}()")

        raise NyxError("TypeError", f"'{fn}' is not callable",
                       hint="Only functions and built-ins can be called with ()")

    # ── python: … end  blocks ─────────────────────────────────────────────────

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


def _type_name(v: Any) -> str:
    if isinstance(v, bool):          return "bool"
    if isinstance(v, (int, float)):  return "number"
    if isinstance(v, str):           return "text"
    if isinstance(v, list):          return "list"
    if isinstance(v, NyxObject):     return "dict"
    return type(v).__name__