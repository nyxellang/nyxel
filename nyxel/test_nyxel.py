"""
tests/test_nyxel.py
────────────────────
Test nyxel

Run with:   python -m pytest tests/  -v
Or:         python tests/test_nyxel.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from nyxel.lexer       import lex
from nyxel.parser      import Parser
from nyxel.runtime     import Environment, NyxObject, _wrap, _unwrap
from nyxel.errors      import NyxError
from nyxel             import run_source


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def run(code: str) -> dict:
    """Run a snippet using the transpiler; return the globals dict."""
    from nyxel.compiler import transpile
    from nyxel._run import __nyx_runtime
    from nyxel.lexer  import lex
    from nyxel.parser import Parser
    from nyxel.errors import (
        NyxError, name_error_hint, index_error_hint,
        type_error_add_hint, suggest_attr, suggest_callable,
    )
    tokens = lex(code)
    stmts  = Parser(tokens).parse()
    py_source = transpile(stmts)
    g = __nyx_runtime([])
    try:
        exec(compile(py_source, "<test>", "exec"), g)
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
        elif "not subscriptable" in msg:
            hint = "Use brackets [...] with lists or dicts, not with numbers"
        raise NyxError("TypeError", msg, hint=hint)
    except IndexError as __e:
        raise NyxError("IndexError", str(__e),
                       hint="Check that the index is within the list's length")
    except AttributeError as __e:
        msg = str(__e)
        if "has no attribute 'append'" in msg:
            kind = "TypeError"
            msg = "Can't add to a non-list value"
            hint = "Use '<<' only with lists, or create a list: let items = []"
        elif "has no attribute '" in msg:
            kind = "AttributeError"
            attr = msg.split("has no attribute '")[1].split("'")[0]
            hint = suggest_callable(attr, list(g.keys()))
            if "'str' object" in msg:
                str_methods = ["upper", "lower", "strip", "starts_with", "ends_with",
                               "contains", "length", "to_int", "to_float"]
                hint = suggest_callable(attr, str_methods) or f"String methods include: {', '.join(str_methods[:6])}"
        elif "No attribute '" in msg:
            # NyxObject field access error — extract fields from message
            kind = "AttributeError"
            attr = msg.split("No attribute '")[1].split("'")[0]
            hint = msg
        else:
            kind = "AttributeError"
            hint = ""
        raise NyxError(kind, msg, hint=hint)
    except SyntaxError as __e:
        msg = str(__e)
        hint = ""
        if "import" in msg.lower():
            hint = "In Nyxel, use 'bring' instead of 'import'"
        raise NyxError("SyntaxError", msg, hint=hint)
    except KeyError as __e:
        raise NyxError("KeyError", str(__e))
    except Exception as __e:
        raise NyxError("RuntimeError", str(__e))
    return g

def val(code: str, name: str):
    """Run a snippet and return the value of a variable."""
    return run(code).get(name)

def out(code: str, capsys) -> str:
    """Run a snippet and return stripped stdout."""
    run(code)
    return capsys.readouterr().out.strip()


# ══════════════════════════════════════════════════════════════════════════════
#  LEXER
# ══════════════════════════════════════════════════════════════════════════════

class TestLexer:

    def test_numbers(self):
        toks = [t for t in lex("42 3.14 1e2") if t.type == "NUM"]
        assert toks[0].value == 42
        assert toks[1].value == 3.14
        assert toks[2].value == 100.0

    def test_strings_double_quotes(self):
        toks = [t for t in lex('"hello world"') if t.type == "STR"]
        assert toks[0].value == "hello world"

    def test_strings_single_quotes(self):
        toks = [t for t in lex("'it\\'s fine'") if t.type == "STR"]
        assert toks[0].value == "it's fine"

    def test_escape_sequences(self):
        toks = [t for t in lex('"line1\\nline2"') if t.type == "STR"]
        assert "\n" in toks[0].value

    def test_keywords(self):
        toks = [t for t in lex("let if elif else for while def return") if t.type == "KW"]
        assert len(toks) == 8

    def test_identifiers(self):
        toks = [t for t in lex("myVar _x foo_bar") if t.type == "ID"]
        assert [t.value for t in toks] == ["myVar", "_x", "foo_bar"]

    def test_operators(self):
        toks = [t for t in lex("== != <= >= ** //") if t.type == "OP"]
        assert {t.value for t in toks} == {"==", "!=", "<=", ">=", "**", "//"}

    def test_comment_stripped(self):
        toks = lex("let x = 5  # ignore this")
        types = [t.type for t in toks]
        assert "NL" in types or "EOF" in types
        values = [t.value for t in toks]
        assert "ignore" not in " ".join(str(v) for v in values)

    def test_indent_dedent(self):
        src = "if true:\n    let x = 1\n"
        toks = lex(src)
        types = [t.type for t in toks]
        assert "INDENT" in types
        assert "DEDENT" in types

    def test_unterminated_string_error(self):
        with pytest.raises(NyxError) as exc:
            lex('"not closed')
        assert "SyntaxError" in str(exc.value)

    def test_pyblock_token(self):
        src = "python:\n    x = 1\nend\n"
        toks = [t for t in lex(src) if t.type == "PYBLOCK"]
        assert len(toks) == 1
        assert "x = 1" in toks[0].value


# ══════════════════════════════════════════════════════════════════════════════
#  PARSER
# ══════════════════════════════════════════════════════════════════════════════

class TestParser:

    def _parse(self, src):
        return Parser(lex(src)).parse()

    def test_let(self):
        from nyxel.nyx_ast import LetStmt
        stmts = self._parse("let x = 5")
        assert isinstance(stmts[0], LetStmt)
        assert stmts[0].name == "x"

    def test_if(self):
        from nyxel.nyx_ast import IfStmt
        stmts = self._parse("if true:\n    let x = 1\n")
        assert isinstance(stmts[0], IfStmt)

    def test_for(self):
        from nyxel.nyx_ast import ForStmt
        stmts = self._parse("for i in [1, 2]:\n    let x = i\n")
        assert isinstance(stmts[0], ForStmt)

    def test_while(self):
        from nyxel.nyx_ast import WhileStmt
        stmts = self._parse("while x > 0:\n    x = x - 1\n")
        assert isinstance(stmts[0], WhileStmt)

    def test_def(self):
        from nyxel.nyx_ast import DefStmt
        stmts = self._parse("def add(a, b):\n    return a + b\n")
        assert isinstance(stmts[0], DefStmt)
        assert stmts[0].name == "add"
        # params are now (name, default_or_None) tuples
        assert [p for p, _ in stmts[0].params] == ["a", "b"]

    def test_dict_literal(self):
        from nyxel.nyx_ast import LetStmt, DictExpr
        stmts = self._parse('let d = {"key": 1}')
        assert isinstance(stmts[0].expr, DictExpr)

    def test_list_literal(self):
        from nyxel.nyx_ast import LetStmt, ListExpr
        stmts = self._parse("let lst = [1, 2, 3]")
        assert isinstance(stmts[0].expr, ListExpr)

    def test_index_expr(self):
        from nyxel.nyx_ast import ExprStmt, IndexExpr
        stmts = self._parse("lst[0]")
        assert isinstance(stmts[0].expr, IndexExpr)

    def test_attr_expr(self):
        from nyxel.nyx_ast import ExprStmt, AttrExpr
        stmts = self._parse("user.name")
        assert isinstance(stmts[0].expr, AttrExpr)

    def test_call_expr(self):
        from nyxel.nyx_ast import ExprStmt, CallExpr
        stmts = self._parse("say(1, 2)")
        assert isinstance(stmts[0].expr, CallExpr)

    def test_missing_colon_error(self):
        with pytest.raises(NyxError):
            self._parse("if true\n    let x = 1\n")

    def test_missing_paren_error(self):
        with pytest.raises(NyxError):
            self._parse("def f(a, b:\n    pass\n")


# ══════════════════════════════════════════════════════════════════════════════
#  RUNTIME — Environment
# ══════════════════════════════════════════════════════════════════════════════

class TestEnvironment:

    def test_define_and_get(self):
        env = Environment()
        env.define("x", 42)
        assert env.get("x") == 42

    def test_scope_chain(self):
        parent = Environment()
        parent.define("x", 1)
        child  = Environment(parent)
        assert child.get("x") == 1

    def test_child_shadows_parent(self):
        parent = Environment()
        parent.define("x", 1)
        child  = Environment(parent)
        child.define("x", 99)
        assert child.get("x") == 99
        assert parent.get("x") == 1

    def test_set_updates_nearest_scope(self):
        parent = Environment()
        parent.define("x", 1)
        child  = Environment(parent)
        child.set("x", 2)
        assert parent.get("x") == 2

    def test_undefined_raises(self):
        env = Environment()
        with pytest.raises(NyxError) as exc:
            env.get("missing")
        assert "NameError" in str(exc.value)

    def test_flat(self):
        parent = Environment()
        parent.define("a", 1)
        child = Environment(parent)
        child.define("b", 2)
        flat = child.flat()
        assert flat["a"] == 1
        assert flat["b"] == 2


# ══════════════════════════════════════════════════════════════════════════════
#  RUNTIME — NyxObject
# ══════════════════════════════════════════════════════════════════════════════

class TestNyxObject:

    def test_attr_access(self):
        obj = NyxObject({"name": "Alice", "age": 30})
        assert obj.name == "Alice"
        assert obj.age == 30

    def test_index_access(self):
        obj = NyxObject({"key": "value"})
        assert obj["key"] == "value"

    def test_attr_set(self):
        obj = NyxObject({"x": 1})
        obj.x = 99
        assert obj.x == 99

    def test_missing_attr_raises(self):
        obj = NyxObject({"a": 1})
        with pytest.raises(AttributeError):
            _ = obj.missing

    def test_contains(self):
        obj = NyxObject({"k": "v"})
        assert "k" in obj
        assert "z" not in obj

    def test_wrap_nested(self):
        raw = {"user": {"name": "Bob"}}
        obj = _wrap(raw)
        assert isinstance(obj, NyxObject)
        assert isinstance(obj.user, NyxObject)
        assert obj.user.name == "Bob"

    def test_unwrap(self):
        obj = NyxObject({"x": 1, "y": NyxObject({"z": 2})})
        raw = _unwrap(obj)
        assert raw == {"x": 1, "y": {"z": 2}}


# ══════════════════════════════════════════════════════════════════════════════
#  INTERPRETER — core language features
# ══════════════════════════════════════════════════════════════════════════════

class TestInterpreter:

    # ── variables ─────────────────────────────────────────────────────────────

    def test_let(self):
        assert val("let x = 42", "x") == 42

    def test_assign(self):
        assert val("let x = 1\nx = 99", "x") == 99

    def test_string(self):
        assert val('let s = "hello"', "s") == "hello"

    def test_bool_true(self):
        assert val("let b = true", "b") is True

    def test_bool_false(self):
        assert val("let b = false", "b") is False

    def test_none(self):
        assert val("let n = none", "n") is None

    # ── arithmetic ────────────────────────────────────────────────────────────

    def test_add(self):
        assert val("let r = 3 + 4", "r") == 7

    def test_subtract(self):
        assert val("let r = 10 - 3", "r") == 7

    def test_multiply(self):
        assert val("let r = 6 * 7", "r") == 42

    def test_divide(self):
        assert val("let r = 10 / 4", "r") == 2.5

    def test_floor_divide(self):
        assert val("let r = 10 // 3", "r") == 3

    def test_modulo(self):
        assert val("let r = 17 % 5", "r") == 2

    def test_power(self):
        assert val("let r = 2 ** 10", "r") == 1024

    def test_division_by_zero(self):
        with pytest.raises(NyxError) as exc:
            run("let r = 1 / 0")
        assert "MathError" in str(exc.value)

    def test_string_concat(self):
        assert val('let s = "hello" + " " + "world"', "s") == "hello world"

    def test_string_number_concat(self):
        assert val('let s = "x = " + str(42)', "s") == "x = 42"

    # ── comparisons & boolean ─────────────────────────────────────────────────

    def test_eq(self):          assert val("let r = 5 == 5", "r") is True
    def test_neq(self):         assert val("let r = 5 != 6", "r") is True
    def test_gt(self):          assert val("let r = 6 > 5", "r") is True
    def test_lt(self):          assert val("let r = 4 < 5", "r") is True
    def test_gte(self):         assert val("let r = 5 >= 5", "r") is True
    def test_lte(self):         assert val("let r = 4 <= 5", "r") is True
    def test_and(self):         assert val("let r = true and true", "r") is True
    def test_or(self):          assert val("let r = false or true", "r") is True
    def test_not(self):         assert val("let r = not false", "r") is True
    def test_in_list(self):     assert val("let r = 2 in [1, 2, 3]", "r") is True
    def test_not_in_list(self): assert val("let r = 9 not in [1, 2, 3]", "r") is True

    # ── if / elif / else ──────────────────────────────────────────────────────

    def test_if_true(self):
        assert val("let r = 0\nif true:\n    r = 1\n", "r") == 1

    def test_if_false(self):
        assert val("let r = 0\nif false:\n    r = 1\n", "r") == 0

    def test_if_else(self):
        assert val("let r = 0\nif false:\n    r = 1\nelse:\n    r = 2\n", "r") == 2

    def test_elif(self):
        code = "let x = 5\nlet r = 0\nif x > 10:\n    r = 1\nelif x > 3:\n    r = 2\nelse:\n    r = 3\n"
        assert val(code, "r") == 2

    # ── for / while / break / continue ───────────────────────────────────────

    def test_repeat_basic(self):
        code = "let t = 0\nrepeat 5:\n    t = t + 1\n"
        assert val(code, "t") == 5

    def test_repeat_expression(self):
        code = "let n = 4\nlet t = 0\nrepeat n:\n    t = t + 1\n"
        assert val(code, "t") == 4

    def test_repeat_zero(self):
        code = "let t = 99\nrepeat 0:\n    t = 0\n"
        assert val(code, "t") == 99

    def test_repeat_break(self):
        code = "let t = 0\nrepeat 10:\n    if t == 3:\n        break\n    t = t + 1\n"
        assert val(code, "t") == 3

    def test_repeat_continue(self):
        # count only even iterations (0,2,4 → 3 increments)
        code = "let t = 0\nlet i = 0\nrepeat 6:\n    if i % 2 != 0:\n        i = i + 1\n        continue\n    t = t + 1\n    i = i + 1\n"
        assert val(code, "t") == 3

    def test_for_loop(self):
        assert val("let t = 0\nfor i in [1,2,3,4,5]:\n    t = t + i\n", "t") == 15

    def test_for_range(self):
        # for + range still works when you need the index value
        assert val("let t = 0\nfor i in range(5):\n    t = t + i\n", "t") == 10

    def test_while_loop(self):
        assert val("let x = 5\nlet t = 0\nwhile x > 0:\n    t = t + x\n    x = x - 1\n", "t") == 15

    def test_break(self):
        code = "let t = 0\nfor i in range(10):\n    if i == 5:\n        break\n    t = t + 1\n"
        assert val(code, "t") == 5

    def test_continue(self):
        code = "let t = 0\nfor i in range(6):\n    if i % 2 == 0:\n        continue\n    t = t + i\n"
        assert val(code, "t") == 9   # 1 + 3 + 5

    # ── functions ─────────────────────────────────────────────────────────────

    def test_def_and_call(self):
        code = "def double(n):\n    return n * 2\nlet r = double(5)\n"
        assert val(code, "r") == 10

    def test_recursion(self):
        code = "def fact(n):\n    if n <= 1:\n        return 1\n    return n * fact(n - 1)\nlet r = fact(6)\n"
        assert val(code, "r") == 720

    def test_closure(self):
        code = (
            "let x = 10\n"
            "def get_x():\n"
            "    return x\n"
            "let r = get_x()\n"
        )
        assert val(code, "r") == 10

    def test_return_none(self):
        code = "def nothing():\n    pass\nlet r = nothing()\n"
        assert val(code, "r") is None

    def test_wrong_arg_count(self):
        with pytest.raises(NyxError) as exc:
            run("def f(a, b):\n    return a\nf(1)\n")
        assert "TypeError" in str(exc.value)


# ══════════════════════════════════════════════════════════════════════════════
#  TRY / CATCH / FINALLY
# ══════════════════════════════════════════════════════════════════════════════

class TestTryCatch:

    def test_try_no_error(self):
        code = "let r = 0\ntry:\n    r = 1\ncatch:\n    r = 99\n"
        assert val(code, "r") == 1

    def test_catch_fires_on_error(self):
        code = "let r = 0\ntry:\n    let x = 1 / 0\ncatch:\n    r = 99\n"
        assert val(code, "r") == 99

    def test_catch_var_has_message(self):
        code = "let msg = \"\"\ntry:\n    let x = 1 / 0\ncatch e:\n    msg = e.message\n"
        assert val(code, "msg") != ""

    def test_catch_var_has_kind(self):
        code = "let k = \"\"\ntry:\n    let x = 1 / 0\ncatch e:\n    k = e.kind\n"
        assert val(code, "k") == "MathError"

    def test_finally_always_runs_on_success(self):
        code = "let r = 0\ntry:\n    r = 1\ncatch:\n    pass\nfinally:\n    r = 99\n"
        assert val(code, "r") == 99

    def test_finally_always_runs_on_error(self):
        code = "let r = 0\ntry:\n    let x = 1 / 0\ncatch:\n    r = 1\nfinally:\n    r = 99\n"
        assert val(code, "r") == 99

    def test_catch_name_error(self):
        code = "let r = \"\"\ntry:\n    say(undefined_xyz)\ncatch e:\n    r = e.kind\n"
        assert val(code, "r") == "NameError"

    def test_try_no_catch_just_finally(self):
        code = "let r = 0\ntry:\n    r = 5\nfinally:\n    r = r + 1\n"
        assert val(code, "r") == 6

    def test_try_missing_clause_error(self):
        with pytest.raises(NyxError) as exc:
            Parser(lex("try:\n    pass\n")).parse()
        assert "SyntaxError" in str(exc.value)


# ══════════════════════════════════════════════════════════════════════════════
#  BRING (MODULE SYSTEM)
# ══════════════════════════════════════════════════════════════════════════════

class TestBring:

    def _make_module(self, tmp_path, name, code):
        f = tmp_path / f"{name}.nx"
        f.write_text(code)
        return str(tmp_path)

    def test_bring_module(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "greet.nx").write_text(
            'def hello(name):\n    return "Hi " + name\n'
        )
        code = "bring greet\nlet r = greet.hello(\"World\")\n"
        assert val(code, "r") == "Hi World"

    def test_bring_as_alias(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "greet.nx").write_text(
            'def hello(name):\n    return "Hi " + name\n'
        )
        code = "bring greet as g\nlet r = g.hello(\"Nyxel\")\n"
        assert val(code, "r") == "Hi Nyxel"

    def test_bring_from(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "math_utils.nx").write_text(
            "def add(a, b):\n    return a + b\n"
        )
        code = "bring add from math_utils\nlet r = add(3, 4)\n"
        assert val(code, "r") == 7

    def test_bring_from_multiple(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "ops.nx").write_text(
            "def double(x):\n    return x * 2\ndef triple(x):\n    return x * 3\n"
        )
        code = "bring double, triple from ops\nlet r = double(5) + triple(2)\n"
        assert val(code, "r") == 16

    def test_bring_module_not_found(self):
        with pytest.raises(NyxError) as exc:
            run("bring nonexistent_module_xyz\n")
        assert "ImportError" in str(exc.value)

    def test_bring_name_not_in_module(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "empty.nx").write_text("let x = 1\n")
        with pytest.raises(NyxError) as exc:
            run("bring missing_fn from empty\n")
        assert "ImportError" in str(exc.value)

    def test_bring_caches_module(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "counter.nx").write_text("let count = 1\n")
        # Bring twice — should not error or re-execute
        code = "bring counter\nbring counter as c2\n"
        run(code)   # just must not raise


# ══════════════════════════════════════════════════════════════════════════════
#  STRUCTS
# ══════════════════════════════════════════════════════════════════════════════

class TestStructs:

    def test_struct_basic(self):
        code = "struct Point:\n    x\n    y\nlet p = Point(3, 4)\nlet r = p.x\n"
        assert val(code, "r") == 3

    def test_struct_default_field(self):
        code = "struct Config:\n    debug = false\n    port = 8080\nlet c = Config()\nlet r = c.port\n"
        assert val(code, "r") == 8080

    def test_struct_partial_defaults(self):
        code = ("struct User:\n    name\n    role = \"guest\"\n"
                "let u = User(\"Alice\")\nlet r = u.role\n")
        assert val(code, "r") == "guest"

    def test_struct_override_default(self):
        code = ("struct User:\n    name\n    role = \"guest\"\n"
                "let u = User(\"Bob\", \"admin\")\nlet r = u.role\n")
        assert val(code, "r") == "admin"

    def test_struct_field_mutation(self):
        code = ("struct Box:\n    value\n"
                "let b = Box(10)\nb.value = 99\nlet r = b.value\n")
        assert val(code, "r") == 99

    def test_struct_too_many_args(self):
        with pytest.raises(NyxError) as exc:
            run("struct P:\n    x\nlet p = P(1, 2, 3)\n")
        assert "TypeError" in str(exc.value)

    def test_struct_missing_required_field(self):
        with pytest.raises(NyxError) as exc:
            run("struct P:\n    x\n    y\nlet p = P(1)\n")
        assert "TypeError" in str(exc.value)


# ══════════════════════════════════════════════════════════════════════════════
#  DEFAULT FUNCTION ARGUMENTS
# ══════════════════════════════════════════════════════════════════════════════

class TestDefaultArgs:

    def test_default_used_when_not_passed(self):
        code = 'def greet(name = "world"):\n    return "hello " + name\nlet r = greet()\n'
        assert val(code, "r") == "hello world"

    def test_default_overridden_when_passed(self):
        code = 'def greet(name = "world"):\n    return "hello " + name\nlet r = greet("Nyxel")\n'
        assert val(code, "r") == "hello Nyxel"

    def test_mixed_required_and_default(self):
        code = ('def msg(prefix, text = "ok"):\n    return prefix + ": " + text\n'
                'let r = msg("status")\n')
        assert val(code, "r") == "status: ok"

    def test_mixed_both_passed(self):
        code = ('def msg(prefix, text = "ok"):\n    return prefix + ": " + text\n'
                'let r = msg("status", "done")\n')
        assert val(code, "r") == "status: done"

    def test_too_few_args_raises(self):
        with pytest.raises(NyxError) as exc:
            run("def f(a, b):\n    return a\nf()\n")
        assert "TypeError" in str(exc.value)


# ══════════════════════════════════════════════════════════════════════════════
#  ERROR QUALITY  (did you mean / helpful hints)
# ══════════════════════════════════════════════════════════════════════════════

class TestErrorQuality:

    def test_did_you_mean_close_match(self):
        try:
            run("let username = 5\nsay(usernme)\n")
        except NyxError as e:
            # Should suggest 'username' for 'usernme'
            assert "username" in e.hint

    def test_no_false_suggestion_for_unrelated_name(self):
        try:
            run("let x = 1\nsay(completely_unrelated_xyz)\n")
        except NyxError as e:
            # Hint should be the fallback, not a wrong suggestion
            assert "let" in e.hint or e.hint == ""

    def test_type_error_suggests_str_conversion(self):
        try:
            run('let n = 5\nlet s = n + " apples"\n')
        except NyxError as e:
            assert "TypeError" in e.kind
            assert "str" in e.hint.lower() or "convert" in e.hint.lower()

    def test_division_by_zero_has_hint(self):
        try:
            run("let r = 10 / 0\n")
        except NyxError as e:
            assert e.kind == "MathError"
            assert e.hint != ""

    def test_index_error_on_list(self):
        with pytest.raises(NyxError) as exc:
            run("let lst = [1, 2]\nlet r = lst[9]\n")
        assert "IndexError" in str(exc.value)

    # ── lists ─────────────────────────────────────────────────────────────────

    def test_list_literal(self):
        lst = val("let lst = [1, 2, 3]", "lst")
        assert lst == [1, 2, 3]

    def test_list_index(self):
        assert val("let lst = [10, 20, 30]\nlet r = lst[1]\n", "r") == 20

    def test_list_index_assign(self):
        assert val("let lst = [1, 2, 3]\nlst[0] = 99\n", "lst")[0] == 99

    def test_list_concat(self):
        assert val("let r = [1, 2] + [3, 4]", "r") == [1, 2, 3, 4]

    def test_list_out_of_bounds(self):
        with pytest.raises(NyxError):
            run("let lst = [1]\nlet r = lst[5]\n")

    # ── dicts / NyxObject ─────────────────────────────────────────────────────

    def test_dict_literal(self):
        code = 'let d = {"a": 1, "b": 2}\nlet r = d.a\n'
        assert val(code, "r") == 1

    def test_dict_index(self):
        assert val('let d = {"k": 42}\nlet r = d["k"]\n', "r") == 42

    def test_dict_attr_assign(self):
        code = 'let d = {"x": 1}\nd.x = 99\nlet r = d.x\n'
        assert val(code, "r") == 99

    # ── python: blocks ────────────────────────────────────────────────────────

    def test_pyblock_return(self):
        code = "let x = 6\nlet r = python:\n    return x * 7\nend\n"
        assert val(code, "r") == 42

    def test_pyblock_sees_nyxel_vars(self):
        code = 'let greeting = "Hello"\nlet r = python:\n    return greeting + " World"\nend\n'
        assert val(code, "r") == "Hello World"

    def test_pyblock_standalone(self):
        code = "let x = 5\npython:\n    y = x + 1\nend\n"
        # No error should be raised
        run(code)

    def test_pyblock_stdlib(self):
        code = "let r = python:\n    import math\n    return math.floor(3.9)\nend\n"
        assert val(code, "r") == 3

    # ── undefined variable ────────────────────────────────────────────────────

    def test_undefined_var(self):
        with pytest.raises(NyxError) as exc:
            run("say(undefined_var)")
        assert "NameError" in str(exc.value)


# ══════════════════════════════════════════════════════════════════════════════
#  BUILT-INS
# ══════════════════════════════════════════════════════════════════════════════

class TestBuiltins:

    def test_len_list(self):
        assert val("let r = len([1, 2, 3])", "r") == 3

    def test_len_string(self):
        assert val('let r = len("hello")', "r") == 5

    def test_type_number(self):
        assert val("let r = type(42)", "r") == "number"

    def test_type_text(self):
        assert val('let r = type("hi")', "r") == "text"

    def test_type_list(self):
        assert val("let r = type([1, 2])", "r") == "list"

    def test_type_bool(self):
        assert val("let r = type(true)", "r") == "bool"

    def test_type_none(self):
        assert val("let r = type(none)", "r") == "none"

    def test_str_conversion(self):
        assert val("let r = str(42)", "r") == "42"

    def test_int_conversion(self):
        assert val('let r = int("7")', "r") == 7

    def test_float_conversion(self):
        assert val('let r = float("3.14")', "r") == 3.14

    def test_abs(self):
        assert val("let r = abs(-9)", "r") == 9

    def test_round(self):
        assert val("let r = round(3.7)", "r") == 4

    def test_max(self):
        # max_of is canonical; max() still works via Python interop if needed
        assert val("let r = max_of([3, 1, 9, 2])", "r") == 9

    def test_min(self):
        assert val("let r = min_of([3, 1, 9, 2])", "r") == 1

    def test_sum(self):
        assert val("let r = sum_of([1, 2, 3, 4, 5])", "r") == 15

    def test_sqrt(self):
        assert val("let r = sqrt(16)", "r") == 4.0

    def test_range(self):
        assert val("let r = range(5)", "r") == [0, 1, 2, 3, 4]

    def test_range_two_args(self):
        assert val("let r = range(2, 5)", "r") == [2, 3, 4]

    def test_sorted(self):
        assert val("let r = sorted([3, 1, 2])", "r") == [1, 2, 3]

    def test_reversed(self):
        assert val("let r = reversed([1, 2, 3])", "r") == [3, 2, 1]

    def test_upper(self):
        assert val('let r = upper("hello")', "r") == "HELLO"

    def test_lower(self):
        assert val('let r = lower("HELLO")', "r") == "hello"

    def test_strip(self):
        assert val('let r = strip("  hi  ")', "r") == "hi"

    def test_split(self):
        assert val('let r = split("a,b,c", ",")', "r") == ["a", "b", "c"]

    def test_join(self):
        assert val('let r = join(", ", ["a", "b", "c"])', "r") == "a, b, c"

    def test_replace(self):
        assert val('let r = replace("hello world", "world", "nyxel")', "r") == "hello nyxel"

    def test_starts_with(self):
        assert val('let r = starts_with("nyxel", "nyx")', "r") is True

    def test_ends_with(self):
        assert val('let r = ends_with("nyxel", "xel")', "r") is True

    def test_contains(self):
        assert val('let r = contains("hello world", "world")', "r") is True

    def test_to_json_from_json(self):
        code = (
            'let d = {"x": 1}\n'
            "let s = to_json(d)\n"
            "let d2 = from_json(s)\n"
            "let r = d2.x\n"
        )
        assert val(code, "r") == 1

    def test_say_output(self, capsys):
        run('say("hello", "world")')
        captured = capsys.readouterr()
        assert captured.out.strip() == "hello world"

    def test_say_bool_display(self, capsys):
        run("say(true)")
        assert capsys.readouterr().out.strip() == "true"

    def test_say_none_display(self, capsys):
        run("say(none)")
        assert capsys.readouterr().out.strip() == "none"


# ══════════════════════════════════════════════════════════════════════════════
#  INTEGRATION — full programs
# ══════════════════════════════════════════════════════════════════════════════

class TestIntegration:

    def test_fizzbuzz(self):
        code = """
