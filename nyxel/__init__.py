"""
Nyxel — public API

    from nyxel import run_source, run_file, Interpreter

    run_source('say("hello")')
"""

from .version     import VERSION
from .errors      import NyxError
from .lexer       import lex
from .parser      import Parser
from .interpreter import Interpreter
from .cli         import main


def run_source(source: str, filename: str = "<input>", script_args=None) -> None:
    tokens = lex(source, filename)
    stmts  = Parser(tokens).parse()
    Interpreter(script_args).run(stmts)


def run_file(path: str, *, check_only: bool = False, script_args=None) -> None:
    from .cli import _run_file
    _run_file(path, check_only=check_only, script_args=script_args)


__all__ = [
    "VERSION", "NyxError", "lex", "Parser", "Interpreter",
    "run_source", "run_file", "main",
]
