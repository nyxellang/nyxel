"""
nyxel.repl
──────────
Interactive Read-Eval-Print loop for Nyxel.

• Special REPL commands:  help  exit  quit  clear  vars
"""

from __future__ import annotations

from typing import List, Optional

from .version     import VERSION
from .errors      import NyxError
from .lexer       import lex
from .parser      import Parser
from .interpreter import Interpreter
from .builtins    import _display
from .ast         import ExprStmt


# ── display strings ───────────────────────────────────────────────────────────

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
  │      numbers where is_even(item)                        │
  │      users where item.age >= 18                         │
  │      words where item.length > 4                        │
  └─────────────────────────────────────────────────────────┘

  ┌─ Built-ins ─────────────────────────────────────────────────┐
  │  say(...)           get(url)     post(url, data)            │
  │  read(path)         write(path, text)    append(path, text) │
  │  read_lines(path)   → list of lines (no split needed)       │
  │  lines_of(text)     → list of lines from text               │
  │  words_of(text)     → list of words from text               │
  │                                                             │
  │  is_even(n)         is_odd(n)    is_divisible_by(n, d)      │
  │  is_empty(x)        is_number(x) is_text(x)                 │
  │  to_str(x)          to_int(x)    to_float(x)                │
  │  count_of(lst, val) → count occurrences                     │
  │                                                             │
  │  len(x)  type(x)  str(x)  int(x)  float(x)                  │
  │  range(n)  sorted(lst)  sum(lst)  max(lst)  min(lst)        │
  │  join(sep, lst)  upper(s)  lower(s)  strip(s)               │
  │  sqrt(n)  abs(n)  round(n)  rand_int(a, b)  choice(lst)     │
  │  env(key)  run(cmd)  exists(path)  to_json(x)  from_json(s) │
  └─────────────────────────────────────────────────────────────┘

  ┌─ Modules ───────────────────────────────────────────────┐
  │  bring math_utils               → math_utils.add(1,2)   │
  │  bring math_utils as m          → m.add(1, 2)           │
  │  bring add from math_utils      → add(1, 2)             │
  └─────────────────────────────────────────────────────────┘

  REPL commands:  help   vars   clear   exit
"""


# ── block-opener detection ────────────────────────────────────────────────────
#
# DESIGN NOTE: This is intentionally heuristic-based, not parser-based.
#
# A parser-based approach would be more correct but requires a full parse
# Attempts on every keystroke, which expensive and complicated error display.
# The heuristic (line ends with ’:’. First word is a block keyword) is right
# For all current Nyxel syntax and will be as long as the language
# Stays block-structured.
# Otherwise: is what we call a higher special case: will terminate with:for alone by the:
# Colon on the same token, but otherwise when x > 3: has “otherwise” as
 #Is captured correctly in either of the first words. Both are separated correctly by the set of keywords.

_BLOCK_OPENERS = frozenset({
    # Nyxel style (primary)
    "when", "otherwise", "fn",
    # Classic aliases
    "if", "elif", "else", "def",
    # Loops
    "for", "while", "repeat",
    # Error handling
    "try", "catch", "finally",
    # Struct
    "struct",
})


def _opens_block(line: str) -> bool:
    """
    Return True if this line begins a new indented block.

    Heuristic: line ends with ":", and its first word is a known block opener.
    See the design note above for limitations and upgrade path.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return False
    if not stripped.endswith(":"):
        return False
    # Strip the trailing colon before splitting so "try:" gives "try" not "try:"
    first_word = stripped.rstrip(":").split()[0].lower() if stripped.rstrip(":") else ""
    # 'for each' is two words — handle it specially
    if first_word == "for":
        return True
    return first_word in _BLOCK_OPENERS or stripped.endswith("python:")


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip())


def _block_depth(buf: List[str]) -> int:
    """
    For unclosed block levels in the accumulated buffer, count.
    Algorithm: track the indent stack. For each line that opens a block ( ’...‘ends
    With ’:’) creates a new level of indentation. extends the indentation of every line with indent,...,until its indentation is one level deeper:
    Each occur on the stack will pop that level first. The stack depth is that answer.
    """
    stack: List[int] = []
    for line in buf:
        if not line.strip() or line.strip().startswith("#"):
            continue
        ind = _indent_of(line)
        # Pop closed levels
        while stack and ind <= stack[-1]:
            stack.pop()
        # Push if this line opens a block
        if _opens_block(line):
            stack.append(ind)
    return len(stack)


# ── result display ────────────────────────────────────────────────────────────

def _show_result(value) -> None:
    """Print an expression result in the REPL style."""
    if value is None:
        return                      # don't print None for side-effect calls
    print(f"   =  {_display(value)}")


# ── run helpers ───────────────────────────────────────────────────────────────

def _run(interp: Interpreter, source: str) -> None:
    """
    Parse and run a source snippet.

    If the last statement is a bare expression, display its result.
    Errors are printed cleanly with no Python traceback.
    """
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
        # Unexpected Python-level error — show cleanly without traceback
        print(f"\n  InternalError\n  {'─'*40}\n  {e}\n")


def _show_vars(interp: Interpreter) -> None:
    """Print all user-defined variables in the current session."""
    from .runtime import NyxFunction, NyxStruct

    # Collect built-in names by running setup_builtins against a dummy env
    from .builtins import setup_builtins
    class _QuickEnv:
        def __init__(self): self._names = set()
        def define(self, k, v): self._names.add(k)
    qe = _QuickEnv()
    setup_builtins(qe)
    builtin_names = qe._names

    user = {k: v for k, v in interp.globals._v.items()
            if k not in builtin_names}

    if not user:
        print("  (no variables defined yet)")
        return

    print()
    for name, val in sorted(user.items()):
        if isinstance(val, NyxFunction):
            # Param is a namedtuple — use .name attribute
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


# ── main REPL loop ────────────────────────────────────────────────────────────

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

        # ── REPL commands (only when not accumulating a block) ─────────────
        if not in_block:
            if low in ("exit", "quit"):
                print("  Goodbye!"); break
            if low == "help":
                print(REPL_HELP); continue
            if low == "clear":
                print("\033[2J\033[H", end=""); continue
            if low == "vars":
                _show_vars(interp); continue

        # ── block accumulation ─────────────────────────────────────────────
        if _opens_block(line):
            buf.append(line)
            in_block = True
            continue

        if in_block:
            if line.strip() == "":
                # Blank line inside nested block → keep accumulating
                if _block_depth(buf) > 1:
                    buf.append(line)
                    continue
                # Blank line at depth 1 → submit the block
                source  = "\n".join(buf)
                buf     = []
                in_block = False
                _run(interp, source)
            else:
                buf.append(line)
            continue

        # ── single-line statement ──────────────────────────────────────────
        if not line.strip():
            continue
        _run(interp, line)