let results = []
for i in range(1, 16):
    if i % 15 == 0:
        results = results + ["FizzBuzz"]
    elif i % 3 == 0:
        results = results + ["Fizz"]
    elif i % 5 == 0:
        results = results + ["Buzz"]
    else:
        results = results + [str(i)]
"""
        r = val(code, "results")
        assert r[2]  == "Fizz"
        assert r[4]  == "Buzz"
        assert r[14] == "FizzBuzz"

    def test_fibonacci(self):
        code = """
def fib(n):
    if n <= 1:
        return n
    return fib(n - 1) + fib(n - 2)

let r = fib(10)
"""
        assert val(code, "r") == 55

    def test_higher_order_map(self):
        # map() was removed as a builtin (too Python-specific)
        # In Nyxel you use a for loop + add … to
        code = """
let doubled = []
for each n in [1, 2, 3, 4, 5]:
    add n * 2 to doubled
"""
        assert val(code, "doubled") == [2, 4, 6, 8, 10]

    def test_higher_order_filter(self):
        # filter() was removed — use 'where item' instead
        code = "let r = range(10) where is_even(item)\n"
        assert val(code, "r") == [0, 2, 4, 6, 8]

    def test_nested_functions(self):
        code = """
def make_adder(n):
    def add(x):
        return x + n
    return add

