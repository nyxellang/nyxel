"""nyxel._run — runtime for transpiled Nyxel code."""

from __future__ import annotations

import json
import math
import os
import random as _random
import subprocess
import sys
import textwrap
import time as _time
import urllib.request
import datetime as _dt
from pathlib import Path
from typing import Any, Dict, List, Optional

from .errors import NyxError, _Return, _Break, _Continue, suggest_attr, index_error_hint, name_error_hint
from .runtime import NyxObject, NyxStruct, NyxException, _wrap, _wrap_copy, _unwrap
from .version import VERSION


# ══════════════════════════════════════════════════════════════════════════════
#  DISPLAY HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _display(v: Any) -> str:
    if v is True:  return "true"
    if v is False: return "false"
    if v is None:  return "none"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _say(*args: Any) -> None:
    print(" ".join(_display(a) for a in args))


def _pretty(data: Any) -> None:
    raw = _unwrap(data)
    try:
        print(json.dumps(raw, indent=2))
    except (TypeError, ValueError):
        print(_display(data))


# ══════════════════════════════════════════════════════════════════════════════
#  BUILTIN TYPE HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _nyx_type(x: Any) -> str:
    if x is None:                   return "none"
    if isinstance(x, bool):         return "bool"
    if isinstance(x, (int, float)): return "number"
    if isinstance(x, str):          return "text"
    if isinstance(x, list):         return "list"
    if isinstance(x, (NyxObject, dict)): return "dict"
    return type(x).__name__


def _nyx_str(x: Any) -> str:
    if x is None:  return "none"
    if x is True:  return "true"
    if x is False: return "false"
    return str(x)


def _nyx_int(x: Any) -> int:
    try:
        return int(x)
    except (ValueError, TypeError):
        raise NyxError("TypeError", f"Can't convert '{x}' to a whole number",
                       hint='Make sure the value is a number or a text like "42"')


def _nyx_float(x: Any) -> float:
    try:
        return float(x)
    except (ValueError, TypeError):
        raise NyxError("TypeError", f"Can't convert '{x}' to a number",
                       hint="Make sure the value looks like a number")


def _nyx_len(x: Any) -> int:
    try:
        return len(x)
    except TypeError:
        raise NyxError("TypeError",
                       f"len() does not work on {_nyx_type(x)} values")


def _nyx_is_empty(obj: Any):
    return lambda: _nyx_len(obj) == 0


def _nyx_list_sorted(obj: list):
    return lambda: sorted(obj)


def _nyx_list_reversed(obj: list):
    return lambda: list(reversed(obj))


def _nyx_list_first(obj: list):
    return lambda: obj[0] if obj else None


def _nyx_list_last(obj: list):
    return lambda: obj[-1] if obj else None


# ══════════════════════════════════════════════════════════════════════════════
#  WHERE — dynamic-scoped filter
# ══════════════════════════════════════════════════════════════════════════════

def __nyx_where__(collection: list, pred_str: str) -> list:
    if not isinstance(collection, list):
        raise NyxError("TypeError",
                       f"'where' requires a list, got {_nyx_type(collection)}",
                       hint="Write:  let results = my_list where condition")
    pred_code = compile(pred_str, "<where>", "eval")
    frame = sys._getframe(1)
    base_scope = {**frame.f_globals, **frame.f_locals}
    result = []
    for item in collection:
        local_scope: dict = {"item": item, "each": item}
        try:
            local_scope["length"] = len(item)
        except TypeError:
            pass
        if isinstance(item, NyxObject):
            for k, v in item._raw().items():
                local_scope[str(k)] = _wrap(v)
        scope = {**base_scope, **local_scope}
        try:
            if eval(pred_code, frame.f_globals, scope):
                result.append(item)
        except NameError as e:
            raise NyxError("NameError", str(e),
                           hint="Inside 'where', use 'item' to refer to the current value.\n"
                                "  Example:  my_list where item.length > 0\n"
                                "  Example:  numbers where is_even(item)\n"
                                "  Example:  users where item.age >= 18")
    return result


# ══════════════════════════════════════════════════════════════════════════════
#  ERROR CONVERSION (for try/catch)
# ══════════════════════════════════════════════════════════════════════════════

