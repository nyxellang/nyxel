"""
Nyxel

Public API:

    from nyxel import run_source, run_file, Interpreter

    run_source('say("hello")')

    interp = Interpreter()
    interp.run(stmts)
"""

from .version     import VERSION
from .errors      import NyxError
from .lexer       import lex
from .parser      import Parser
from .interpreter import Interpreter
from .cli         import main


def run_source(
    source: str,
    filename: str = "<input>",
    script_args=None,
) -> None:
    """Lex, parse, and execute a string of Nyxel source code."""
    tokens = lex(source, filename)
    stmts  = Parser(tokens).parse()
    Interpreter(script_args).run(stmts)


def run_file(path: str, *, check_only: bool = False, script_args=None) -> None:
    """Read a .nx file from disk and execute it (or just check syntax)."""
    from .cli import _run_file
    _run_file(path, check_only=check_only, script_args=script_args)


__all__ = [
    "VERSION",
    "NyxError",
    "lex",
    "Parser",
    "Interpreter",
    "run_source",
    "run_file",
    "main",
]