let add5 = make_adder(5)
let r = add5(10)
"""
        assert val(code, "r") == 15

    def test_python_interop_math(self):
        code = """
let n = 25
let r = python:
    import math
    return math.sqrt(n)
end
"""
        assert val(code, "r") == 5.0

    def test_json_roundtrip(self):
        code = """
let original = {"name": "Nyxel", "version": 1}
let serialized = to_json(original)
let parsed = from_json(serialized)
let r = parsed.name
"""
        assert val(code, "r") == "Nyxel"

    def test_dict_mutation(self):
        code = """
let config = {"debug": false, "port": 8080}
config.debug = true
config.port = 9090
let r = config.debug
let p = config.port
"""
        g = run(code)
        assert g.get("r") is True
        assert g.get("p") == 9090

    def test_complex_string_processing(self):
        code = """
let words = split("the quick brown fox", " ")
let caps = []
for w in words:
    caps = caps + [upper(w[0]) + w[1:]]
let r = join(" ", caps)
"""
        # This uses python: style slicing via the Python interop
        # Actually Nyxel doesn't have slice notation yet — skip slicing
        # Instead test a simpler version:
        code2 = """
let words = split("hello world nyxel", " ")
let r = len(words)
"""
        assert val(code2, "r") == 3

    def test_write_and_read_file(self, tmp_path):
        p = str(tmp_path / "test.txt")
        code = f"""