def _nyx_catch_convert(e: Exception):
    """Convert a caught Python or NyxError to a (kind, message) pair."""
    if isinstance(e, NyxError):
        return e.kind, e.msg
    if isinstance(e, ZeroDivisionError):
        return "MathError", "Division by zero"
    return e.__class__.__name__, str(e)


# ══════════════════════════════════════════════════════════════════════════════
#  MODULE LOADING (bring)
# ══════════════════════════════════════════════════════════════════════════════

_SEARCH_DIRS = [".", "modules", "lib"]
_loaded_modules: Dict[str, tuple] = {}
_loading: set = set()


def __nyx_bring__(module_name: str) -> NyxObject:
    if module_name == "gui":
        from .gui import make_gui_module
        class _FakeInterp:
            def _eval(self, node, env):
                raise NyxError("InternalError", "GUI module needs interpreter")
            def _call(self, fn, args):
                return fn(*args)
        return make_gui_module(_FakeInterp())

    path = _find_module(module_name)
    if path is None:
        raise NyxError("ImportError", f"Module '{module_name}' not found",
                       hint=f"Create '{module_name}.nx' in ./, modules/, or lib/")

    current_mtime = path.stat().st_mtime
    if module_name in _loaded_modules:
        meta_path, meta_mtime, meta_ns = _loaded_modules[module_name]
        if meta_mtime == current_mtime:
            return meta_ns

    if module_name in _loading:
        raise NyxError("ImportError",
                       f"Circular import: '{module_name}' is already being loaded",
                       hint="Modules cannot bring themselves (directly or indirectly)")

    _loading.add(module_name)
    try:
        from .lexer import lex
        from .parser import Parser
        from .compiler import transpile

        source = path.read_text(encoding="utf-8")
        tokens = lex(source, str(path))
        parser = Parser(tokens)
        stmts = parser.parse()
        py_source = transpile(stmts, str(path))

        mod_g = __nyx_runtime([])
        pre_keys = set(mod_g.keys())
        exec(compile(py_source, str(path), "exec"), mod_g)
        exports = {k: v for k, v in mod_g.items() if k not in pre_keys}

        ns = NyxObject(exports)
        _loaded_modules[module_name] = (path, current_mtime, ns)
        return ns
    except NyxError:
        raise
    except Exception as e:
        raise NyxError("ImportError", f"Failed to load module '{module_name}': {e}",
                       hint="Check that the module file has valid Nyxel syntax")
    finally:
        _loading.discard(module_name)


def __nyx_bring_from__(module_name: str, names: dict) -> None:
    ns = __nyx_bring__(module_name)
    for orig, alias in names.items():
        try:
            val = ns.__getattr__(orig)
        except AttributeError:
            available = list(ns._raw().keys())
            raise NyxError("ImportError",
                           f"'{module_name}' has no name '{orig}'",
                           hint=suggest_attr(orig, available))
        # Assign to caller's frame
        f = sys._getframe(1)
        f.f_globals[alias] = val


def _find_module(name: str) -> Optional[Path]:
    for d in _SEARCH_DIRS:
        p = Path(d) / f"{name}.nx"
        if p.exists():
            return p
    return None


# ══════════════════════════════════════════════════════════════════════════════
#  STRUCT
# ══════════════════════════════════════════════════════════════════════════════

def __nyx_struct__(name: str, fields: list, defaults: dict):
    return _NyxStructMaker(name, fields, defaults)


class _NyxStructMaker:
    __slots__ = ("name", "fields", "defaults")
    def __init__(self, name, fields, defaults):
        self.name = name
        self.fields = fields
        self.defaults = defaults

    def __call__(self, *args):
        if len(args) > len(self.fields):
            raise NyxError(
                "TypeError",
                f"{self.name}() takes at most {len(self.fields)} argument(s), "
                f"got {len(args)}",
            )
        d: dict = {}
        for i, fname in enumerate(self.fields):
            if i < len(args):
                d[fname] = args[i]
            elif fname in self.defaults:
                d[fname] = self.defaults[fname]
            else:
                raise NyxError(
                    "TypeError",
                    f"{self.name}() missing required field '{fname}'",
                    hint=f"Pass a value for '{fname}', or give it a default in the struct",
                )
        return NyxObject(d)

    def __repr__(self):
        return f"<struct {self.name}>"


