"""
nyxel.builtins
──────────────
All built-in functions and constants available in every Nyxel script.

Design rule: if most users need it → built-in.  Otherwise → module (future).

Categories
──────────
  output      say()  pretty()
  http        get()  post()
  file        read()  write()  append()
              read_lines()  lines_of()  words_of()
              save_json()  load_json()
  data        numbers_of()  average_of()  sum_of()  max_of()  min_of()
              unique()  flatten()  first_of()  last_of()  zip_with()
  types       len()  type()  str()  int()  float()  bool()
              to_str()  to_int()  to_float()
  checks      is_even()  is_odd()  is_divisible_by()
              is_number()  is_text()  is_empty()  count_of()
  math        abs  round  floor  ceil  sqrt  max  min  sum  pow  pi  e  inf
  random      random  rand_int  choice  shuffle
  sequences   range  sorted  reversed  zip  enumerate  map  filter  any  all
  strings     split  join  strip  upper  lower  replace  starts_with  ends_with
              contains  format
  json        to_json  from_json
  os/system   env  run  run_lines  exit  args  exists  ls  mkdir  cwd  sleep  time

Native dot-access properties (resolved in interpreter.AttrExpr)
──────────────────────────────────────────────────────────────────
  "hello".length      → 5
  [1,2,3].length      → 3
  {"a":1}.length      → 1
  "".is_empty()       → true
  [].is_empty()       → true
  "hello".upper()     → "HELLO"    (string methods forwarded)
  "hello".contains("ell") → true
"""

from __future__ import annotations

import json
import math
import os
import random as _random
import sys
import time as _time
from typing import Any, List

from .errors import NyxError
from .runtime import Environment, NyxFunction, NyxObject, _wrap, _unwrap
from .version import VERSION


# ── output ────────────────────────────────────────────────────────────────────

def _display(v: Any) -> str:
    """Convert a Nyxel value to its display string."""
    if v is True:  return "true"
    if v is False: return "false"
    if v is None:  return "none"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _say(*args: Any) -> None:
    """say(a, b, …) — print values space-joined, using Nyxel display names."""
    print(" ".join(_display(a) for a in args))


def _pretty(data: Any) -> None:
    """
    pretty(data) — print any value in a readable format.

    For dicts and lists, prints nicely indented JSON.
    For everything else, behaves like say().

        pretty(users)
        pretty({"name": "Alice", "age": 25})
    """
    raw = _unwrap(data)
    try:
        print(json.dumps(raw, indent=2))
    except (TypeError, ValueError):
        print(_display(data))


# ── HTTP ──────────────────────────────────────────────────────────────────────

def _get(url: str) -> Any:
    """
    HTTP GET.  Auto-parses a JSON response into dot-accessible NyxObjects.
    Returns raw text if the response is not JSON.
    """
    try:
        import urllib.request
        req = urllib.request.Request(
            url, headers={"User-Agent": f"Nyxel/{VERSION}"}
        )
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
    """
    HTTP POST with a JSON body.  Auto-parses a JSON response.
    """
    try:
        import urllib.request
        headers = {"User-Agent": f"Nyxel/{VERSION}"}
        payload = b""
        if data is not None:
            payload = json.dumps(_unwrap(data)).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(
            url, data=payload, headers=headers, method="POST"
        )
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


# ── file ──────────────────────────────────────────────────────────────────────

def _read(path: str) -> str:
    from pathlib import Path
    p = Path(path)
    if not p.exists():
        raise NyxError("FileError", f"File not found: '{path}'",
                       hint="Check the path and make sure the file exists")
    return p.read_text(encoding="utf-8")


def _read_lines(path: str) -> list:
    """
    read_lines(path) — read a file and return each line as a list item.
    Empty lines are included as empty strings.

        let lines = read_lines("notes.txt")
        for each line in lines:
            say(line)
    """
    from pathlib import Path
    p = Path(path)
    if not p.exists():
        raise NyxError("FileError", f"File not found: '{path}'",
                       hint="Check the path and make sure the file exists")
    return [line.rstrip() for line in p.read_text(encoding="utf-8").splitlines()]


def _lines_of(text: str) -> list:
    """
    lines_of(text) — split text into a list of lines.
    Use instead of  text.split("\\n").
    """
    if not isinstance(text, str):
        raise NyxError("TypeError", f"lines_of() needs text, got {_type(text)}",
                       hint="Pass a text value to lines_of()")
    return text.splitlines()