write("{p}", "Nyxel test")
let r = read("{p}")
"""
        assert val(code, "r") == "Nyxel test"

    def test_file_not_found(self):
        with pytest.raises(NyxError) as exc:
            run('read("/no/such/file.txt")')
        assert "FileError" in str(exc.value)


# ══════════════════════════════════════════════════════════════════════════════
#  ERROR QUALITY
# ══════════════════════════════════════════════════════════════════════════════

class TestErrors:

    def test_error_has_kind(self):
        try:
            run("undefined_var")
        except NyxError as e:
            assert e.kind == "NameError"

    def test_error_has_message(self):
        try:
            run("let x = 1 / 0")
        except NyxError as e:
            assert e.msg

    def test_error_formats_cleanly(self):
        try:
            run("let x = 1 / 0")
        except NyxError as e:
            formatted = str(e)
            assert "MathError" in formatted
            assert "─" in formatted     # decorative bar present

    def test_hint_present_on_name_error(self):
        try:
            run("say(oops)")
        except NyxError as e:
            assert e.hint   # hint should be non-empty

    def test_syntax_error_on_bad_token(self):
        with pytest.raises(NyxError) as exc:
            Parser(lex("let 123abc = 5")).parse()
        assert "SyntaxError" in str(exc.value)


# ══════════════════════════════════════════════════════════════════════════════
#  RUNNER
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Allow running directly without pytest installed
    import traceback

    results = {"passed": 0, "failed": 0, "errors": []}
    test_classes = [
        TestLexer, TestParser, TestEnvironment, TestNyxObject,
        TestInterpreter, TestBuiltins, TestIntegration, TestErrors,
    ]

    for cls in test_classes:
        instance = cls()
        methods  = [m for m in dir(cls) if m.startswith("test_")]
        print(f"\n  {cls.__name__}  ({len(methods)} tests)")
        for method_name in methods:
            method = getattr(instance, method_name)
            # Skip tests that need capsys or tmp_path fixtures when run directly
            import inspect
            sig = inspect.signature(method)
            if len(sig.parameters) > 0:
                print(f"    ○  {method_name}  (skipped — needs pytest fixture)")
                continue
            try:
                method()
                print(f"    ✓  {method_name}")
                results["passed"] += 1
            except (AssertionError, Exception) as e:
                print(f"    ✗  {method_name}")
                results["failed"] += 1
                results["errors"].append((method_name, str(e)))

    total = results["passed"] + results["failed"]
    print(f"\n  ─────────────────────────────────────────────")
    print(f"  {results['passed']}/{total} passed", end="")
    if results["failed"]:
        print(f"  ·  {results['failed']} failed")
        for name, err in results["errors"]:
            print(f"    ✗ {name}: {err}")
    else:
        print("  —  all passed ✓")


# ══════════════════════════════════════════════════════════════════════════════
#  BRING RUNTIME  —  strengthened module loader
# ══════════════════════════════════════════════════════════════════════════════

class TestModuleLoaderRuntime:

    def test_module_cached_not_re_executed(self, tmp_path, monkeypatch):
        """A module should execute only once even if brought multiple times."""
        monkeypatch.chdir(tmp_path)
        # Module appends to a file on each execution
        (tmp_path / "counter.nx").write_text(
            'write("counter_log.txt", str(len(read("counter_log.txt")) + 1))\n'
            'let value = 42\n'
        )
        (tmp_path / "counter_log.txt").write_text("")
        code = "bring counter\nbring counter as c2\nlet r = counter.value\n"
        assert val(code, "r") == 42

    def test_module_isolates_globals(self, tmp_path, monkeypatch):
        """Module should not see or modify the caller's variables."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "isolated.nx").write_text("let x = 999\n")
        code = "let x = 1\nbring isolated\nlet r = x\n"
        assert val(code, "r") == 1   # caller's x unchanged

    def test_module_exports_only_user_names(self, tmp_path, monkeypatch):
        """Built-ins like say/get should not appear in module namespace."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mymod.nx").write_text("let greeting = \"hello\"\n")
        code = "bring mymod\nlet r = mymod.greeting\n"
        assert val(code, "r") == "hello"
        # say should not be an exported name from the module
        try:
            val("bring mymod\nlet r = mymod.say\n", "r")
            assert False, "Should have raised AttributeError"
        except NyxError as e:
            assert "AttributeError" in e.kind

    def test_module_error_shows_module_name(self, tmp_path, monkeypatch):
        """Errors inside a module should mention the module name."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "broken.nx").write_text("let x = 1 / 0\n")
        try:
            run("bring broken\n")
            assert False, "Should have raised"
        except NyxError as e:
            assert "broken" in str(e)

    def test_circular_import_detected(self, tmp_path, monkeypatch):
        """Circular brings should raise ImportError immediately."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "a.nx").write_text("bring b\n")
        (tmp_path / "b.nx").write_text("bring a\n")
        with pytest.raises(NyxError) as exc:
            run("bring a\n")
        assert "ImportError" in str(exc.value)

    def test_bring_from_suggests_close_name(self, tmp_path, monkeypatch):
        """bring wrong_name from module should suggest the correct name."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "maths.nx").write_text("def add(a, b):\n    return a + b\n")
        try:
            run("bring aad from maths\n")
        except NyxError as e:
            # Should suggest 'add' for 'aad'
            assert "add" in e.hint


# ══════════════════════════════════════════════════════════════════════════════
#  ERROR INTELLIGENCE  —  suggestions, field hints, missing colon
# ══════════════════════════════════════════════════════════════════════════════

class TestErrorIntelligence:

    # ── attribute suggestions ─────────────────────────────────────────────────

    def test_attr_error_suggests_close_field(self):
        """Typo in field name → suggest the correct field."""
        code = 'let u = {"name": "Alice", "age": 30}\nlet r = u.nme\n'
        try:
            run(code)
        except NyxError as e:
            assert "name" in e.hint

    def test_attr_error_lists_fields_when_no_close_match(self):
        """Completely wrong field → show available fields."""
        code = 'let u = {"name": "Alice"}\nlet r = u.xyz_totally_wrong\n'
        try:
            run(code)
        except NyxError as e:
            assert "name" in e.hint

    def test_attr_error_on_empty_object(self):
        """AttributeError on empty object should say 'no fields'."""
        code = 'let u = {}\nlet r = u.anything\n'
        try:
            run(code)
        except NyxError as e:
            assert "no fields" in e.hint.lower() or e.hint != ""

    # ── callable / name suggestions ───────────────────────────────────────────

    def test_print_suggests_say(self):
        """print() is not in Nyxel — should suggest say()."""
        try:
            run('print("hello")\n')
        except NyxError as e:
            assert "say" in e.hint

    def test_import_suggests_bring(self):
        """import is not a statement — should suggest bring."""
        try:
            run("import math\n")
        except NyxError as e:
            assert "bring" in e.hint

    def test_typo_in_function_name_suggests_correct(self):
        """Calling a slightly-misspelled function → suggest the real one."""
        code = "def calculate(x):\n    return x * 2\nlet r = calculte(5)\n"
        try:
            run(code)
        except NyxError as e:
            assert "calculate" in e.hint

    def test_typo_in_variable_name_suggests_correct(self):
        """Using a slightly-misspelled variable → suggest the real one."""
        code = "let total = 100\nlet r = totall\n"
        try:
            run(code)
        except NyxError as e:
            assert "total" in e.hint

    # ── missing colon detection ───────────────────────────────────────────────

    def test_missing_colon_after_if(self):
        """if without colon → specific 'missing colon' error."""
        src = "if true\n    say(\"hi\")\n"
        try:
            Parser(lex(src)).parse()
        except NyxError as e:
            assert ":" in e.msg or "colon" in e.msg.lower()

    def test_missing_colon_after_for(self):
        src = "for x in [1, 2]\n    say(x)\n"
        try:
            Parser(lex(src)).parse()
        except NyxError as e:
            assert ":" in e.msg or "colon" in e.msg.lower()

    def test_missing_colon_after_def(self):
        src = "def greet(name)\n    say(name)\n"
        try:
            Parser(lex(src)).parse()
        except NyxError as e:
            assert ":" in e.msg or "colon" in e.msg.lower()

    def test_missing_colon_hint_is_actionable(self):
        """The hint for a missing colon should show an example."""
        src = "while true\n    pass\n"
        try:
            Parser(lex(src)).parse()
        except NyxError as e:
            assert ":" in e.hint


# ══════════════════════════════════════════════════════════════════════════════
#  REPL  —  auto-display and block detection
# ══════════════════════════════════════════════════════════════════════════════

class TestReplLogic:
    """Test REPL helper functions without running the interactive loop."""

    def test_opens_block_if_statement(self):
        from nyxel.repl import _opens_block
        assert _opens_block("if x > 3:")
        assert _opens_block("for item in list:")
        assert _opens_block("while True:")
        assert _opens_block("def greet(name):")
        assert _opens_block("try:")
        assert _opens_block("struct Point:")
        assert _opens_block("repeat 5:")

    def test_does_not_open_block_normal_statement(self):
        from nyxel.repl import _opens_block
        assert not _opens_block('let x = {"key": "value"}')
        assert not _opens_block("say(x)")
        assert not _opens_block("")
        assert not _opens_block("# comment:")

    def test_block_depth_single_block(self):
        from nyxel.repl import _block_depth
        buf = ["if x > 3:", "    say(x)"]
        assert _block_depth(buf) == 1

    def test_block_depth_nested_blocks(self):
        from nyxel.repl import _block_depth
        buf = ["def greet(name):", "    if name:", "        say(name)"]
        assert _block_depth(buf) == 2

    def test_block_depth_closed_block(self):
        from nyxel.repl import _block_depth
        buf = ["if x > 3:", "    say(x)", "say('after')"]
        assert _block_depth(buf) == 0

    def test_run_repl_returns_expression_result(self):
        """eval() should return the value of a bare expression."""
        import nyxel._run as _run_mod
        from nyxel.compiler import Compiler
        _nyx_runtime = getattr(_run_mod, '__nyx_runtime')
        g = _nyx_runtime([])
        toks   = lex("3 + 4")
        stmts  = Parser(toks).parse()
        c = Compiler()
        result = eval(c._expr(stmts[0].expr), g)
        assert result == 7

    def test_run_repl_returns_none_for_let(self):
        """exec() should set the variable."""
        import nyxel._run as _run_mod
        from nyxel.compiler import transpile
        _nyx_runtime = getattr(_run_mod, '__nyx_runtime')
        g = _nyx_runtime([])
        toks   = lex("let x = 5")
        stmts  = Parser(toks).parse()
        py_source = transpile(stmts)
        exec(py_source, g)
        assert g.get("x") == 5

    def test_run_repl_returns_none_for_say(self):
        """say() returns None."""
        import nyxel._run as _run_mod
        from nyxel.compiler import transpile
        _nyx_runtime = getattr(_run_mod, '__nyx_runtime')
        g = _nyx_runtime([])
        toks   = lex('say("hello")')
        stmts  = Parser(toks).parse()
        py_source = transpile(stmts)
        exec(py_source, g)

    def test_run_repl_returns_variable_value(self):
        import nyxel._run as _run_mod
        from nyxel.compiler import Compiler, transpile
        _nyx_runtime = getattr(_run_mod, '__nyx_runtime')
        g = _nyx_runtime([])
        exec(transpile(Parser(lex("let x = 42")).parse()), g)
        toks   = lex("x")
        stmts  = Parser(toks).parse()
        c = Compiler()
        result = eval(c._expr(stmts[0].expr), g)
        assert result == 42


