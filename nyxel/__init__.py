"""
Nyxel — public API

    from nyxel import run_source, run_file, Interpreter

    run_source('say("hello")')
"""

from .version     import VERSION
from .errors      import NyxError, name_error_hint, suggest_callable
from .lexer       import lex
from .parser      import Parser
from .compiler    import transpile
from ._run        import __nyx_runtime
from .cli         import main


def run_source(source: str, filename: str = "<input>", script_args=None) -> None:
    tokens = lex(source, filename)
    parser = Parser(tokens)
    stmts  = parser.parse()
    py_source = transpile(stmts, filename)
    g = __nyx_runtime(script_args or [])
    try:
        exec(compile(py_source, filename, "exec"), g)
    except NyxError:
        raise
    except ZeroDivisionError:
        raise NyxError("MathError", "Division by zero",
                       hint="Make sure the divisor is not zero")
    except NameError as __e:
        hint = name_error_hint(getattr(__e, "name", str(__e)), list(g.keys()))
        raise NyxError("NameError", f"'{__e.name}' doesn't exist yet", hint=hint)
    except TypeError as __e:
        msg = str(__e)
        hint = ""
        if "unsupported operand type" in msg:
            hint = "Make sure both operands are numbers for this operation"
            if "'str'" in msg:
                hint = "Convert the number first:  str(the_number) + the_text"
        elif "can only concatenate str" in msg:
            hint = "Convert the number first:  str(the_number) + the_text"
        raise NyxError("TypeError", msg, hint=hint)
    except IndexError as __e:
        raise NyxError("IndexError", str(__e),
                       hint="Check that the index is within the list's length")
    except AttributeError as __e:
        msg = str(__e)
        hint = ""
        if "has no attribute '" in msg:
            attr = msg.split("has no attribute '")[1].split("'")[0]
            hint = suggest_callable(attr, list(g.keys()))
        raise NyxError("AttributeError", msg, hint=hint)
    except SyntaxError as __e:
        msg = str(__e)
        hint = ""
        if "import" in msg.lower():
            hint = "In Nyxel, use 'bring' instead of 'import'"
        raise NyxError("SyntaxError", msg, hint=hint)
    except Exception as __e:
        raise NyxError("RuntimeError", str(__e))


def run_file(path: str, *, check_only: bool = False, script_args=None) -> None:
    from .cli import _run_file
    _run_file(path, check_only=check_only, script_args=script_args)


__all__ = [
    "VERSION", "NyxError", "lex", "Parser",
    "run_source", "run_file", "main",
]