def _words_of(text: str) -> list:
    """
    words_of(text) — split text into individual words.
    Handles multiple spaces, tabs, and newlines automatically.
    """
    if not isinstance(text, str):
        raise NyxError("TypeError", f"words_of() needs text, got {_type(text)}",
                       hint="Pass a text value to words_of()")
    return text.split()


def _write(path: str, content: Any) -> None:
    from pathlib import Path
    Path(path).write_text(str(content), encoding="utf-8")


def _append(path: str, content: Any) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(str(content))


def _save_json(path: str, data: Any) -> None:
    """
    save_json(path, data) — save a list or dict to a JSON file.

    The file is human-readable (indented).
    Use load_json() to read it back.

        save_json("users.json", users)
        save_json("config.json", {"host": "localhost", "port": 8080})
    """
    from pathlib import Path
    raw = _unwrap(data)
    try:
        Path(path).write_text(json.dumps(raw, indent=2), encoding="utf-8")
    except (TypeError, ValueError) as e:
        raise NyxError("FileError", f"Can't save JSON to '{path}': {e}",
                       hint="Make sure the data is a list or dict")


def _load_json(path: str) -> Any:
    """
    load_json(path) — load a JSON file and return it as a Nyxel object.

    Use after save_json() or on any .json file.

        let users = load_json("users.json")
        say(users.length, "users loaded")
    """
    from pathlib import Path
    p = Path(path)
    if not p.exists():
        raise NyxError("FileError", f"File not found: '{path}'",
                       hint="Check the path — did you save it first?")
    try:
        return _wrap(json.loads(p.read_text(encoding="utf-8")))
    except json.JSONDecodeError as e:
        raise NyxError("FileError", f"'{path}' is not valid JSON: {e}",
                       hint="Check that the file contains valid JSON")


# ── data helpers ──────────────────────────────────────────────────────────────

def _numbers_of(text_or_list: Any) -> list:
    """
    numbers_of(text_or_list) — extract all numbers from text or a mixed list.

    From text:  reads whitespace-separated tokens and converts each to a number.
    From list:  keeps only the numeric items.
    Non-numeric tokens are silently skipped.

        let values = numbers_of(read("data.txt"))
        say("Average:", average_of(values))

        numbers_of("10 20 bad 30")   # → [10, 20, 30]
        numbers_of([1, "skip", 2])   # → [1, 2]
    """
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
    """
    average_of(list) — calculate the average (mean) of a list of numbers.

        let values = [10, 20, 30, 40]
        say("Average:", average_of(values))   # → 25
    """
    if not isinstance(lst, list):
        raise NyxError(
            "TypeError",
            f"average_of() needs a list, got {_type(lst)}",
            hint="Write:  average_of(my_list)  where my_list is a list of numbers",
        )
    nums = [x for x in lst if isinstance(x, (int, float))]
    if not nums:
        raise NyxError(
            "MathError",
            "Cannot compute average of an empty list",
            hint="Make sure the list has at least one number.\n"
                 "  Example:  let values = numbers_of(read(\"data.txt\"))",
        )
    return sum(nums) / len(nums)


def _sum_of(lst: Any) -> float:
    """sum_of(list) — add up all numbers in a list."""
    if not isinstance(lst, list):
        raise NyxError(
            "TypeError",
            f"sum_of() needs a list, got {_type(lst)}",
            hint="Write:  sum_of([10, 20, 30])  or  sum_of(my_list)",
        )
    try:
        return sum(x for x in lst if isinstance(x, (int, float)))
    except TypeError as e:
        raise NyxError(
            "TypeError",
            "sum_of() couldn't add the values in the list",
            hint="Make sure the list contains only numbers",
        )


def _max_of(lst: Any) -> Any:
    """max_of(list) — return the largest value in a list."""
    if not isinstance(lst, list):
        raise NyxError(
            "TypeError",
            f"max_of() needs a list, got {_type(lst)}",
            hint="Write:  max_of([3, 1, 9])  or  max_of(my_list)",
        )
    if not lst:
        raise NyxError(
            "MathError",
            "Cannot find the largest value in an empty list",
            hint="Make sure the list has at least one item",
        )
    return max(lst)