# ══════════════════════════════════════════════════════════════════════════════
#  PYTHON BLOCK
# ══════════════════════════════════════════════════════════════════════════════

def __nyx_pyblock__(code: str, **kwargs):
    code = code.strip()
    if not code:
        return None
    fn_src = "def __nyx_block__():\n" + textwrap.indent(code, "    ")
    frame = sys._getframe(1)
    caller_g = frame.f_globals
    caller_l = dict(frame.f_locals)
    globals_dict = {**caller_g, **caller_l, "__builtins__": __builtins__, **kwargs}
    try:
        exec(fn_src, globals_dict)
        result = globals_dict["__nyx_block__"]()
        return _wrap(result)
    except NyxError:
        raise
    except Exception as e:
        raise NyxError("PythonError",
                       f"Python block raised {type(e).__name__}: {e}",
                       hint="Check your python: … end code for Python errors")


# ══════════════════════════════════════════════════════════════════════════════
#  NETWORK
# ══════════════════════════════════════════════════════════════════════════════

def _get(url: str) -> Any:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": f"Nyxel/{VERSION}"})
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read().decode("utf-8")
        try:
            return _wrap(json.loads(body))
        except json.JSONDecodeError:
            return body
    except NyxError:
        raise
    except Exception as e:
        raise NyxError("NetworkError", f"GET failed: {e}",
                       hint="Check the URL and your internet connection")


def _post(url: str, data: Any = None) -> Any:
    try:
        headers = {"User-Agent": f"Nyxel/{VERSION}"}
        payload = b""
        if data is not None:
            payload = json.dumps(_unwrap(data)).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read().decode("utf-8")
        try:
            return _wrap(json.loads(body))
        except json.JSONDecodeError:
            return body
    except NyxError:
        raise
    except Exception as e:
        raise NyxError("NetworkError", f"POST failed: {e}",
                       hint="Check the URL and your internet connection")


# ══════════════════════════════════════════════════════════════════════════════
#  FILE HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _read(path: str) -> str:
    p = Path(path)
    if not p.exists():
        raise NyxError("FileError", f"File not found: '{path}'",
                       hint="Check the path and make sure the file exists")
    return p.read_text(encoding="utf-8")


def _read_lines(path: str) -> list:
    p = Path(path)
    if not p.exists():
        raise NyxError("FileError", f"File not found: '{path}'",
                       hint="Check the path and make sure the file exists")
    return [line.rstrip() for line in p.read_text(encoding="utf-8").splitlines()]


def _lines_of(text: str) -> list:
    if not isinstance(text, str):
        raise NyxError("TypeError", f"lines_of() needs text, got {_nyx_type(text)}",
                       hint="Pass a text value to lines_of()")
    return text.splitlines()


def _words_of(text: str) -> list:
    if not isinstance(text, str):
        raise NyxError("TypeError", f"words_of() needs text, got {_nyx_type(text)}",
                       hint="Pass a text value to words_of()")
    return text.split()


def _write(path: str, content: Any) -> None:
    Path(path).write_text(str(content), encoding="utf-8")


def _append(path: str, content: Any) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(str(content))


def _save_json(path: str, data: Any) -> None:
    raw = _unwrap(data)
    try:
        Path(path).write_text(json.dumps(raw, indent=2), encoding="utf-8")
    except (TypeError, ValueError) as e:
        raise NyxError("FileError", f"Can't save JSON to '{path}': {e}",
                       hint="Make sure the data is a list or dict")


def _load_json(path: str) -> Any:
    p = Path(path)
    if not p.exists():
        raise NyxError("FileError", f"File not found: '{path}'",
                       hint="Check the path — did you save it first?")
    try:
        return _wrap(json.loads(p.read_text(encoding="utf-8")))
    except json.JSONDecodeError as e:
        raise NyxError("FileError", f"'{path}' is not valid JSON: {e}",
                       hint="Check that the file contains valid JSON")


# ══════════════════════════════════════════════════════════════════════════════
#  DATA MANIPULATION
# ══════════════════════════════════════════════════════════════════════════════