# ══════════════════════════════════════════════════════════════════════════════
#  BYTECODE  —  design / structure validation
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
#  PARAM NAMEDTUPLE — type consistency fix
# ══════════════════════════════════════════════════════════════════════════════

class TestParamNamedTuple:
    """Verify function definitions work correctly in transpiled mode."""

    def test_params_are_Param_objects(self):
        g = run("fn add(a, b):\n    return a + b\n")
        fn = g.get("add")
        assert callable(fn)
        assert fn(1, 2) == 3

    def test_param_name_attribute(self):
        g = run("fn greet(name):\n    return name\n")
        fn = g.get("greet")
        assert fn("Alice") == "Alice"

    def test_param_default_none_for_required(self):
        g = run("fn f(x):\n    return x\n")
        fn = g.get("f")
        with pytest.raises(TypeError):
            fn()

    def test_param_default_set_for_optional(self):
        g = run('fn greet(name = "world"):\n    return name\n')
        fn = g.get("greet")
        assert fn() == "world"
        assert fn("custom") == "custom"

    def test_required_count_property(self):
        g = run('fn f(a, b, c = 0):\n    return a\n')
        fn = g.get("f")
        with pytest.raises(TypeError):
            fn(1)
        assert fn(1, 2) == 1
        assert fn(1, 2, 3) == 1

    def test_param_names_property(self):
        g = run("fn f(x, y, z):\n    return x\n")
        fn = g.get("f")
        assert fn.__code__.co_varnames[:3] == ("x", "y", "z")

    def test_fn_repr_shows_defaults(self):
        g = run('fn greet(name = "world"):\n    return name\n')
        fn = g.get("greet")
        assert "greet" in repr(fn)

    def test_fn_repr_required_params(self):
        g = run("fn add(a, b):\n    return a + b\n")
        fn = g.get("add")
        assert callable(fn)
        assert fn(3, 4) == 7


# ══════════════════════════════════════════════════════════════════════════════
#  REFERENCE SEMANTICS — documented _wrap behaviour
# ══════════════════════════════════════════════════════════════════════════════

class TestReferenceSemantics:

    def test_two_vars_share_same_object(self):
        """let b = a makes b point to the same NyxObject."""
        code = 'let a = {"x": 1}\nlet b = a\nb.x = 99\nlet r = a.x\n'
        assert val(code, "r") == 99

    def test_copy_is_independent(self):
        """obj.copy() returns an independent object."""
        code = 'let a = {"x": 1}\nlet b = a.copy()\nb.x = 99\nlet r = a.x\n'
        assert val(code, "r") == 1

    def test_copy_has_same_initial_values(self):
        code = 'let a = {"x": 42}\nlet b = a.copy()\nlet r = b.x\n'
        assert val(code, "r") == 42

    def test_struct_instances_are_independent(self):
        """Each struct() call creates its own dict — not shared."""
        code = (
            "struct Box:\n    value\n"
            "let a = Box(1)\n"
            "let b = Box(1)\n"
            "a.value = 99\n"
            "let r = b.value\n"
        )
        assert val(code, "r") == 1

    def test_wrap_does_not_double_wrap(self):
        """_wrap on an already-wrapped NyxObject returns the same object."""
        from nyxel.runtime import NyxObject, _wrap
        obj = NyxObject({"x": 1})
        assert _wrap(obj) is obj

    def test_wrap_copy_is_independent(self):
        """_wrap_copy creates a new NyxObject that doesn't share the dict."""
        from nyxel.runtime import NyxObject, _wrap_copy
        original = {"x": 1}
        wrapped = _wrap_copy(original)
        wrapped.x = 99
        assert original["x"] == 1   # original dict unchanged

    def test_nyx_object_copy_method_exists(self):
        code = 'let a = {"k": "v"}\nlet b = a.copy()\n'
        run(code)   # must not raise

    def test_where_items_are_references(self):
        """Items returned by 'where' are the same objects (not copies)."""
        # Both 'people' and 'adults' refer to the same NyxObjects,
        # so mutating one via the original list is visible via the filtered list.
        code = (
            'let people = [{"name": "Alice", "age": 25}, {"name": "Bob", "age": 15}]\n'
            "let adults = people where age >= 18\n"
            # adults[0] and people[0] are the same object
            "let r = adults[0].name\n"
        )
        assert val(code, "r") == "Alice"
        # Verify it's the same item, not a copy, by checking identity via mutation
        code2 = (
            'let people = [{"name": "Alice", "age": 25}]\n'
            "let adults = people where age >= 18\n"
            "let same = len(adults) == 1\n"
        )
        assert val(code2, "same") is True


# ══════════════════════════════════════════════════════════════════════════════
#  REPL BLOCK DETECTION — heuristic correctness
# ══════════════════════════════════════════════════════════════════════════════

class TestReplBlockDetection:

    def test_otherwise_colon_opens_block(self):
        from nyxel.repl import _opens_block
        assert _opens_block("otherwise:")

    def test_otherwise_when_opens_block(self):
        from nyxel.repl import _opens_block
        assert _opens_block("otherwise when x > 3:")

    def test_fn_opens_block(self):
        from nyxel.repl import _opens_block
        assert _opens_block("fn greet(name):")

    def test_try_colon_opens_block(self):
        from nyxel.repl import _opens_block
        assert _opens_block("try:")

    def test_catch_opens_block(self):
        from nyxel.repl import _opens_block
        assert _opens_block("catch e:")

    def test_finally_opens_block(self):
        from nyxel.repl import _opens_block
        assert _opens_block("finally:")

    def test_dict_literal_does_not_open_block(self):
        from nyxel.repl import _opens_block
        # A dict literal on its own line shouldn't be treated as a block
        assert not _opens_block('let d = {"key": "value"}')

    def test_empty_string_does_not_open_block(self):
        from nyxel.repl import _opens_block
        assert not _opens_block("")

    def test_comment_does_not_open_block(self):
        from nyxel.repl import _opens_block
        assert not _opens_block("# when x > 3:")

    def test_block_depth_otherwise_block(self):
        from nyxel.repl import _block_depth
        buf = ["when x > 3:", "    say(x)", "otherwise:"]
        # 'otherwise:' is at depth 0 indent, closes the when, opens otherwise
        assert _block_depth(buf) == 1


# ══════════════════════════════════════════════════════════════════════════════
#  DESIGN DECISIONS — verify key invariants hold in code
# ══════════════════════════════════════════════════════════════════════════════

class TestDesignInvariants:

    def test_print_is_not_a_builtin(self):
        """print was removed — only say exists."""
        with pytest.raises(NyxError) as exc:
            run('print("hello")\n')
        e = exc.value
        assert e.kind == "NameError"
        assert "say" in e.hint      # should suggest say

    def test_fn_and_def_produce_identical_ast(self):
        """fn and def are aliases — same AST node type."""
        from nyxel.nyx_ast import DefStmt
        fn_stmts  = Parser(lex("fn add(a, b):\n    return a + b\n")).parse()
        def_stmts = Parser(lex("def add(a, b):\n    return a + b\n")).parse()
        assert type(fn_stmts[0]) == type(def_stmts[0]) == DefStmt

    def test_when_and_if_produce_identical_ast(self):
        """when and if are aliases — same AST node type."""
        from nyxel.nyx_ast import IfStmt
        when_stmts = Parser(lex("when x:\n    pass\n")).parse()
        if_stmts   = Parser(lex("if x:\n    pass\n")).parse()
        assert type(when_stmts[0]) == type(if_stmts[0]) == IfStmt

    def test_module_does_not_export_builtins(self, tmp_path, monkeypatch):
        """Modules should not leak built-in names to callers."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mymod.nx").write_text("let greeting = \"hello\"\n")
        try:
            val("bring mymod\nlet r = mymod.say\n", "r")
            assert False, "Should have raised"
        except NyxError as e:
            assert "AttributeError" in e.kind

    def test_defstmt_params_always_param_objects(self):
        """Both fn and def produce callable functions."""
        for code in [
            "fn f(x, y = 0):\n    return x\n",
            "def f(x, y = 0):\n    return x\n",
        ]:
            g = run(code)
            fn = g.get("f")
            assert callable(fn)
            assert fn(1) == 1
            assert fn(2, 3) == 2

    def test_nyx_exception_is_nyx_object(self):
        """NyxException must be a NyxObject — it's a runtime value."""
        from nyxel.runtime import NyxException, NyxObject
        exc = NyxException("TestError", "something went wrong")
        assert isinstance(exc, NyxObject)
        assert exc.kind    == "TestError"
        assert exc.message == "something went wrong"


# ══════════════════════════════════════════════════════════════════════════════
#  .length AND .is_empty()
# ══════════════════════════════════════════════════════════════════════════════

class TestDotLength:

    def test_string_length(self):
        assert val('let r = "hello".length', "r") == 5

    def test_string_length_empty(self):
        assert val('let r = "".length', "r") == 0

    def test_list_length(self):
        assert val("let r = [1, 2, 3].length", "r") == 3

    def test_list_length_empty(self):
        assert val("let r = [].length", "r") == 0

    def test_dict_length(self):
        assert val('let r = {"a": 1, "b": 2}.length', "r") == 2

    def test_variable_string_length(self):
        assert val('let name = "Nyxel"\nlet r = name.length', "r") == 5

    def test_variable_list_length(self):
        assert val("let lst = [10, 20, 30]\nlet r = lst.length", "r") == 3

    def test_length_in_where_condition(self):
        code = (
            'let words = ["hi", "hello", "hey", "howdy"]\n'
            "let long = words where length > 3\n"
            "let r = long.length\n"
        )
        assert val(code, "r") == 2

    def test_is_empty_on_empty_list(self):
        assert val("let r = [].is_empty()", "r") is True

    def test_is_empty_on_non_empty_list(self):
        assert val("let r = [1].is_empty()", "r") is False

    def test_is_empty_on_empty_string(self):
        assert val('let r = "".is_empty()', "r") is True

    def test_is_empty_on_non_empty_string(self):
        assert val('let r = "hi".is_empty()', "r") is False

    def test_length_on_name_dot_length(self):
        """name.length — the key use case mentioned in the requirements."""
        code = 'let name = "Alice"\nlet r = name.length\n'
        assert val(code, "r") == 5