def _min_of(lst: Any) -> Any:
    """min_of(list) — return the smallest value in a list."""
    if not isinstance(lst, list):
        raise NyxError(
            "TypeError",
            f"min_of() needs a list, got {_type(lst)}",
            hint="Write:  min_of([3, 1, 9])  or  min_of(my_list)",
        )
    if not lst:
        raise NyxError(
            "MathError",
            "Cannot find the smallest value in an empty list",
            hint="Make sure the list has at least one item",
        )
    return min(lst)


def _unique(lst: Any) -> list:
    """
    unique(list) — return a list with duplicates removed, order preserved.

        unique([1, 2, 2, 3, 1])   # → [1, 2, 3]
    """
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
    """
    flatten(list) — turn a list of lists into a single flat list.

        flatten([[1,2], [3,4], [5]])   # → [1, 2, 3, 4, 5]
    """
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
    """
    first_of(list) — return the first item, or none if the list is empty.

        first_of([10, 20, 30])   # → 10
        first_of([])             # → none
    """
    if not isinstance(lst, list):
        raise NyxError("TypeError", f"first_of() needs a list, got {_type(lst)}")
    return lst[0] if lst else None


def _last_of(lst: Any) -> Any:
    """
    last_of(list) — return the last item, or none if the list is empty.

        last_of([10, 20, 30])   # → 30
    """
    if not isinstance(lst, list):
        raise NyxError("TypeError", f"last_of() needs a list, got {_type(lst)}")
    return lst[-1] if lst else None


def _group_by(lst: Any, key: str) -> Any:
    """
    group_by(list, field) — group a list of objects by a field value.

    Returns a dict where each key is a field value and the value is a list
    of items that have that value.

        let by_city = group_by(users, "city")
        for each city in by_city.keys():
            say(city, ":", by_city[city].length, "users")
    """
    if not isinstance(lst, list):
        raise NyxError("TypeError", f"group_by() needs a list, got {_type(lst)}")
    result: dict = {}
    for item in lst:
        if isinstance(item, NyxObject):
            d = item._raw()
            k = str(d.get(key, "unknown"))
        else:
            k = str(item)
        if k not in result:
            result[k] = []
        result[k].append(item)
    return _wrap(result)


# ── type utilities ────────────────────────────────────────────────────────────

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
    if isinstance(x, NyxObject):    return "dict"
    if isinstance(x, dict):         return "dict"
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
        raise NyxError("TypeError",
                       f"Can't convert '{x}' to a whole number",
                       hint='Make sure the value is a number or a text like "42"')


def _float(x: Any) -> float:
    try:
        return float(x)
    except (ValueError, TypeError):
        raise NyxError("TypeError",
                       f"Can't convert '{x}' to a number",
                       hint="Make sure the value looks like a number")


# ── beginner-friendly type aliases ────────────────────────────────────────────

def _to_str(x: Any) -> str:
    """to_str(x) — convert any value to text."""
    return _str(x)

def _to_int(x: Any) -> int:
    """to_int(x) — convert text or a number to a whole number."""
    return _int(x)

def _to_float(x: Any) -> float:
    """to_float(x) — convert text or a number to a decimal number."""
    return _float(x)


# ── check functions ───────────────────────────────────────────────────────────

def _is_even(n: Any) -> bool:
    try:
        return int(n) % 2 == 0
    except (TypeError, ValueError):
        raise NyxError("TypeError", f"is_even() needs a number, got '{_type(n)}'")

def _is_odd(n: Any) -> bool:
    try:
        return int(n) % 2 != 0
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
    try:
        return len(x) == 0
    except TypeError:
        raise NyxError("TypeError",
                       f"is_empty() works on lists, text, and dicts — not {_type(x)}")

def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)

def _is_text(x: Any) -> bool:
    return isinstance(x, str)

def _count_of(lst: Any, value: Any) -> int:
    try:
        return lst.count(value)
    except AttributeError:
        raise NyxError("TypeError",
                       f"count_of() needs a list or text, got {_type(lst)}")


# ── sequences ─────────────────────────────────────────────────────────────────

def _range(*args: Any) -> list:
    try:
        return list(range(*[int(a) for a in args]))
    except (ValueError, TypeError) as e:
        raise NyxError("ValueError", f"range() error: {e}")


# ── OS / system ───────────────────────────────────────────────────────────────

def _run_command(cmd: str) -> str:
    """
    run(command) — run a shell command and return its output as text.

        let output = run("ls")
        say(output)

        run("python my_script.py")
        run("docker ps")
    """
    import subprocess
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    combined = (r.stdout + r.stderr).strip()
    return combined


