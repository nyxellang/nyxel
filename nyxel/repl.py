"""
nyxel.repl — Interactive Read-Eval-Print loop.

Special REPL commands:  help  exit  quit  clear  vars
"""

from __future__ import annotations

from typing import List, Optional

from .version     import VERSION
from .errors      import NyxError
from .lexer       import lex
from .parser      import Parser
from .interpreter import Interpreter
from .builtins    import _display
from .nyx_ast import ExprStmt


BANNER = f"""\
  ╔═══════════════════════════════════════════╗
  ║ Nyxel {VERSION} - a simple scripting lang ║
  ╚═══════════════════════════════════════════╝

  Type  help  for commands,  exit  to quit.
   Results of expression are displayed automatically.
"""

REPL_HELP = """
  ┌─ Core syntax ───────────────────────────────────────────┐
  │  let x = 5              declare a variable              │
  │  x = x + 1              reassign                        │
  │  say("hello", x)        output (space-joined)           │
  │                                                         │
  │  when x > 3:            conditional                     │
  │      say("big")                                         │
  │  otherwise when x == 3:                                 │
  │      say("exact")                                       │
  │  otherwise:                                             │
  │      say("small")                                       │
  │                                                         │
  │  for item in list:      iterate over a collection       │
  │  repeat 5:              run 5 times                     │
  │  repeat 5 as i:         run 5 times, i = 0..4           │
  │  repeat i from 1 to 5:  i goes 1, 2, 3, 4, 5            │
  │  while cond:            conditional loop                │
  │                                                         │
  │  fn greet(name):        define a function               │
  │      return "Hi " + name                                │
  │                                                         │
  │  try: / catch e: / finally:   error handling            │
  │  struct Point: / x / y = 0   lightweight object         │
  │                                                         │
  │  list where condition   filter a list 'item' is current │
  └─────────────────────────────────────────────────────────┘

  ┌─ GUI ───────────────────────────────────────────────────┐
  │  create window("My App") size(800, 600):                │
  │      btn1 = btn("Click me") on_click(my_fn)             │
  │      btn2 = btn("Go") on_click(go) place(50, 100)       │
  │      lbl  = label("Hello World") place(10, 10)          │
  │      inp  = input("placeholder") place(10, 50)          │
  │                                                         │
  │  size(w, h) is optional — defaults to 800x600           │
  │  place(x, y) is optional — widgets pack vertically      │
  │  inp.value → read current text from an input field      │
  └─────────────────────────────────────────────────────────┘

  ┌─ Built-ins ─────────────────────────────────────────────────┐
  │  say(...)           get(url)     post(url, data)            │
  │  read(path)         write(path, text)    append(path, text) │
  │  read_lines(path)   lines_of(text)       words_of(text)     │
  │  is_even(n)  is_odd(n)  is_empty(x)  is_number(x)          │
  │  to_str(x)  to_int(x)  to_float(x)                         │
  │  len  type  str  int  float  range  sorted  sum  max  min  │
  │  join  upper  lower  strip  sqrt  abs  round  rand_int      │
  │  env  run  exists  to_json  from_json                       │
  └─────────────────────────────────────────────────────────────┘

  ┌─ Modules ───────────────────────────────────────────────┐
  │  bring math_utils               → math_utils.add(1,2)   │
  │  bring math_utils as m          → m.add(1, 2)           │
  │  bring add from math_utils      → add(1, 2)             │
  └─────────────────────────────────────────────────────────┘

  REPL commands:  help   vars   clear   exit
"""


_BLOCK_OPENERS = frozenset({
    "when", "otherwise", "fn",
    "if", "elif", "else", "def",
    "for", "while", "repeat",
    "try", "catch", "finally",
    "struct",
    "create",
})


def _opens_block(line: str) -> bool:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return False
    if not stripped.endswith(":"):
        return False
    first_word = stripped.rstrip(":").split()[0].lower() if stripped.rstrip(":") else ""
    if first_word == "for":
        return True
    return first_word in _BLOCK_OPENERS or stripped.endswith("python:")


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip())


def _block_depth(buf: List[str]) -> int:
    """
    Count unclosed block levels in the accumulated buffer by tracking an
    indent stack.  Each line ending with ':' that matches a block opener
    pushes a level; dedenting pops it.
    """
    stack: List[int] = []
    for line in buf:
        if not line.strip() or line.strip().startswith("#"):
            continue
        ind = _indent_of(line)
        while stack and ind <= stack[-1]:
            stack.pop()
        if _opens_block(line):
            stack.append(ind)
    return len(stack)


def _show_result(value) -> None:
    if value is None:
        return
    print(f"   =  {_display(value)}")


def _run(interp: Interpreter, source: str) -> None:
    try:
        toks  = lex(source)
        stmts = Parser(toks).parse()
        if not stmts:
            return
        result = interp.run_repl(stmts)
        _show_result(result)
    except NyxError as e:
        print(e)
    except SystemExit:
        raise
    except Exception as e:
        print(f"\n  InternalError\n  {'─'*40}\n  {e}\n")


def _show_vars(interp: Interpreter) -> None:
    from .runtime import NyxFunction, NyxStruct
    from .builtins import setup_builtins

    class _QuickEnv:
        def __init__(self): self._names = set()
        def define(self, k, v): self._names.add(k)
    qe = _QuickEnv()
    setup_builtins(qe)
    builtin_names = qe._names

    user = {k: v for k, v in interp.globals._v.items() if k not in builtin_names}

    if not user:
        print("  (no variables defined yet)")
        return

    print()
    for name, val in sorted(user.items()):
        if isinstance(val, NyxFunction):
            sig = ", ".join(
                p.name if p.default is None else f"{p.name} = ..."
                for p in val.params
            )
            print(f"  {name}({sig})  →  fn")
        elif isinstance(val, NyxStruct):
            print(f"  {name}  →  struct")
        else:
            print(f"  {name}  =  {_display(val)}")
    print()


def run_repl() -> None:
    print(BANNER)

    try:
        import readline
        readline.parse_and_bind("tab: complete")
    except ImportError:
        pass

    interp          = Interpreter()
    buf: List[str]  = []
    in_block        = False

    while True:
        try:
            depth  = _block_depth(buf) if in_block else 0
            if in_block:
                prompt = f"  [{depth}] ...  " if depth > 1 else "   ...   "
            else:
                prompt = "   >>>   "
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print("\n  Goodbye!"); break

        low = line.strip().lower()

        if not in_block:
            if low in ("exit", "quit"):
                print("  Goodbye!"); break
            if low == "help":
                print(REPL_HELP); continue
            if low == "clear":
                print("\033[2J\033[H", end=""); continue
            if low == "vars":
                _show_vars(interp); continue

        if _opens_block(line):
            buf.append(line)
            in_block = True
            continue

        if in_block:
            if line.strip() == "":
                if _block_depth(buf) > 1:
                    buf.append(line)
                    continue
                source   = "\n".join(buf)
                buf      = []
                in_block = False
                _run(interp, source)
            else:
                buf.append(line)
            continue

        if not line.strip():
            continue
        _run(interp, line)
