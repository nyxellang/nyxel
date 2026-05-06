"""
nyxel.cli
─────────
Command-line interface for the  nyx  tool.

Commands
────────
  nyx run   <file.nx>  [args…]   execute a script
  nyx repl                        start the interactive REPL
  nyx check <file.nx>             syntax-check without running
  nyx version                     print the version
  nyx help                        show usage
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List

from .version import VERSION
from .errors import NyxError
from .lexer import lex
from .parser import Parser
from .interpreter import Interpreter
from .repl import run_repl


# ── usage text ────────────────────────────────────────────────────────────────

USAGE = f"""\

  Nyxel {VERSION}  ─  a lightweight, expressive scripting language

  Usage
  ─────
    nyx run   <file.nx>  [args…]   run a script
    nyx repl                        interactive REPL
    nyx check <file.nx>             syntax check (no execution)
    nyx version                     show version
    nyx help                        show this message

  Examples
  ────────
    nyx run main.nx
    nyx run fetch_data.nx --verbose
    nyx check script.nx
    nyx repl
"""


# ── helpers ───────────────────────────────────────────────────────────────────

def _run_file(
    path: str,
    *,
    check_only: bool = False,
    script_args: List[str] = None,
) -> None:
    try:
        source = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"  ✗  File not found: {path}")
        sys.exit(1)
    except Exception as e:
        print(f"  ✗  Cannot read '{path}': {e}")
        sys.exit(1)

    try:
        tokens = lex(source, path)
        stmts  = Parser(tokens).parse()
    except NyxError as e:
        print(e)
        sys.exit(1)

    if check_only:
        print(f"  ✓  {path}  —  syntax OK")
        return

    try:
        Interpreter(script_args).run(stmts)
    except NyxError as e:
        print(e)
        sys.exit(1)
    except SystemExit:
        raise
    except Exception as e:
        print(f"  ✗  Unexpected runtime error: {e}")
        sys.exit(1)


# ── entry point ───────────────────────────────────────────────────────────────

def main(argv: List[str] = None) -> None:
    if argv is None:
        argv = sys.argv[1:]

    if not argv or argv[0] in ("help", "--help", "-h"):
        print(USAGE)
        return

    cmd = argv[0]

    if cmd in ("version", "--version", "-v"):
        print(f"Nyxel {VERSION}")
        return

    if cmd == "repl":
        run_repl()
        return

    if cmd == "run":
        if len(argv) < 2:
            print("  ✗  Usage: nyx run <file.nx>")
            sys.exit(1)
        _run_file(argv[1], script_args=argv[2:])
        return

    if cmd == "check":
        if len(argv) < 2:
            print("  ✗  Usage: nyx check <file.nx>")
            sys.exit(1)
        _run_file(argv[1], check_only=True)
        return

    # Bare filename shortcut:  nyx script.nx
    if Path(cmd).exists():
        _run_file(cmd, script_args=argv[1:])
        return

    print(f"  ✗  Unknown command: '{cmd}'")
    print(f"     Run  nyx help  for usage.")
    sys.exit(1)