def _run_lines(cmd: str) -> list:
    """
    run_lines(command) — run a shell command and return each line of output
    as a list item.  Useful when you want to process output line by line.

        let processes = run_lines("docker ps")
        say("Running:", processes.length, "containers")

        for each line in run_lines("ls -la"):
            say(line)
    """
    import subprocess
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    combined = (r.stdout + r.stderr).strip()
    return [line for line in combined.splitlines() if line.strip()]


# ── registration ──────────────────────────────────────────────────────────────

def _nyx_map(fn, lst, interpreter):
    """map() that works with both Python callables and NyxFunctions."""
    return [interpreter._call(fn, [x]) for x in lst]


def _nyx_filter(fn, lst, interpreter):
    """filter() that works with both Python callables and NyxFunctions."""
    return [x for x in lst if interpreter._call(fn, [x])]


def setup_builtins(env: Environment, script_args: List[str] = None,
                   interpreter=None) -> None:
    """Populate an Environment with all Nyxel built-ins."""

    # output
    env.define("say",    _say)
    env.define("pretty", _pretty)       # readable JSON/dict output

    # http
    env.define("get",    _get)
    env.define("post",   _post)

    # file
    env.define("read",       _read)
    env.define("write",      _write)
    env.define("append",     _append)
    env.define("read_lines", _read_lines)
    env.define("lines_of",   _lines_of)
    env.define("words_of",   _words_of)
    env.define("save_json",  _save_json)   # ← new
    env.define("load_json",  _load_json)   # ← new

    # data helpers
    env.define("numbers_of", _numbers_of)  # extract numbers from text/list
    env.define("average_of", _average_of)  # mean of a list
    env.define("sum_of",     _sum_of)      # sum (readable alias)
    env.define("max_of",     _max_of)      # max (readable alias)
    env.define("min_of",     _min_of)      # min (readable alias)
    env.define("unique",     _unique)      # deduplicate
    env.define("flatten",    _flatten)     # flatten nested lists
    env.define("first_of",   _first_of)   # first item or none
    env.define("last_of",    _last_of)    # last item or none
    env.define("group_by",   _group_by)   # group objects by field

    # types
    env.define("len",       _len)
    env.define("type",      _type)
    env.define("str",       _str)
    env.define("int",       _int)
    env.define("float",     _float)
    env.define("bool",      bool)

    # beginner-friendly type aliases
    env.define("to_str",    _to_str)
    env.define("to_int",    _to_int)
    env.define("to_float",  _to_float)

    # check functions
    env.define("is_even",          _is_even)
    env.define("is_odd",           _is_odd)
    env.define("is_divisible_by",  _is_divisible_by)
    env.define("is_empty",         _is_empty)
    env.define("is_number",        _is_number)
    env.define("is_text",          _is_text)
    env.define("count_of",         _count_of)

    # math — use sum_of / max_of / min_of for lists (see data helpers above)
    # abs, round, floor, ceil, sqrt, pow are kept — they have no readable alias
    # and they operate on single numbers, not lists, so there's no confusion
    env.define("abs",    abs)
    env.define("round",  round)
    env.define("floor",  math.floor)
    env.define("ceil",   math.ceil)
    env.define("sqrt",   math.sqrt)
    env.define("pow",    pow)
    env.define("log",    math.log)
    env.define("pi",     math.pi)
    env.define("e",      math.e)
    env.define("inf",    math.inf)

    # random
    env.define("random",    _random.random)
    env.define("rand_int",  lambda a, b: _random.randint(int(a), int(b)))
    env.define("choice",    _random.choice)
    env.define("shuffle",   lambda lst: _random.sample(lst, len(lst)))

    # sequences
    env.define("range",     _range)
    env.define("sorted",    sorted)
    env.define("reversed",  lambda lst: list(reversed(lst)))

    # strings
    env.define("split",       lambda s, sep=None: s.split(sep) if sep else s.split())
    env.define("join",        lambda sep, lst: sep.join(_str(x) for x in lst))
    env.define("strip",       lambda s: s.strip())
    env.define("upper",       lambda s: s.upper())
    env.define("lower",       lambda s: s.lower())
    env.define("replace",     lambda s, a, b: s.replace(a, b))
    env.define("starts_with", lambda s, p: s.startswith(p))
    env.define("ends_with",   lambda s, p: s.endswith(s))
    env.define("contains",    lambda s, sub: sub in s)
    env.define("format",      lambda tmpl, *a: tmpl.format(*a))

    # json
    env.define("to_json",   lambda x: json.dumps(_unwrap(x), indent=2))
    env.define("from_json", lambda s: _wrap(json.loads(s)))

    # os / system
    env.define("env",        lambda k, d="": os.environ.get(k, d))
    env.define("run",        _run_command)
    env.define("run_lines",  _run_lines)   # ← new: run → list of lines
    env.define("exit",       sys.exit)
    env.define("args",       script_args or [])
    env.define("exists",     os.path.exists)
    env.define("ls",         lambda p=".": os.listdir(p))
    env.define("mkdir",      lambda p: os.makedirs(p, exist_ok=True) or True)
    env.define("cwd",        os.getcwd)
    env.define("sleep",      _time.sleep)
    env.define("time",       _time.time)

    # boolean / null as first-class values
    env.define("true",   True)
    env.define("false",  False)
    env.define("none",   None)

    # ── Arabic built-in aliases ───────────────────────────────────────────────
    # Every built-in function has an Arabic name so fully Arabic scripts
    # don't need to mix languages for function calls.

    # output
    env.define("قل",          _say)            # say
    env.define("اطبع",        _say)            # print (alternate)

    # http
    env.define("احضر",        _get)            # get
    env.define("أرسل",        _post)           # post

    # file
    env.define("اقرأ",        _read)           # read
    env.define("اكتب",        _write)          # write
    env.define("ألحق",        _append)         # append
    env.define("اقرأ_أسطر",   _read_lines)     # read_lines
    env.define("أسطر",        _lines_of)       # lines_of
    env.define("كلمات",       _words_of)       # words_of
    env.define("احفظ_json",   _save_json)      # save_json
    env.define("احمل_json",   _load_json)      # load_json

    # data
    env.define("أرقام",       _numbers_of)     # numbers_of
    env.define("متوسط",       _average_of)     # average_of
    env.define("مجموع",       _sum_of)         # sum_of
    env.define("أكبر",        _max_of)         # max_of
    env.define("أصغر",        _min_of)         # min_of
    env.define("فريد",        _unique)         # unique
    env.define("اجمع",        _flatten)        # flatten
    env.define("الأول",       _first_of)       # first_of
    env.define("الأخير",      _last_of)        # last_of
    env.define("جمع_حسب",     _group_by)       # group_by

    # types
    env.define("طول",         _len)            # len
    env.define("نوع",         _type)           # type
    env.define("نص",          _str)            # str
    env.define("إلى_نص",      _to_str)         # to_str
    env.define("إلى_عدد",     _to_int)         # to_int
    env.define("إلى_عشري",    _to_float)       # to_float

    # checks
    env.define("زوجي",        _is_even)        # is_even
    env.define("فردي",        _is_odd)         # is_odd
    env.define("يقبل_القسمة", _is_divisible_by) # is_divisible_by
    env.define("فارغ",        _is_empty)       # is_empty
    env.define("هو_رقم",      _is_number)      # is_number
    env.define("هو_نص",       _is_text)        # is_text
    env.define("عدد_تكرار",   _count_of)       # count_of

    # math
    env.define("قيمة_مطلقة",  abs)             # abs
    env.define("تقريب",       round)           # round
    env.define("جذر",         math.sqrt)       # sqrt
    env.define("أرضي",        math.floor)      # floor
    env.define("سقفي",        math.ceil)       # ceil

    # sequences
    env.define("مدى",         _range)          # range
    env.define("مرتب",        sorted)          # sorted
    env.define("معكوس",       lambda lst: list(reversed(lst)))  # reversed

    # strings
    env.define("ادمج",        lambda sep, lst: sep.join(_str(x) for x in lst))  # join
    env.define("قص",          lambda s: s.strip())     # strip
    env.define("كبير",        lambda s: s.upper())     # upper
    env.define("صغير",        lambda s: s.lower())     # lower
    env.define("استبدل",      lambda s, a, b: s.replace(a, b))  # replace

    # system
    env.define("بيئة",        lambda k, d="": os.environ.get(k, d))  # env
    env.define("نفذ",         _run_command)    # run
    env.define("موجود",       os.path.exists)  # exists

    # Arabic boolean/null literals
    env.define("صحيح",        True)            # true
    env.define("خطأ",         False)           # false
    env.define("لاشيء",       None)            # none