def _numbers_of(text_or_list: Any) -> list:
    result = []
    items = text_or_list.split() if isinstance(text_or_list, str) else text_or_list
    for item in items:
        raw = item._raw().get("value", item) if isinstance(item, NyxObject) else item
        try:
            n = float(str(raw))
            result.append(int(n) if n == int(n) else n)
        except (ValueError, TypeError):
            pass
    return result


def _average_of(lst: Any) -> float:
    if not isinstance(lst, list):
        raise NyxError("TypeError", f"average_of() needs a list, got {_nyx_type(lst)}",
                       hint="Write:  average_of(my_list)")
    nums = [x for x in lst if isinstance(x, (int, float))]
    if not nums:
        raise NyxError("MathError", "Cannot compute average of an empty list",
                       hint="Make sure the list has at least one number")
    return sum(nums) / len(nums)


def _sum_of(lst: Any) -> float:
    if not isinstance(lst, list):
        raise NyxError("TypeError", f"sum_of() needs a list, got {_nyx_type(lst)}",
                       hint="Write:  sum_of([10, 20, 30])")
    try:
        return sum(x for x in lst if isinstance(x, (int, float)))
    except TypeError:
        raise NyxError("TypeError", "sum_of() couldn't add the values in the list",
                       hint="Make sure the list contains only numbers")


def _max_of(lst: Any) -> Any:
    if not isinstance(lst, list):
        raise NyxError("TypeError", f"max_of() needs a list, got {_nyx_type(lst)}")
    if not lst:
        raise NyxError("MathError", "Cannot find the largest value in an empty list",
                       hint="Make sure the list has at least one item")
    return max(lst)


def _min_of(lst: Any) -> Any:
    if not isinstance(lst, list):
        raise NyxError("TypeError", f"min_of() needs a list, got {_nyx_type(lst)}")
    if not lst:
        raise NyxError("MathError", "Cannot find the smallest value in an empty list",
                       hint="Make sure the list has at least one item")
    return min(lst)


def _unique(lst: Any) -> list:
    if not isinstance(lst, list):
        raise NyxError("TypeError", f"unique() needs a list, got {_nyx_type(lst)}")
    seen = set()
    result = []
    for item in lst:
        key = _unwrap(item) if isinstance(item, NyxObject) else item
        try:
            if key not in seen:
                seen.add(key)
                result.append(item)
        except TypeError:
            if key not in result:
                result.append(item)
    return result


def _flatten(lst: Any) -> list:
    if not isinstance(lst, list):
        raise NyxError("TypeError", f"flatten() needs a list, got {_nyx_type(lst)}")
    result = []
    for item in lst:
        if isinstance(item, list):
            result.extend(item)
        else:
            result.append(item)
    return result


def _first_of(lst: Any) -> Any:
    if not isinstance(lst, list):
        raise NyxError("TypeError", f"first_of() needs a list, got {_nyx_type(lst)}")
    return lst[0] if lst else None


def _last_of(lst: Any) -> Any:
    if not isinstance(lst, list):
        raise NyxError("TypeError", f"last_of() needs a list, got {_nyx_type(lst)}")
    return lst[-1] if lst else None


def _group_by(lst: Any, key: str) -> Any:
    if not isinstance(lst, list):
        raise NyxError("TypeError", f"group_by() needs a list, got {_nyx_type(lst)}")
    result: dict = {}
    for item in lst:
        k = str(item._raw().get(key, "unknown")) if isinstance(item, NyxObject) else str(item)
        if k not in result:
            result[k] = []
        result[k].append(item)
    return _wrap(result)


# ══════════════════════════════════════════════════════════════════════════════
#  BOOLEAN HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _is_even(n: Any) -> bool:
    try:    return int(n) % 2 == 0
    except (TypeError, ValueError):
        raise NyxError("TypeError", f"is_even() needs a number, got '{_nyx_type(n)}'")

def _is_odd(n: Any) -> bool:
    try:    return int(n) % 2 != 0
    except (TypeError, ValueError):
        raise NyxError("TypeError", f"is_odd() needs a number, got '{_nyx_type(n)}'")

def _is_divisible_by(n: Any, d: Any) -> bool:
    try:
        if int(d) == 0:
            raise NyxError("MathError", "Can't check divisibility by zero")
        return int(n) % int(d) == 0
    except (TypeError, ValueError):
        raise NyxError("TypeError",
                       f"is_divisible_by() needs numbers, got '{_nyx_type(n)}' and '{_nyx_type(d)}'")