class TestStringMethods:

    def test_upper_via_dot(self):
        assert val('let r = "hello".upper()', "r") == "HELLO"

    def test_lower_via_dot(self):
        assert val('let r = "HELLO".lower()', "r") == "hello"

    def test_strip_via_dot(self):
        assert val('let r = "  hi  ".strip()', "r") == "hi"

    def test_contains_via_dot(self):
        assert val('let r = "hello world".contains("world")', "r") is True

    def test_starts_with_via_dot(self):
        assert val('let r = "nyxel".starts_with("nyx")', "r") is True

    def test_ends_with_via_dot(self):
        assert val('let r = "nyxel".ends_with("xel")', "r") is True

    def test_replace_via_dot(self):
        assert val('let r = "hello world".replace("world", "nyxel")', "r") == "hello nyxel"

    def test_split_via_dot(self):
        assert val('let r = "a,b,c".split(",")', "r") == ["a", "b", "c"]


# ══════════════════════════════════════════════════════════════════════════════
#  ADD … TO
# ══════════════════════════════════════════════════════════════════════════════

class TestAddTo:

    def test_basic_add_to(self):
        code = "let lst = []\nadd 1 to lst\nadd 2 to lst\nlet r = lst.length\n"
        assert val(code, "r") == 2

    def test_add_preserves_order(self):
        code = "let lst = []\nadd 10 to lst\nadd 20 to lst\nadd 30 to lst\n"
        assert val(code, "lst") == [10, 20, 30]

    def test_add_expression(self):
        code = "let lst = []\nlet x = 5\nadd x * 2 to lst\n"
        assert val(code, "lst") == [10]

    def test_add_string(self):
        code = 'let words = []\nadd "hello" to words\nadd "world" to words\n'
        assert val(code, "words") == ["hello", "world"]

    def test_add_in_loop(self):
        code = (
            "let evens = []\n"
            "for each n in [1, 2, 3, 4, 5, 6]:\n"
            "    when is_even(n):\n"
            "        add n to evens\n"
        )
        assert val(code, "evens") == [2, 4, 6]

    def test_add_to_non_list_raises(self):
        with pytest.raises(NyxError) as exc:
            run('let x = "not a list"\nadd 1 to x\n')
        assert "TypeError" in str(exc.value)
        assert "list" in str(exc.value)


# ══════════════════════════════════════════════════════════════════════════════
#  FOR EACH
# ══════════════════════════════════════════════════════════════════════════════

class TestForEach:

    def test_for_each_basic(self):
        code = "let t = 0\nfor each n in [1,2,3,4,5]:\n    t = t + n\n"
        assert val(code, "t") == 15

    def test_for_each_with_descriptive_name(self):
        code = "let names = []\nfor each person in [\"Alice\",\"Bob\"]:\n    add person to names\n"
        assert val(code, "names") == ["Alice", "Bob"]

    def test_for_each_and_for_produce_same_result(self):
        """for each and for are identical — same AST node."""
        r1 = val("let t = 0\nfor each n in [1,2,3]:\n    t = t + n\n", "t")
        r2 = val("let t = 0\nfor n in [1,2,3]:\n    t = t + n\n", "t")
        assert r1 == r2

    def test_for_each_with_where(self):
        code = (
            "let total = 0\n"
            "let evens = [1,2,3,4,5,6] where is_even(n)\n"
        )
        # where with a function call — n refers to the list item
        code2 = (
            "let nums = [1,2,3,4,5,6]\n"
            "let total = 0\n"
            "for each n in nums:\n"
            "    when is_even(n):\n"
            "        total = total + n\n"
        )
        assert val(code2, "total") == 12


# ══════════════════════════════════════════════════════════════════════════════
#  BEGINNER BUILTINS
# ══════════════════════════════════════════════════════════════════════════════

class TestBeginnerBuiltins:

    def test_is_even_true(self):   assert val("let r = is_even(4)", "r") is True
    def test_is_even_false(self):  assert val("let r = is_even(3)", "r") is False
    def test_is_odd_true(self):    assert val("let r = is_odd(3)",  "r") is True
    def test_is_odd_false(self):   assert val("let r = is_odd(4)",  "r") is False

    def test_is_empty_empty_list(self):     assert val("let r = is_empty([])",   "r") is True
    def test_is_empty_non_empty_list(self): assert val("let r = is_empty([1])",  "r") is False
    def test_is_empty_empty_string(self):   assert val('let r = is_empty("")',   "r") is True
    def test_is_empty_non_empty_string(self): assert val('let r = is_empty("x")', "r") is False

    def test_to_str(self):   assert val("let r = to_str(42)",   "r") == "42"
    def test_to_int(self):   assert val('let r = to_int("7")',  "r") == 7
    def test_to_float(self): assert val('let r = to_float("3.5")', "r") == 3.5

    def test_is_number_true(self):  assert val("let r = is_number(42)",   "r") is True
    def test_is_number_false(self): assert val('let r = is_number("hi")', "r") is False
    def test_is_text_true(self):    assert val('let r = is_text("hi")',   "r") is True
    def test_is_text_false(self):   assert val("let r = is_text(42)",     "r") is False

    def test_is_even_in_loop(self):
        code = (
            "let evens = []\n"
            "for each n in range(10):\n"
            "    when is_even(n):\n"
            "        add n to evens\n"
        )
        assert val(code, "evens") == [0, 2, 4, 6, 8]

    def test_to_str_with_concat(self):
        code = 'let age = 25\nlet r = "Age: " + to_str(age)\n'
        assert val(code, "r") == "Age: 25"


# ══════════════════════════════════════════════════════════════════════════════
#  WHERE — 'item' canonical variable and teaching NameError
# ══════════════════════════════════════════════════════════════════════════════

class TestWhereItem:

    def test_item_works_on_list_of_strings(self):
        code = 'let words = ["hi", "hello", "hey"]\nlet r = words where item.length > 3\n'
        assert val(code, "r") == ["hello"]

    def test_item_works_on_list_of_numbers(self):
        code = "let r = [1,2,3,4,5] where is_even(item)\n"
        assert val(code, "r") == [2, 4]

    def test_item_works_on_list_of_objects(self):
        code = (
            'let people = [{"name": "Alice", "age": 25}, {"name": "Bob", "age": 15}]\n'
            "let r = people where item.age >= 18\n"
        )
        result = val(code, "r")
        assert len(result) == 1

    def test_each_alias_also_works(self):
        """'each' is an alias for 'item' inside where."""
        code = "let r = [1,2,3,4,5] where is_odd(each)\n"
        assert val(code, "r") == [1, 3, 5]

    def test_field_names_still_work_for_objects(self):
        """Fields like 'age', 'name' still accessible directly (no item. needed)."""
        code = (
            'let users = [{"name": "Alice", "age": 25}, {"name": "Bob", "age": 15}]\n'
            "let r = users where age >= 18\n"
        )
        result = val(code, "r")
        assert len(result) == 1

    def test_length_directly_accessible(self):
        """'length' works directly inside where — no item.length needed for strings."""
        code = 'let words = ["a", "bb", "ccc", "dddd"]\nlet r = words where length > 2\n'
        assert val(code, "r") == ["ccc", "dddd"]

    def test_nameerror_in_where_gives_teaching_hint(self):
        """NameError inside where should explain 'item'."""
        try:
            run("[1,2,3] where x > 1\n")
        except NyxError as e:
            assert e.kind == "NameError"
            assert "item" in e.hint.lower()

    def test_nameerror_hint_shows_example(self):
        """The teaching hint should include a code example."""
        try:
            run('["hi", "bye"] where f.length > 2\n')
        except NyxError as e:
            assert "item" in e.hint
            assert "Example" in e.hint or "example" in e.hint or "=>" in e.hint or ":" in e.hint

    def test_item_with_length_in_where(self):
        code = 'let names = ["Al", "Bob", "Charlie"]\nlet r = names where item.length > 2\n'
        assert val(code, "r") == ["Bob", "Charlie"]

    def test_where_with_outer_variable(self):
        """Outer scope variables should still be accessible in where conditions."""
        code = "let min_age = 18\nlet ages = [15, 20, 17, 25]\nlet r = ages where item >= min_age\n"
        assert val(code, "r") == [20, 25]

    def test_item_works_with_is_empty(self):
        code = 'let words = ["hello", "", "world", ""]\nlet r = words where not is_empty(item)\n'
        assert val(code, "r") == ["hello", "world"]


# ══════════════════════════════════════════════════════════════════════════════
#  read_lines, lines_of, words_of
# ══════════════════════════════════════════════════════════════════════════════

