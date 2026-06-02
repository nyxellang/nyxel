"""nyxel.builtins"""

from __future__ import annotations

import json
import math
import os
import random as _random
import subprocess
import sys
import time as _time
import datetime as _dt
import urllib.request
from pathlib import Path
from typing import Any, List

from .errors import NyxError
from .runtime import Environment, NyxFunction, NyxObject, _wrap, _unwrap
from .version import VERSION


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
        raise NyxError("TypeError", f"lines_of() needs text, got {_type(text)}",
                       hint="Pass a text value to lines_of()")
    return text.splitlines()


def _words_of(text: str) -> list:
    if not isinstance(text, str):
        raise NyxError("TypeError", f"words_of() needs text, got {_type(text)}",
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
        raise NyxError("TypeError", f"average_of() needs a list, got {_type(lst)}",
                       hint="Write:  average_of(my_list)")
    nums = [x for x in lst if isinstance(x, (int, float))]
    if not nums:
        raise NyxError("MathError", "Cannot compute average of an empty list",
                       hint="Make sure the list has at least one number")
    return sum(nums) / len(nums)


def _sum_of(lst: Any) -> float:
    if not isinstance(lst, list):
        raise NyxError("TypeError", f"sum_of() needs a list, got {_type(lst)}",
                       hint="Write:  sum_of([10, 20, 30])")
    try:
        return sum(x for x in lst if isinstance(x, (int, float)))
    except TypeError:
        raise NyxError("TypeError", "sum_of() couldn't add the values in the list",
                       hint="Make sure the list contains only numbers")


def _max_of(lst: Any) -> Any:
    if not isinstance(lst, list):
        raise NyxError("TypeError", f"max_of() needs a list, got {_type(lst)}")
    if not lst:
        raise NyxError("MathError", "Cannot find the largest value in an empty list",
                       hint="Make sure the list has at least one item")
    return max(lst)


def _min_of(lst: Any) -> Any:
    if not isinstance(lst, list):
        raise NyxError("TypeError", f"min_of() needs a list, got {_type(lst)}")
    if not lst:
        raise NyxError("MathError", "Cannot find the smallest value in an empty list",
                       hint="Make sure the list has at least one item")
    return min(lst)


def _unique(lst: Any) -> list:
    if not isinstance(lst, list):
        raise NyxError("TypeError", f"unique() needs a list, got {_type(lst)}")
    seen = []
    result = []
    for item in lst:
        key = _unwrap(item) if isinstance(item, NyxObject) else item
        if key not in seen:
            seen.append(key)
            result.append(item)
    return result


def _flatten(lst: Any) -> list:
    if not isinstance(lst, list):
        raise NyxError("TypeError", f"flatten() needs a list, got {_type(lst)}")
    result = []
    for item in lst:
        if isinstance(item, list):
            result.extend(item)
        else:
            result.append(item)
    return result


def _first_of(lst: Any) -> Any:
    if not isinstance(lst, list):
        raise NyxError("TypeError", f"first_of() needs a list, got {_type(lst)}")
    return lst[0] if lst else None


def _last_of(lst: Any) -> Any:
    if not isinstance(lst, list):
        raise NyxError("TypeError", f"last_of() needs a list, got {_type(lst)}")
    return lst[-1] if lst else None


def _group_by(lst: Any, key: str) -> Any:
    if not isinstance(lst, list):
        raise NyxError("TypeError", f"group_by() needs a list, got {_type(lst)}")
    result: dict = {}
    for item in lst:
        k = str(item._raw().get(key, "unknown")) if isinstance(item, NyxObject) else str(item)
        if k not in result:
            result[k] = []
        result[k].append(item)
    return _wrap(result)


def _len(x: Any) -> int:
    try:
        return len(x)
    except TypeError:
        raise NyxError("TypeError", f"len() does not work on {_type(x)} values")


def _type(x: Any) -> str:
    if x is None:                   return "none"
    if isinstance(x, bool):         return "bool"
    if isinstance(x, (int, float)): return "number"
    if isinstance(x, str):          return "text"
    if isinstance(x, list):         return "list"
    if isinstance(x, (NyxObject, dict)): return "dict"
    if isinstance(x, NyxFunction):  return "function"
    return type(x).__name__


def _str(x: Any) -> str:
    if x is None:  return "none"
    if x is True:  return "true"
    if x is False: return "false"
    return str(x)


def _int(x: Any) -> int:
    try:
        return int(x)
    except (ValueError, TypeError):
        raise NyxError("TypeError", f"Can't convert '{x}' to a whole number",
                       hint='Make sure the value is a number or a text like "42"')


def _float(x: Any) -> float:
    try:
        return float(x)
    except (ValueError, TypeError):
        raise NyxError("TypeError", f"Can't convert '{x}' to a number",
                       hint="Make sure the value looks like a number")


def _to_str(x: Any) -> str:   return _str(x)
def _to_int(x: Any) -> int:   return _int(x)
def _to_float(x: Any) -> float: return _float(x)


def _is_even(n: Any) -> bool:
    try:    return int(n) % 2 == 0
    except (TypeError, ValueError):
        raise NyxError("TypeError", f"is_even() needs a number, got '{_type(n)}'")

def _is_odd(n: Any) -> bool:
    try:    return int(n) % 2 != 0
    except (TypeError, ValueError):
        raise NyxError("TypeError", f"is_odd() needs a number, got '{_type(n)}'")

def _is_divisible_by(n: Any, d: Any) -> bool:
    try:
        if int(d) == 0:
            raise NyxError("MathError", "Can't check divisibility by zero")
        return int(n) % int(d) == 0
    except (TypeError, ValueError):
        raise NyxError("TypeError",
                       f"is_divisible_by() needs numbers, got '{_type(n)}' and '{_type(d)}'")

def _is_empty(x: Any) -> bool:
    try:    return len(x) == 0
    except TypeError:
        raise NyxError("TypeError",
                       f"is_empty() works on lists, text, and dicts — not {_type(x)}")

def _is_number(x: Any) -> bool: return isinstance(x, (int, float)) and not isinstance(x, bool)
def _is_text(x: Any) -> bool:   return isinstance(x, str)

def _count_of(lst: Any, value: Any) -> int:
    try:    return lst.count(value)
    except AttributeError:
        raise NyxError("TypeError", f"count_of() needs a list or text, got {_type(lst)}")


def _range(*args: Any) -> list:
    try:    return list(range(*[int(a) for a in args]))
    except (ValueError, TypeError) as e:
        raise NyxError("ValueError", f"range() error: {e}")


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


# returns a human-readable date/time object with fields and methods
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
        # format("pattern") -> custom strftime
        if name == "format":  return lambda p: dt.strftime(p)
        raise AttributeError(f"date has no field '{name}'")

    def __str__(self):
        return self._dt.strftime("%B %d, %Y  %I:%M %p")

    def __repr__(self):
        return self.__str__()


def _date():
    return _DateObj(_dt.datetime.now())


def _time_now():
    return _dt.datetime.now().strftime("%I:%M %p")



def _listen_key():
    try:
        import readchar
        k = readchar.readkey()
        # normalize special keys to readable names
        special = {
            readchar.key.ENTER: "enter", readchar.key.SPACE: "space",
            readchar.key.BACKSPACE: "backspace", readchar.key.TAB: "tab",
            readchar.key.UP: "up", readchar.key.DOWN: "down",
            readchar.key.LEFT: "left", readchar.key.RIGHT: "right",
            readchar.key.ESC: "escape",
        }
        return special.get(k, k)
    except ImportError:
        raise NyxError("ImportError", "listen_key() needs the readchar package",
                       hint="Run:  pip install readchar")


def setup_builtins(env: Environment, script_args: List[str] = None) -> None:

    env.define("say",    _say)
    env.define("pretty", _pretty)

    env.define("get",    _get)
    env.define("post",   _post)

    env.define("read",       _read)
    env.define("write",      _write)
    env.define("append",     _append)
    env.define("read_lines", _read_lines)
    env.define("lines_of",   _lines_of)
    env.define("words_of",   _words_of)
    env.define("save_json",  _save_json)
    env.define("load_json",  _load_json)

    env.define("numbers_of", _numbers_of)
    env.define("average_of", _average_of)
    env.define("sum_of",     _sum_of)
    env.define("max_of",     _max_of)
    env.define("min_of",     _min_of)
    env.define("unique",     _unique)
    env.define("flatten",    _flatten)
    env.define("first_of",   _first_of)
    env.define("last_of",    _last_of)
    env.define("group_by",   _group_by)

    env.define("len",      _len)
    env.define("type",     _type)
    env.define("str",      _str)
    env.define("int",      _int)
    env.define("float",    _float)
    env.define("bool",     bool)
    env.define("to_str",   _to_str)
    env.define("to_int",   _to_int)
    env.define("to_float", _to_float)

    env.define("is_even",         _is_even)
    env.define("is_odd",          _is_odd)
    env.define("is_divisible_by", _is_divisible_by)
    env.define("is_empty",        _is_empty)
    env.define("is_number",       _is_number)
    env.define("is_text",         _is_text)
    env.define("count_of",        _count_of)

    env.define("abs",   abs)
    env.define("round", round)
    env.define("floor", math.floor)
    env.define("ceil",  math.ceil)
    env.define("sqrt",  math.sqrt)
    env.define("pow",   pow)
    env.define("log",   math.log)
    env.define("pi",    math.pi)
    env.define("e",     math.e)
    env.define("inf",   math.inf)

    env.define("random",   _random.random)
    env.define("rand_int", lambda a, b: _random.randint(int(a), int(b)))
    env.define("choice",   _random.choice)
    env.define("shuffle",  lambda lst: _random.sample(lst, len(lst)))

    env.define("range",    _range)
    env.define("sorted",   sorted)
    env.define("reversed", lambda lst: list(reversed(lst)))
    env.define("zip",      lambda *lsts: [list(row) for row in zip(*lsts)])
    env.define("enumerate", lambda lst: [[i, v] for i, v in enumerate(lst)])
    env.define("any",      lambda lst: any(lst))
    env.define("all",      lambda lst: all(lst))
    env.define("map",      lambda fn, lst: list(map(fn, lst)))
    env.define("filter",   lambda fn, lst: list(filter(fn, lst)))

    env.define("split",       lambda s, sep=None: s.split(sep) if sep else s.split())
    env.define("join",        lambda sep, lst: sep.join(_str(x) for x in lst))
    env.define("strip",       lambda s: s.strip())
    env.define("upper",       lambda s: s.upper())
    env.define("lower",       lambda s: s.lower())
    env.define("replace",     lambda s, a, b: s.replace(a, b))
    env.define("starts_with", lambda s, p: s.startswith(p))
    env.define("ends_with",   lambda s, p: s.endswith(p))
    env.define("contains",    lambda s, sub: sub in s)
    env.define("format",      lambda tmpl, *a: tmpl.format(*a))

    env.define("to_json",   lambda x: json.dumps(_unwrap(x), indent=2))
    env.define("from_json", lambda s: _wrap(json.loads(s)))

    env.define("env",       lambda k, d="": os.environ.get(k, d))
    env.define("run",       _run_command)
    env.define("run_lines", _run_lines)
    env.define("exit",      sys.exit)
    env.define("args",      script_args or [])
    env.define("exists",    os.path.exists)
    env.define("ls",        lambda p=".": os.listdir(p))
    env.define("mkdir",     lambda p: os.makedirs(p, exist_ok=True) or True)
    env.define("cwd",       os.getcwd)
    env.define("wait",       _wait)
    env.define("date",       _date)
    env.define("time",       _time_now)
    env.define("unix",       lambda: int(_time.time()))
    env.define("listen_key",  _listen_key)

    env.define("true",  True)
    env.define("false", False)
    env.define("none",  None)

    # ── Arabic built-in aliases ───────────────────────────────────────────────
    env.define("قل",          _say)
    env.define("اطبع",        _say)
    env.define("احضر",        _get)
    env.define("أرسل",        _post)
    env.define("اقرأ",        _read)
    env.define("اكتب",        _write)
    env.define("ألحق",        _append)
    env.define("اقرأ_أسطر",   _read_lines)
    env.define("أسطر",        _lines_of)
    env.define("كلمات",       _words_of)
    env.define("احفظ_json",   _save_json)
    env.define("احمل_json",   _load_json)
    env.define("أرقام",       _numbers_of)
    env.define("متوسط",       _average_of)
    env.define("مجموع",       _sum_of)
    env.define("أكبر",        _max_of)
    env.define("أصغر",        _min_of)
    env.define("فريد",        _unique)
    env.define("اجمع",        _flatten)
    env.define("الأول",       _first_of)
    env.define("الأخير",      _last_of)
    env.define("جمع_حسب",     _group_by)
    env.define("طول",         _len)
    env.define("نوع",         _type)
    env.define("نص",          _str)
    env.define("إلى_نص",      _to_str)
    env.define("إلى_عدد",     _to_int)
    env.define("إلى_عشري",    _to_float)
    env.define("زوجي",        _is_even)
    env.define("فردي",        _is_odd)
    env.define("يقبل_القسمة", _is_divisible_by)
    env.define("فارغ",        _is_empty)
    env.define("هو_رقم",      _is_number)
    env.define("هو_نص",       _is_text)
    env.define("عدد_تكرار",   _count_of)
    env.define("قيمة_مطلقة",  abs)
    env.define("تقريب",       round)
    env.define("جذر",         math.sqrt)
    env.define("أرضي",        math.floor)
    env.define("سقفي",        math.ceil)
    env.define("مدى",         _range)
    env.define("مرتب",        sorted)
    env.define("معكوس",       lambda lst: list(reversed(lst)))
    env.define("ادمج",        lambda sep, lst: sep.join(_str(x) for x in lst))
    env.define("قص",          lambda s: s.strip())
    env.define("كبير",        lambda s: s.upper())
    env.define("صغير",        lambda s: s.lower())
    env.define("استبدل",      lambda s, a, b: s.replace(a, b))
    env.define("بيئة",        lambda k, d="": os.environ.get(k, d))
    env.define("نفذ",         _run_command)
    env.define("موجود",       os.path.exists)
    env.define("صحيح",        True)
    env.define("خطأ",         False)
    env.define("لاشيء",       None)