def _is_empty(x: Any) -> bool:
    try:    return len(x) == 0
    except TypeError:
        raise NyxError("TypeError",
                       f"is_empty() works on lists, text, and dicts — not {_nyx_type(x)}")

def _is_number(x: Any) -> bool: return isinstance(x, (int, float)) and not isinstance(x, bool)
def _is_text(x: Any) -> bool:   return isinstance(x, str)

def _count_of(lst: Any, value: Any) -> int:
    try:    return lst.count(value)
    except AttributeError:
        raise NyxError("TypeError", f"count_of() needs a list or text, got {_nyx_type(lst)}")


def _range(*args: Any) -> list:
    try:    return list(range(*[int(a) for a in args]))
    except (ValueError, TypeError) as e:
        raise NyxError("ValueError", f"range() error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  SYSTEM / COMMAND
# ══════════════════════════════════════════════════════════════════════════════

def _run_command(cmd: str) -> str:
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return (r.stdout + r.stderr).strip()


def _run_lines(cmd: str) -> list:
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return [line for line in (r.stdout + r.stderr).strip().splitlines() if line.strip()]


def _wait(amount, unit="seconds"):
    units = {
        "seconds": 1, "second": 1, "s": 1,
        "minutes": 60, "minute": 60, "min": 60, "m": 60,
        "hours": 3600, "hour": 3600, "h": 3600,
        "ms": 0.001, "milliseconds": 0.001, "millisecond": 0.001,
    }
    mul = units.get(str(unit).lower().strip())
    if mul is None:
        raise NyxError("ValueError", f"Unknown time unit '{unit}'",
                       hint="Use: seconds, minutes, hours, ms")
    _time.sleep(float(amount) * mul)


# ══════════════════════════════════════════════════════════════════════════════
#  DATE / TIME
# ══════════════════════════════════════════════════════════════════════════════

class _DateObj:
    def __init__(self, dt):
        self._dt = dt
    def __getattr__(self, name):
        dt = object.__getattribute__(self, "_dt")
        if name == "year":    return dt.year
        if name == "month":   return dt.month
        if name == "day":     return dt.day
        if name == "hour":    return dt.hour
        if name == "minute":  return dt.minute
        if name == "second":  return dt.second
        if name == "unix":    return int(dt.timestamp())
        if name == "weekday": return dt.strftime("%A")
        if name == "format":  return lambda p: dt.strftime(p)
        raise AttributeError(f"date has no field '{name}'")
    def __str__(self):
        return self._dt.strftime("%B %d, %Y  %I:%M %p")
    def __repr__(self):
        return self.__str__()


def _date():
    return _DateObj(_dt.datetime.now())

def _time_now():
    return _time.time()

def _listen_key():
    try:
        import readchar
        try:
            k = readchar.readkey()
        except KeyboardInterrupt:
            return "ctrl+c"
        special = {
            readchar.key.ENTER: "enter", readchar.key.SPACE: "space",
            readchar.key.BACKSPACE: "backspace", readchar.key.TAB: "tab",
            readchar.key.UP: "up", readchar.key.DOWN: "down",
            readchar.key.LEFT: "left", readchar.key.RIGHT: "right",
            readchar.key.ESC: "escape",
        }
        if k in special:
            return special[k]
        if isinstance(k, str) and len(k) == 1 and "\x01" <= k <= "\x1a":
            return f"ctrl+{chr(ord('a') + ord(k) - 1)}"
        return k
    except ImportError:
        raise NyxError("ImportError", "listen_key() needs the readchar package",
                       hint="Run:  pip install readchar")


def _on_key(key):
    """Block until the given key is pressed, then return true.

        on_key("q")          # wait for 'q'
        when on_key("esc"):  # wait for Escape
            exit()
    """
    target = str(key)
    while _listen_key() != target:
        pass
    return True


# ══════════════════════════════════════════════════════════════════════════════
#  RUNTIME SETUP
# ══════════════════════════════════════════════════════════════════════════════

def __nyx_runtime(script_args: Optional[list] = None) -> dict:
    g: dict = {}

    # --- core Nyxel types and signals ---
    g["NyxError"] = NyxError
    g["NyxObject"] = NyxObject
    g["NyxStruct"] = NyxStruct
    g["NyxException"] = NyxException
    g["_Return"] = _Return
    g["_Break"] = _Break
    g["_Continue"] = _Continue
    g["_wrap"] = _wrap
    g["_unwrap"] = _unwrap

    # --- runtime helpers ---
    g["__nyx_len"] = _nyx_len
    g["__nyx_is_empty"]  = _nyx_is_empty
    g["__nyx_list_sorted"]   = _nyx_list_sorted
    g["__nyx_list_reversed"] = _nyx_list_reversed
    g["__nyx_list_first"]    = _nyx_list_first
    g["__nyx_list_last"]     = _nyx_list_last
    g["__nyx_where__"]  = __nyx_where__
    g["__nyx_bring__"]  = __nyx_bring__
    g["__nyx_bring_from__"] = __nyx_bring_from__
    g["__nyx_struct__"] = __nyx_struct__
    g["__nyx_pyblock__"] = __nyx_pyblock__
    g["__nyx_catch_convert"] = _nyx_catch_convert

    # --- display ---
    g["say"]    = _say
    g["pretty"] = _pretty

    # --- network ---
    g["get"]  = _get
    g["post"] = _post

    # --- file ---
    g["read"]       = _read
    g["write"]      = _write
    g["append"]     = _append
    g["read_lines"] = _read_lines
    g["lines_of"]   = _lines_of
    g["words_of"]   = _words_of
    g["save_json"]  = _save_json
    g["load_json"]  = _load_json

    # --- data ---
    g["numbers_of"] = _numbers_of
    g["average_of"] = _average_of
    g["sum_of"]     = _sum_of
    g["max_of"]     = _max_of
    g["min_of"]     = _min_of
    g["unique"]     = _unique
    g["flatten"]    = _flatten
    g["first_of"]   = _first_of
    g["last_of"]    = _last_of
    g["group_by"]   = _group_by

    # --- type ---
    g["len"]      = _nyx_len
    g["type"]     = _nyx_type
    g["str"]      = _nyx_str
    g["int"]      = _nyx_int
    g["float"]    = _nyx_float
    g["bool"]     = bool
    g["to_str"]   = _nyx_str
    g["to_int"]   = _nyx_int
    g["to_float"] = _nyx_float

    # --- boolean ---
    g["is_even"]         = _is_even
    g["is_odd"]          = _is_odd
    g["is_divisible_by"] = _is_divisible_by
    g["is_empty"]        = _is_empty
    g["is_number"]       = _is_number
    g["is_text"]         = _is_text
    g["count_of"]        = _count_of

    # --- math ---
    g["abs"]   = abs
    g["round"] = round
    g["floor"] = math.floor
    g["ceil"]  = math.ceil
    g["sqrt"]  = math.sqrt
    g["pow"]   = pow
    g["log"]   = math.log
    g["pi"]    = math.pi
    g["e"]     = math.e
    g["inf"]   = math.inf

    # --- random ---
    g["random"]   = _random.random
    g["rand_int"] = lambda a, b: _random.randint(int(a), int(b))
    g["choice"]   = _random.choice
    g["shuffle"]  = lambda lst: _random.sample(lst, len(lst))

    # --- sequence ---
    g["range"]    = _range
    g["sorted"]   = sorted
    g["reversed"] = lambda lst: list(reversed(lst))
    g["zip"]      = lambda *lsts: [list(row) for row in zip(*lsts)]
    g["enumerate"] = lambda lst: [[i, v] for i, v in enumerate(lst)]
    g["any"]      = lambda lst: any(lst)
    g["all"]      = lambda lst: all(lst)
    g["map"]      = lambda fn, lst: list(map(fn, lst))
    g["filter"]   = lambda fn, lst: list(filter(fn, lst))

    # --- string ---
    g["split"]       = lambda s, sep=None: s.split(sep) if sep else s.split()
    g["join"]        = lambda sep, lst: sep.join(_nyx_str(x) for x in lst)
    g["strip"]       = lambda s: s.strip()
    g["upper"]       = lambda s: s.upper()
    g["lower"]       = lambda s: s.lower()
    g["replace"]     = lambda s, a, b: s.replace(a, b)
    g["starts_with"] = lambda s, p: s.startswith(p)
    g["ends_with"]   = lambda s, p: s.endswith(p)
    g["contains"]    = lambda s, sub: sub in s
    g["format"]      = lambda tmpl, *a: tmpl.format(*a)

    # --- json ---
    g["to_json"]   = lambda x: json.dumps(_unwrap(x), indent=2)
    g["from_json"] = lambda s: _wrap(json.loads(s))

    # --- system ---
    g["env"]        = lambda k, d="": os.environ.get(k, d)
    g["run"]        = _run_command
    g["run_lines"]  = _run_lines
    g["exit"]       = sys.exit
    g["quit_app"]   = sys.exit
    g["args"]       = script_args or []
    g["exists"]     = os.path.exists
    g["ls"]         = lambda p=".": os.listdir(p)
    g["mkdir"]      = lambda p: os.makedirs(p, exist_ok=True) or True
    g["cwd"]        = os.getcwd
    g["wait"]       = _wait
    g["date"]       = _date
    g["time"]       = _time_now
    g["unix"]       = lambda: int(_time.time())
    g["listen_key"] = _listen_key
    g["on_key"]     = _on_key

    # --- constants ---
    g["true"]  = True
    g["false"] = False
    g["none"]  = None

    # --- Arabic aliases ---
    g["قل"]          = _say
    g["اطبع"]        = _say
    g["احضر"]        = _get
    g["أرسل"]        = _post
    g["اقرأ"]        = _read
    g["اكتب"]        = _write
    g["ألحق"]        = _append
    g["اقرأ_أسطر"]   = _read_lines
    g["أسطر"]        = _lines_of
    g["كلمات"]       = _words_of
    g["احفظ_json"]   = _save_json
    g["احمل_json"]   = _load_json
    g["أرقام"]       = _numbers_of
    g["متوسط"]       = _average_of
    g["مجموع"]       = _sum_of
    g["أكبر"]        = _max_of
    g["أصغر"]        = _min_of
    g["فريد"]        = _unique
    g["اجمع"]        = _flatten
    g["الأول"]       = _first_of
    g["الأخير"]      = _last_of
    g["جمع_حسب"]     = _group_by
    g["طول"]         = _nyx_len
    g["نوع"]         = _nyx_type
    g["نص"]          = _nyx_str
    g["إلى_نص"]      = _nyx_str
    g["إلى_عدد"]     = _nyx_int
    g["إلى_عشري"]    = _nyx_float
    g["زوجي"]        = _is_even
    g["فردي"]        = _is_odd
    g["يقبل_القسمة"] = _is_divisible_by
    g["فارغ"]        = _is_empty
    g["هو_رقم"]      = _is_number
    g["هو_نص"]       = _is_text
    g["عدد_تكرار"]   = _count_of
    g["قيمة_مطلقة"]  = abs
    g["تقريب"]       = round
    g["جذر"]         = math.sqrt
    g["أرضي"]        = math.floor
    g["سقفي"]        = math.ceil
    g["مدى"]         = _range
    g["مرتب"]        = sorted
    g["معكوس"]       = lambda lst: list(reversed(lst))
    g["ادمج"]        = lambda sep, lst: sep.join(_nyx_str(x) for x in lst)
    g["قص"]          = lambda s: s.strip()
    g["كبير"]        = lambda s: s.upper()
    g["صغير"]        = lambda s: s.lower()
    g["استبدل"]      = lambda s, a, b: s.replace(a, b)
    g["بيئة"]        = lambda k, d="": os.environ.get(k, d)
    g["نفذ"]         = _run_command
    g["موجود"]       = os.path.exists
    g["انتظر"]       = _wait
    g["وقت"]         = _time_now
    g["تاريخ"]       = _date
    g["استمع"]       = _listen_key
    g["عند_المفتاح"] = _on_key
    g["إنهاء"]       = sys.exit
    g["أنهِ"]        = sys.exit
    g["صحيح"]        = True
    g["خطأ"]         = False
    g["لاشيء"]       = None

    g["__builtins__"] = {"Exception": Exception}
    return g