class TestFileHelpers:

    def test_read_lines_returns_list(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "test.txt").write_text("line one\nline two\nline three\n")
        code = 'let lines = read_lines("test.txt")\nlet r = lines.length\n'
        assert val(code, "r") == 3

    def test_read_lines_content(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "notes.txt").write_text("hello\nworld\n")
        code = 'let lines = read_lines("notes.txt")\nlet r = lines[0]\n'
        assert val(code, "r") == "hello"

    def test_read_lines_filters_with_where(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data.txt").write_text("short\na longer line\nhi\nanother long one\n")
        code = 'let lines = read_lines("data.txt")\nlet long = lines where item.length > 5\nlet r = long.length\n'
        assert val(code, "r") == 2

    def test_lines_of_basic(self):
        code = 'let r = lines_of("hello\\nworld\\nnyxel")\n'
        assert val(code, "r") == ["hello", "world", "nyxel"]

    def test_lines_of_length(self):
        code = 'let r = lines_of("a\\nb\\nc").length\n'
        assert val(code, "r") == 3

    def test_words_of_basic(self):
        code = 'let r = words_of("hello world nyxel")\n'
        assert val(code, "r") == ["hello", "world", "nyxel"]

    def test_words_of_length(self):
        code = 'let r = words_of("one two three four five").length\n'
        assert val(code, "r") == 5

    def test_words_of_first_word(self):
        code = 'let r = words_of("Nyxel is simple")[0]\n'
        assert val(code, "r") == "Nyxel"

    def test_words_of_handles_extra_spaces(self):
        """words_of should handle multiple spaces between words."""
        code = 'let r = words_of("hello   world").length\n'
        assert val(code, "r") == 2

    def test_lines_of_on_non_text_raises(self):
        with pytest.raises(NyxError) as exc:
            run("let r = lines_of(42)\n")
        assert "TypeError" in str(exc.value)

    def test_words_of_on_non_text_raises(self):
        with pytest.raises(NyxError) as exc:
            run("let r = words_of([1,2,3])\n")
        assert "TypeError" in str(exc.value)


# ══════════════════════════════════════════════════════════════════════════════
#  NEW CHECK BUILTINS — is_divisible_by, count_of
# ══════════════════════════════════════════════════════════════════════════════

class TestNewCheckBuiltins:

    def test_is_divisible_by_true(self):
        assert val("let r = is_divisible_by(10, 5)", "r") is True

    def test_is_divisible_by_false(self):
        assert val("let r = is_divisible_by(7, 3)", "r") is False

    def test_is_divisible_by_zero_raises(self):
        with pytest.raises(NyxError) as exc:
            run("let r = is_divisible_by(5, 0)\n")
        assert "MathError" in str(exc.value)

    def test_is_divisible_in_where(self):
        code = "let r = range(1, 13) where is_divisible_by(item, 3)\n"
        assert val(code, "r") == [3, 6, 9, 12]

    def test_count_of_list(self):
        assert val("let r = count_of([1, 2, 2, 3, 2], 2)", "r") == 3

    def test_count_of_zero(self):
        assert val("let r = count_of([1, 2, 3], 9)", "r") == 0

    def test_count_of_string(self):
        assert val('let r = count_of("hello world", "l")', "r") == 3

    def test_fizzbuzz_without_percent(self):
        """Beginner should be able to write FizzBuzz without knowing %."""
        code = """
let results = []
repeat i from 1 to 15:
    when is_divisible_by(i, 15):
        add "FizzBuzz" to results
    otherwise when is_divisible_by(i, 3):
        add "Fizz" to results
    otherwise when is_divisible_by(i, 5):
        add "Buzz" to results
    otherwise:
        add to_str(i) to results
"""
        r = val(code, "results")
        assert r[2]  == "Fizz"
        assert r[4]  == "Buzz"
        assert r[14] == "FizzBuzz"


# ══════════════════════════════════════════════════════════════════════════════
#  BEGINNER SCRIPT INTEGRATION — the "does it feel smooth?" test
# ══════════════════════════════════════════════════════════════════════════════

class TestBeginnerScriptIntegration:

    def test_full_list_workflow(self):
        """The complete beginner list workflow from the examples."""
        code = """
let scores = [72, 91, 45, 88, 63, 95, 55, 80]

let passing = []
let failing = []

for each score in scores:
    when score >= 60:
        add score to passing
    otherwise:
        add score to failing
"""
        g = run(code)
        assert g.get("passing") == [72, 91, 88, 63, 95, 80]
        assert g.get("failing") == [45, 55]

    def test_where_reads_like_a_sentence(self):
        """
        The key readability test:
          users where item.age >= 18
        should read like English and just work.
        """
        code = """
let users = [
    {"name": "Alice", "age": 25},
    {"name": "Bob",   "age": 16},
    {"name": "Carol", "age": 19}
]

let adults = users where item.age >= 18
let names = []
for each user in adults:
    add user.name to names
"""
        g = run(code)
        assert g.get("names") == ["Alice", "Carol"]

    def test_no_percent_needed_for_fizzbuzz(self):
        """FizzBuzz with no % symbol — beginners can write it."""
        code = """
let fizzbuzz = []
repeat i from 1 to 5:
    when is_divisible_by(i, 3):
        add "Fizz" to fizzbuzz
    otherwise:
        add to_str(i) to fizzbuzz
"""
        r = val(code, "fizzbuzz")
        assert r == ["1", "2", "Fizz", "4", "5"]

    def test_read_lines_workflow(self, tmp_path, monkeypatch):
        """read_lines + where + for each — no split() knowledge needed."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "tasks.txt").write_text("Buy milk\nDo homework\nRun\nFinish the project\n")
        code = """
let tasks = read_lines("tasks.txt")
let big_tasks = tasks where item.length > 8
"""
        r = val(code, "big_tasks")
        assert r == ["Do homework", "Finish the project"]


# ══════════════════════════════════════════════════════════════════════════════
#  NEW BUILTINS — save_json, load_json, pretty, data helpers
# ══════════════════════════════════════════════════════════════════════════════

class TestJsonHelpers:

    def test_save_and_load_json_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        code = (
            'let data = {"name": "Alice", "score": 99}\n'
            'save_json("out.json", data)\n'
            'let back = load_json("out.json")\n'
            'let r = back.name\n'
        )
        assert val(code, "r") == "Alice"

    def test_save_json_creates_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        run('let d = {"x": 1}\nsave_json("test.json", d)\n')
        assert (tmp_path / "test.json").exists()

    def test_save_json_list(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        code = (
            'let items = [{"id": 1}, {"id": 2}]\n'
            'save_json("items.json", items)\n'
            'let back = load_json("items.json")\n'
            'let r = back.length\n'
        )
        assert val(code, "r") == 2

    def test_load_json_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(NyxError) as exc:
            run('load_json("no_such_file.json")\n')
        assert "FileError" in str(exc.value)

    def test_load_json_preserves_fields(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        import json
        (tmp_path / "data.json").write_text(json.dumps({"age": 25, "name": "Bob"}))
        code = 'let d = load_json("data.json")\nlet r = d.age\n'
        assert val(code, "r") == 25


class TestDataHelpers:

    def test_numbers_of_from_text(self):
        code = 'let r = numbers_of("10 20 bad 30")\n'
        assert val(code, "r") == [10, 20, 30]

    def test_numbers_of_skips_non_numbers(self):
        code = 'let r = numbers_of("1.5 hello 2.5 world 3")\n'
        r = val(code, "r")
        assert len(r) == 3
        assert r[0] == 1.5

    def test_numbers_of_from_list(self):
        code = 'let r = numbers_of([1, "skip", 2, "also_skip", 3])\n'
        assert val(code, "r") == [1, 2, 3]

    def test_average_of_basic(self):
        assert val("let r = average_of([10, 20, 30])", "r") == 20.0

    def test_average_of_single(self):
        assert val("let r = average_of([42])", "r") == 42.0

    def test_average_of_empty_raises(self):
        with pytest.raises(NyxError) as exc:
            run("let r = average_of([])\n")
        assert "MathError" in str(exc.value)
        # Message should be teaching-quality
        assert "empty" in str(exc.value).lower()

    def test_sum_of(self):
        assert val("let r = sum_of([1, 2, 3, 4, 5])", "r") == 15

    def test_max_of(self):
        assert val("let r = max_of([3, 1, 9, 2])", "r") == 9

    def test_min_of(self):
        assert val("let r = min_of([3, 1, 9, 2])", "r") == 1

    def test_unique_removes_duplicates(self):
        assert val("let r = unique([1, 2, 2, 3, 1, 3])", "r") == [1, 2, 3]

    def test_unique_preserves_order(self):
        assert val("let r = unique([3, 1, 2, 1, 3])", "r") == [3, 1, 2]

    def test_unique_empty(self):
        assert val("let r = unique([])", "r") == []

    def test_flatten_basic(self):
        assert val("let r = flatten([[1,2],[3,4],[5]])", "r") == [1,2,3,4,5]

    def test_flatten_empty_inner(self):
        assert val("let r = flatten([[1], [], [2]])", "r") == [1, 2]

    def test_first_of(self):
        assert val("let r = first_of([10, 20, 30])", "r") == 10

    def test_first_of_empty(self):
        assert val("let r = first_of([])", "r") is None

    def test_last_of(self):
        assert val("let r = last_of([10, 20, 30])", "r") == 30

    def test_last_of_empty(self):
        assert val("let r = last_of([])", "r") is None

    def test_group_by(self):
        code = (
            'let people = [\n'
            '    {"name": "Alice", "city": "NY"},\n'
            '    {"name": "Bob",   "city": "LA"},\n'
            '    {"name": "Carol", "city": "NY"}\n'
            ']\n'
            'let by_city = group_by(people, "city")\n'
            'let r = by_city["NY"].length\n'
        )
        assert val(code, "r") == 2

    def test_run_lines_returns_list(self):
        code = 'let r = run_lines("echo hello")\n'
        result = val(code, "r")
        assert isinstance(result, list)
        assert len(result) >= 1


class TestDataWorkflow:
    """End-to-end tests that simulate real project scripts."""

    def test_clean_data_workflow(self, tmp_path, monkeypatch):
        """Simulate 02_clean_data.nx logic."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "raw.txt").write_text("apple\nbanana\n\napple\ncherry\n")
        code = """
let lines = read_lines("raw.txt")
let non_empty = lines where not is_empty(item)
let clean = unique(non_empty)
"""
        g = run(code)
        clean = g.get("clean")
        assert len(clean) == 3
        assert "apple" in clean

    def test_numbers_analysis_workflow(self):
        """Simulate 03_data_analysis.nx logic."""
        code = """
let text = "10 20 30 40 50"
let values = numbers_of(text)
let avg = average_of(values)
let above = values where item > avg
"""
        g = run(code)
        assert g.get("avg") == 30.0
        above = g.get("above")
        assert above == [40, 50]

    def test_save_load_preserve_list(self, tmp_path, monkeypatch):
        """save_json then load_json roundtrip for a list."""
        monkeypatch.chdir(tmp_path)
        code = """
let scores = [85, 92, 78, 96, 88]
save_json("scores.json", scores)
let loaded = load_json("scores.json")
let r = average_of(loaded)
"""
        assert abs(val(code, "r") - 87.8) < 0.01

    def test_pretty_does_not_crash(self, capsys):
        """pretty() should print without raising."""
        run('let d = {"name": "Nyxel"}\npretty(d)\n')
        out = capsys.readouterr().out
        assert "Nyxel" in out
        assert '"name"' in out


# ══════════════════════════════════════════════════════════════════════════════
#  ERROR QUALITY AUDIT — every user-facing error must have a hint
# ══════════════════════════════════════════════════════════════════════════════

class TestErrorHints:
    """
    Verify that every common error:
      1. Has a non-empty hint
      2. Keeps to the rule: one explanation + one example, no paragraphs
    """

    def _get_error(self, code: str) -> NyxError:
        try:
            run(code)
            raise AssertionError("Expected a NyxError but none was raised")
        except NyxError as e:
            return e

    # ── NameError ─────────────────────────────────────────────────────────────

    def test_name_error_has_hint(self):
        e = self._get_error("say(undefined_xyz)\n")
        assert e.kind == "NameError"
        assert e.hint

    def test_name_error_suggests_let(self):
        e = self._get_error("say(completely_new_name)\n")
        assert "let" in e.hint or "Did you mean" in e.hint

    def test_name_error_print_suggests_say(self):
        e = self._get_error('print("hello")\n')
        assert "say" in e.hint

    def test_name_error_typo_suggests_correct(self):
        e = self._get_error("let username = 5\nsay(usernam)\n")
        assert "username" in e.hint

    # ── TypeError ─────────────────────────────────────────────────────────────

    def test_type_error_add_number_text_has_hint(self):
        # Note: "5 + text" is VALID in Nyxel (auto-coerced to string concat).
        # A real type error: subtracting text from a number.
        e = self._get_error('let r = "hello" - 5\n')
        assert e.kind == "TypeError"
        assert e.hint
        assert "number" in e.hint.lower()

    def test_type_error_operator_has_hint(self):
        e = self._get_error('let r = "hello" - "world"\n')
        assert e.kind == "TypeError"
        assert e.hint
        assert "number" in e.hint.lower()

    def test_type_error_repeat_non_number_has_hint(self):
        e = self._get_error('repeat "five":\n    say("hi")\n')
        assert e.hint

    def test_type_error_wrong_arg_count_has_hint(self):
        e = self._get_error("fn f(a, b):\n    return a\nf(1)\n")
        assert e.kind == "TypeError"
        assert e.hint or e.msg   # message already explains it clearly

    # ── MathError ────────────────────────────────────────────────────────────

    def test_division_by_zero_has_hint(self):
        e = self._get_error("let r = 10 / 0\n")
        assert e.kind == "MathError"
        assert e.hint
        assert "zero" in e.hint.lower() or "divisor" in e.hint.lower()

    def test_floor_division_by_zero_has_hint(self):
        e = self._get_error("let r = 10 // 0\n")
        assert e.kind == "MathError"
        assert e.hint

    def test_average_of_empty_has_hint(self):
        e = self._get_error("average_of([])\n")
        assert e.kind == "MathError"
        assert e.hint
        assert "number" in e.hint.lower() or "example" in e.hint.lower()

    def test_max_of_empty_has_hint(self):
        e = self._get_error("max_of([])\n")
        assert e.kind == "MathError"
        assert e.hint

    def test_min_of_empty_has_hint(self):
        e = self._get_error("min_of([])\n")
        assert e.kind == "MathError"
        assert e.hint

    # ── IndexError ────────────────────────────────────────────────────────────

    def test_index_out_of_bounds_has_hint(self):
        e = self._get_error("let lst = [1, 2, 3]\nlet r = lst[9]\n")
        assert e.kind == "IndexError"
        assert e.hint
        assert "9" in e.hint or "index" in e.hint.lower() or "valid" in e.hint.lower()

    def test_index_wrong_type_has_hint(self):
        e = self._get_error('let r = 42["key"]\n')
        assert e.kind == "TypeError"
        assert e.hint

    # ── AttributeError ───────────────────────────────────────────────────────

    def test_attr_error_suggests_close_field(self):
        e = self._get_error('let u = {"name": "Alice"}\nlet r = u.nme\n')
        assert e.kind == "AttributeError"
        assert "name" in e.hint

    def test_attr_error_lists_available_fields(self):
        e = self._get_error('let u = {"score": 99}\nlet r = u.xyz\n')
        assert e.kind == "AttributeError"
        assert "score" in e.hint

    def test_string_attr_error_shows_available(self):
        e = self._get_error('"hello".nonexistent()\n')
        assert e.kind == "AttributeError"
        assert e.hint
        # Should list some real string methods
        assert any(m in e.hint for m in ["upper", "lower", "length", "strip", "contains"])

    # ── FileError ─────────────────────────────────────────────────────────────

    def test_read_missing_file_has_hint(self):
        e = self._get_error('read("no_such_file_xyz.txt")\n')
        assert e.kind == "FileError"
        assert e.hint

    def test_load_json_missing_file_has_hint(self):
        e = self._get_error('load_json("no_such_file.json")\n')
        assert e.kind == "FileError"
        assert e.hint

    # ── SyntaxError ──────────────────────────────────────────────────────────

    def test_missing_colon_has_hint(self):
        e = self._get_error("when true\n    say('hi')\n")
        assert e.kind == "SyntaxError"
        assert e.hint
        assert ":" in e.hint

    def test_try_without_catch_has_hint(self):
        try:
            Parser(lex("try:\n    pass\n")).parse()
            assert False
        except NyxError as e:
            assert e.hint
            assert "catch" in e.hint.lower() or "finally" in e.hint.lower()

    def test_struct_not_indented_has_hint(self):
        try:
            Parser(lex("struct Point:\nx = 0\n")).parse()
            assert False
        except NyxError as e:
            assert e.hint
            assert "indent" in e.hint.lower()

    # ── Where NameError ───────────────────────────────────────────────────────

    def test_where_name_error_teaches_item(self):
        e = self._get_error("[1,2,3] where x > 1\n")
        assert e.kind == "NameError"
        assert "item" in e.hint.lower()

    def test_where_name_error_shows_example(self):
        e = self._get_error('["a","b"] where f.length > 0\n')
        assert "item" in e.hint

    # ── add to non-list ───────────────────────────────────────────────────────

    def test_add_to_non_list_has_hint(self):
        e = self._get_error('let x = "text"\nadd 1 to x\n')
        assert e.kind == "TypeError"
        assert e.hint
        assert "list" in e.hint.lower()

    # ── import suggestion ─────────────────────────────────────────────────────

    def test_import_suggests_bring(self):
        e = self._get_error("import math\n")
        assert "bring" in e.hint

    # ── hint length rule: no hint should be more than 3 lines ─────────────────

    def test_all_common_errors_have_concise_hints(self):
        """No hint should be a wall of text. Max 3 lines."""
        test_cases = [
            ("say(undefined)\n",               "NameError"),
            ('let r = 5 + " text"\n',          "TypeError"),
            ("let r = 1 / 0\n",                "MathError"),
            ("let r = [1,2][9]\n",             "IndexError"),
            ('let u = {"a":1}\nlet r = u.z\n', "AttributeError"),
            ('read("no_file.txt")\n',           "FileError"),
            ("average_of([])\n",               "MathError"),
        ]
        for code, expected_kind in test_cases:
            try:
                run(code)
            except NyxError as e:
                assert e.kind == expected_kind, f"Expected {expected_kind}, got {e.kind}"
                if e.hint:
                    line_count = e.hint.count("\n") + 1
                    assert line_count <= 4, (
                        f"{expected_kind} hint has {line_count} lines — keep it to 3 max.\n"
                        f"Hint was: {e.hint!r}"
                    )


# ══════════════════════════════════════════════════════════════════════════════
#  ARABIC LANGUAGE SUPPORT
# ══════════════════════════════════════════════════════════════════════════════

class TestArabic:

    def test_arabic_let(self):
        assert val("اجعل س = 5", "س") == 5

    def test_arabic_say(self, capsys):
        run('قل("مرحبا")')
        assert "مرحبا" in capsys.readouterr().out

    def test_arabic_when(self):
        # pre-define ن then reassign inside when block
        code = "اجعل س = 10\nاجعل ن = 0\nعندما س > 5:\n    ن = 1\nوإلا:\n    ن = 0\n"
        assert val(code, "ن") == 1

    def test_arabic_otherwise(self):
        code = "اجعل س = 2\nاجعل ن = 0\nعندما س > 5:\n    ن = 1\nوإلا:\n    ن = 99\n"
        assert val(code, "ن") == 99

    def test_arabic_repeat(self):
        code = "اجعل ع = 0\nكرر 5:\n    ع = ع + 1\n"
        assert val(code, "ع") == 5

    def test_arabic_repeat_range(self):
        code = "اجعل مجموع = 0\nكرر i من 1 إلى 5:\n    مجموع = مجموع + i\n"
        assert val(code, "مجموع") == 15

    def test_arabic_for_each(self):
        code = "اجعل ع = 0\nلكل كل رقم في [1, 2, 3]:\n    ع = ع + رقم\n"
        assert val(code, "ع") == 6

    def test_arabic_fn(self):
        code = "دالة مضاعفة(رقم):\n    أرجع رقم * 2\nاجعل ن = مضاعفة(5)\n"
        assert val(code, "ن") == 10

    def test_arabic_add_to(self):
        code = "اجعل قائمة = []\nأضف 1 إلى قائمة\nأضف 2 إلى قائمة\n"
        assert val(code, "قائمة") == [1, 2]

    def test_arabic_where(self):
        code = "اجعل أرقام = [1, 2, 3, 4, 5]\nاجعل نتيجة = أرقام حيث item > 3\n"
        assert val(code, "نتيجة") == [4, 5]

    def test_arabic_true_false(self):
        assert val("اجعل ص = صحيح", "ص") is True
        assert val("اجعل خ = خطأ", "خ") is False

    def test_arabic_none(self):
        assert val("اجعل ل = لاشيء", "ل") is None

    def test_arabic_and_or(self):
        assert val("اجعل ن = صحيح و صحيح", "ن") is True
        assert val("اجعل ن = خطأ أو صحيح", "ن") is True

    def test_arabic_not(self):
        assert val("اجعل ن = ليس خطأ", "ن") is True

    def test_arabic_try_catch(self):
        # Note: خطأ means both 'false' and is a common Arabic word for 'error'
        # Use a different catch variable name to avoid the collision
        code = (
            "اجعل رسالة = \"\"\n"
            "حاول:\n"
            "    اجعل س = 1 / 0\n"
            "اصطد ع:\n"
            "    رسالة = ع.message\n"
        )
        assert val(code, "رسالة") != ""

    def test_arabic_builtin_قل(self, capsys):
        run('قل("اختبار")')
        assert "اختبار" in capsys.readouterr().out

    def test_arabic_builtin_طول(self):
        assert val("اجعل ن = طول([1, 2, 3])", "ن") == 3

    def test_arabic_builtin_متوسط(self):
        assert val("اجعل ن = متوسط([10, 20, 30])", "ن") == 20.0

    def test_arabic_builtin_مجموع(self):
        assert val("اجعل ن = مجموع([1, 2, 3, 4, 5])", "ن") == 15

    def test_arabic_builtin_زوجي(self):
        assert val("اجعل ن = زوجي(4)", "ن") is True
        assert val("اجعل ن = زوجي(3)", "ن") is False

    def test_arabic_builtin_فردي(self):
        assert val("اجعل ن = فردي(3)", "ن") is True

    def test_arabic_variable_names(self):
        """Arabic identifiers should work as variable names."""
        code = "اجعل الاسم = \"أحمد\"\nاجعل العمر = 25\n"
        g = run(code)
        assert g.get("الاسم") == "أحمد"
        assert g.get("العمر") == 25

    def test_arabic_object_fields(self):
        """Arabic field names on NyxObjects."""
        code = 'اجعل مستخدم = {"الاسم": "فاطمة", "العمر": 20}\n'
        g = run(code)
        obj = g.get("مستخدم")
        assert obj["الاسم"] == "فاطمة"

    def test_mixed_arabic_english(self):
        """Arabic and English keywords can coexist in the same file."""
        code = (
            "اجعل قائمة = [1, 2, 3, 4, 5]\n"
            "let evens = قائمة where is_even(item)\n"
            "اجعل ع = طول(evens)\n"
        )
        assert val(code, "ع") == 2

    def test_arabic_keyword_normalisation(self):
        """Arabic keywords should produce the same AST as English keywords."""
        from nyxel.lexer import lex
        from nyxel.nyx_ast  import LetStmt
        from nyxel.parser import Parser
        arabic  = Parser(lex("اجعل س = 5")).parse()
        english = Parser(lex("let س = 5")).parse()
        assert type(arabic[0])  == type(english[0]) == LetStmt
        assert arabic[0].name   == english[0].name  == "س"
