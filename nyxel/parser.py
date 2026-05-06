"""
nyxel.parser
────────────
Recursive-descent parser.

New syntax in this version:
  when cond:               replaces  if cond:
  otherwise when cond:     replaces  elif cond:
  otherwise:               replaces  else:
  fn name(params):         replaces  def name(params):
  repeat n as i:           repeat with loop index
  repeat i from a to b:    range-based repeat
  collection where cond    list filtering expression

Classic  if / elif / else / def  remain valid — same AST, just aliases.

Operator precedence (low → high):
  where  →  or  →  and  →  not  →  comparison  →
  additive  →  multiplicative  →  unary  →  postfix  →  atom
"""

from typing import List, Optional

from .errors import NyxError
from .tokens import Token
from .ast import (
    Node,
    LetStmt, AssignStmt, IfStmt, RepeatStmt, RepeatRangeStmt,
    ForStmt, WhileStmt,
    TryStmt, DefStmt, ReturnStmt, BreakStmt, ContinueStmt, PassStmt,
    ExprStmt, PyBlockStmt, BringStmt, BringFromStmt, StructStmt, AddToStmt,
    NumExpr, StrExpr, BoolExpr, NoneExpr,
    ListExpr, DictExpr, VarExpr,
    BinOpExpr, UnaryExpr, CallExpr, IndexExpr, AttrExpr, PyBlockExpr,
    WhereExpr,
)


class Parser:

    def __init__(self, tokens: List[Token]):
        self._toks = tokens
        self._pos  = 0

    # ── navigation ────────────────────────────────────────────────────────────

    def _t(self) -> Token:
        return self._toks[self._pos] if self._pos < len(self._toks) else self._toks[-1]

    def _peek(self, n: int = 1) -> Token:
        i = self._pos + n
        return self._toks[i] if i < len(self._toks) else self._toks[-1]

    def _adv(self) -> Token:
        t = self._t()
        if self._pos < len(self._toks):
            self._pos += 1
        return t

    def _skip(self, *types: str):
        while self._t().type in types:
            self._adv()

    def _is_kw(self, *words: str) -> bool:
        return self._t().type == "KW" and self._t().value in words

    def _is_op(self, *ops: str) -> bool:
        return self._t().type == "OP" and self._t().value in ops

    def _is_p(self, *chars: str) -> bool:
        return self._t().type == "PUNCT" and self._t().value in chars

    # ── error helpers ─────────────────────────────────────────────────────────

    def _need_kw(self, word: str) -> Token:
        if not self._is_kw(word):
            t = self._t()
            raise NyxError("SyntaxError", f"Expected '{word}', got '{t.value}'",
                           t.line, t.col, t.raw,
                           hint=f"Write '{word}' here")
        return self._adv()
    # Keywords that can NEVER be used as names — they are structural syntax
    _RESERVED_NAMES = frozenset({
        "let", "when", "if", "elif", "else", "otherwise",
        "for", "in", "while", "repeat", "to",
        "try", "catch", "finally",
        "fn", "def", "return",
        "bring", "from", "as",
        "struct",
        "where",
        "and", "or", "not",
        "true", "false", "none",
        "python",
        "break", "continue", "pass",
        # Note: 'each' and 'add' are NOT here — they can be used as names
        # 'each' needs to work as a variable inside 'where' (item alias)
        # 'add' needs to work as a user-defined function name
    })

    def _need_id(self) -> str:
        t = self._t()
        # IDs are always fine
        if t.type == "ID":
            return self._adv().value
        # Some keywords can serve as identifiers (function/variable names)
        # when unambiguous — e.g.  fn is_empty():  or  let length = 5
        if t.type == "KW" and t.value not in self._RESERVED_NAMES:
            return self._adv().value
        raise NyxError("SyntaxError", f"Expected a name, got '{t.value}'",
                       t.line, t.col, t.raw,
                       "Names must start with a letter or underscore")

    def _need_p(self, ch: str) -> Token:
        if not self._is_p(ch):
            t = self._t()
            if ch == ":" and t.type in ("NL", "INDENT", "DEDENT", "EOF"):
                raise NyxError(
                    "SyntaxError",
                    "Missing ':' at the end of the line",
                    t.line, t.col, t.raw,
                    "Add ':' to open the block — e.g.  when x > 3:",
                )
            raise NyxError("SyntaxError", f"Expected '{ch}', got '{t.value}'",
                           t.line, t.col, t.raw, f"Add '{ch}' here")
        return self._adv()

    # ── top-level ─────────────────────────────────────────────────────────────

    def parse(self) -> List[Node]:
        stmts = []
        self._skip("NL", "DEDENT", "INDENT")
        while self._t().type != "EOF":
            s = self._stmt()
            if s is not None:
                stmts.append(s)
            self._skip("NL", "DEDENT")
        return stmts

    # ── indented block ────────────────────────────────────────────────────────

    def _block(self) -> List[Node]:
        stmts = []
        self._skip("NL")
        if self._t().type != "INDENT":
            t = self._t()
            raise NyxError("SyntaxError", "Expected an indented block",
                           t.line, t.col, t.raw, "Indent the body with spaces")
        self._adv()
        self._skip("NL")
        while self._t().type not in ("DEDENT", "EOF"):
            s = self._stmt()
            if s is not None:
                stmts.append(s)
            self._skip("NL")
        if self._t().type == "DEDENT":
            self._adv()
        return stmts

    # ── statements ────────────────────────────────────────────────────────────

    def _stmt(self) -> Optional[Node]:
        self._skip("NL", "DEDENT")
        t = self._t()

        if t.type in ("NL", "DEDENT", "EOF"):
            self._adv(); return None

        if t.type == "PYBLOCK":
            code = t.value; self._adv(); self._skip("NL")
            return PyBlockStmt(code)

        if t.type == "KW":
            v = t.value

            # ── conditionals: Nyxel style + classic aliases ──────────────────
            if v in ("when", "if"):       return self._when()

            # ── loops ────────────────────────────────────────────────────────
            if v == "repeat":             return self._repeat()
            if v == "for":                return self._for()
            if v == "while":              return self._while()

            # ── list helpers ──────────────────────────────────────────────────
            if v == "add":                return self._add_to()

            # ── error handling ────────────────────────────────────────────────
            if v == "try":                return self._try()

            # ── functions: Nyxel style + classic alias ────────────────────────
            if v in ("fn", "def"):        return self._fn()

            # ── modules ───────────────────────────────────────────────────────
            if v == "bring":              return self._bring()

            # ── structs ───────────────────────────────────────────────────────
            if v == "struct":             return self._struct()

            # ── other ─────────────────────────────────────────────────────────
            if v == "let":                return self._let()
            if v == "return":             return self._return()
            if v == "break":    self._adv(); self._skip("NL"); return BreakStmt()
            if v == "continue": self._adv(); self._skip("NL"); return ContinueStmt()
            if v == "pass":     self._adv(); self._skip("NL"); return PassStmt()

        return self._assign_or_expr()

    # ── let ───────────────────────────────────────────────────────────────────

    def _let(self) -> LetStmt:
        self._adv()
        name = self._need_id()
        if not self._is_op("="):
            t = self._t()
            raise NyxError("SyntaxError", "Expected '=' after variable name",
                           t.line, t.col, t.raw, "Write: let name = value")
        self._adv()
        expr = self._expr()
        self._skip("NL")
        return LetStmt(name, expr)

    # ── assignment or expression statement ────────────────────────────────────

    def _assign_or_expr(self) -> Node:
        if self._t().type == "ID":
            saved = self._pos
            name  = self._adv().value

            if self._is_op("="):
                self._adv()
                val = self._expr(); self._skip("NL")
                return AssignStmt(("var", name), val)

            if self._is_p("["):
                self._adv()
                idx = self._expr()
                if self._is_p("]"):
                    self._adv()
                    if self._is_op("="):
                        self._adv()
                        val = self._expr(); self._skip("NL")
                        return AssignStmt(("index", VarExpr(name), idx), val)
                self._pos = saved

            elif self._is_p("."):
                self._adv()
                if self._t().type in ("ID", "KW"):
                    attr = self._adv().value
                    if self._is_op("="):
                        self._adv()
                        val = self._expr(); self._skip("NL")
                        return AssignStmt(("attr", VarExpr(name), attr), val)
                self._pos = saved

            else:
                self._pos = saved

        expr = self._expr(); self._skip("NL")
        return ExprStmt(expr)

    # ── when / if ─────────────────────────────────────────────────────────────

    def _when(self) -> IfStmt:
        """
        Parse both Nyxel-style and classic conditionals:

          when x > 3:              if x > 3:
              ...                      ...
          otherwise when x == 3:   elif x == 3:
              ...                      ...
          otherwise:               else:
              ...                      ...
        """
        self._adv()                         # consume 'when' or 'if'
        cond = self._expr()
        self._need_p(":")
        body = self._block()
        elifs     = []
        else_body = []

        while True:
            # ── Nyxel style: otherwise when … / otherwise: ────────────────
            if self._is_kw("otherwise"):
                saved = self._pos
                self._adv()                 # consume 'otherwise'

                if self._is_kw("when"):
                    self._adv()             # consume 'when'
                    ec = self._expr()
                    self._need_p(":")
                    elifs.append((ec, self._block()))
                    continue

                if self._is_p(":"):
                    self._adv()             # consume ':'
                    else_body = self._block()
                    break

                # 'otherwise' not followed by 'when' or ':' → roll back
                self._pos = saved
                break

            # ── Classic alias: elif / else ─────────────────────────────────
            elif self._is_kw("elif"):
                self._adv()
                ec = self._expr()
                self._need_p(":")
                elifs.append((ec, self._block()))
                continue

            elif self._is_kw("else"):
                self._adv()
                self._need_p(":")
                else_body = self._block()
                break

            else:
                break

        return IfStmt(cond, body, elifs, else_body)

    # ── repeat ────────────────────────────────────────────────────────────────

    def _repeat(self) -> Node:
        """
        repeat 5:              — basic counted loop
        repeat 5 as i:         — counted loop, i = current index (0-based)
        repeat i from 1 to 5:  — range loop, i goes 1 … 5 inclusive
        """
        self._adv()                         # consume 'repeat'

        # Detect  repeat var from start to end:
        # Heuristic: next token is ID followed by 'from'
        if self._t().type == "ID" and \
           self._peek().type == "KW" and self._peek().value == "from":
            var   = self._adv().value       # consume var name
            self._need_kw("from")
            start = self._expr()
            self._need_kw("to")
            end   = self._expr()
            self._need_p(":")
            return RepeatRangeStmt(var, start, end, self._block())

        # Otherwise: repeat expr  [as var]:
        count  = self._expr()
        as_var = None

        if self._is_kw("as"):
            self._adv()                     # consume 'as'
            as_var = self._need_id()

        self._need_p(":")
        return RepeatStmt(count, self._block(), as_var=as_var)

    # ── for / for each ────────────────────────────────────────────────────────

    def _for(self) -> ForStmt:
        """
        Parse both:
            for x in list:       standard form
            for each x in list:  Nyxel preferred form — reads like English
        """
        self._adv()                         # consume 'for'

        # 'for each' — consume the 'each' keyword
        if self._is_kw("each"):
            self._adv()                     # consume 'each'

        var = self._need_id()
        self._need_kw("in")
        iterable = self._expr(); self._need_p(":")
        return ForStmt(var, iterable, self._block())

    # ── add … to ──────────────────────────────────────────────────────────────

    def _add_to(self) -> AddToStmt:
        """
        add value to list_name

        Natural-language sugar for appending to a list.
        Beginners shouldn't need to know about .append().

            let scores = []
            add 99 to scores
            add result to scores
        """
        self._adv()                         # consume 'add'
        value_expr = self._expr()
        self._need_kw("to")
        t = self._t()
        if t.type != "ID":
            raise NyxError("SyntaxError",
                           "Expected a list name after 'to'",
                           t.line, t.col, t.raw,
                           "Write:  add value to my_list")
        list_name = self._adv().value
        self._skip("NL")
        return AddToStmt(value_expr, list_name)

    # ── while ─────────────────────────────────────────────────────────────────

    def _while(self) -> WhileStmt:
        self._adv()
        cond = self._expr(); self._need_p(":")
        return WhileStmt(cond, self._block())

    # ── try / catch / finally ─────────────────────────────────────────────────

    def _try(self) -> TryStmt:
        self._adv()
        self._need_p(":")
        body = self._block()

        catch_var  = None
        catch_body = []
        if self._is_kw("catch"):
            self._adv()
            if self._t().type == "ID":
                catch_var = self._adv().value
            self._need_p(":")
            catch_body = self._block()

        finally_body = []
        if self._is_kw("finally"):
            self._adv()
            self._need_p(":")
            finally_body = self._block()

        if not catch_body and not finally_body:
            t = self._t()
            raise NyxError("SyntaxError",
                           "try block needs at least a catch or finally clause",
                           t.line, t.col, t.raw,
                           hint="Add  catch e:  to handle errors, or  finally:  to always run cleanup")

        return TryStmt(body, catch_var, catch_body, finally_body)

    # ── fn / def ──────────────────────────────────────────────────────────────

    def _fn(self) -> DefStmt:
        """
        Parse both:
            fn add(a, b):    (Nyxel style — preferred)
            def add(a, b):   (classic alias — still valid)
        """
        self._adv()                         # consume 'fn' or 'def'
        name = self._need_id()
        self._need_p("(")

        params = []
        while not self._is_p(")") and self._t().type != "EOF":
            pname   = self._need_id()
            default = None
            if self._is_op("="):
                self._adv()
                default = self._expr()
            params.append((pname, default))
            if self._is_p(","):
                self._adv()

        self._need_p(")")
        self._need_p(":")
        return DefStmt(name, params, self._block())

    # ── bring ─────────────────────────────────────────────────────────────────

    def _bring(self) -> Node:
        self._adv()

        t = self._t()
        if t.type not in ("ID", "KW"):
            raise NyxError("SyntaxError", "Expected a name after 'bring'",
                           t.line, t.col, t.raw,
                           hint="Write: bring module_name  or  bring name from module")

        names = []
        while True:
            orig  = self._adv().value
            alias = orig
            if self._is_kw("as"):
                self._adv()
                alias = self._need_id()
            names.append((orig, alias))
            if not self._is_p(","):
                break
            self._adv()

        if self._is_kw("from"):
            self._adv()
            t = self._t()
            if t.type not in ("ID", "KW"):
                raise NyxError("SyntaxError", "Expected module name after 'from'",
                               t.line, t.col, t.raw,
                               hint="Write:  bring add from math_utils")
            module_name = self._adv().value
            self._skip("NL")
            return BringFromStmt(module_name, names)

        if len(names) > 1:
            raise NyxError("SyntaxError",
                           "Use  bring name from module  to bring multiple names",
                           hint="Write: bring add, multiply from math_utils")
        module_name, alias = names[0]
        self._skip("NL")
        return BringStmt(module_name, alias)

    # ── struct ────────────────────────────────────────────────────────────────

    def _struct(self) -> StructStmt:
        self._adv()
        name = self._need_id()
        self._need_p(":")
        self._skip("NL")

        if self._t().type != "INDENT":
            t = self._t()
            raise NyxError("SyntaxError", "struct body must be indented",
                           t.line, t.col, t.raw,
                           hint="Indent the field names below the struct declaration")
        self._adv()
        self._skip("NL")

        fields = []
        while self._t().type not in ("DEDENT", "EOF"):
            self._skip("NL")
            if self._t().type in ("DEDENT", "EOF"):
                break
            t = self._t()
            if t.type not in ("ID", "KW"):
                raise NyxError("SyntaxError",
                               f"Expected a field name, got '{t.value}'",
                               t.line, t.col, t.raw,
                               hint="Field names must start with a letter:  name  age  score")
            fname   = self._adv().value
            default = None
            if self._is_op("="):
                self._adv()
                default = self._expr()
            fields.append((fname, default))
            self._skip("NL")

        if self._t().type == "DEDENT":
            self._adv()

        return StructStmt(name, fields)

    # ── return ────────────────────────────────────────────────────────────────

    def _return(self) -> ReturnStmt:
        self._adv()
        if self._t().type in ("NL", "EOF", "DEDENT"):
            return ReturnStmt(NoneExpr())
        expr = self._expr(); self._skip("NL")
        return ReturnStmt(expr)

    # ══════════════════════════════════════════════════════════════════════════
    #  EXPRESSION HIERARCHY  (precedence low → high)
    # ══════════════════════════════════════════════════════════════════════════

    def _expr(self) -> Node:
        return self._where()

    # ── where (lowest precedence — wraps a whole expression) ─────────────────

    def _where(self) -> Node:
        """
        collection where condition

        The condition is evaluated for each item in the collection.
        Item fields are automatically in scope.

            let adults = people where age >= 18
            let active = users where active == true and score > 50
        """
        left = self._or()
        if self._is_kw("where"):
            self._adv()
            condition = self._or()          # condition has same precedence as or
            return WhereExpr(left, condition)
        return left

    def _or(self) -> Node:
        left = self._and()
        while self._is_kw("or"):
            self._adv()
            left = BinOpExpr(left, "or", self._and())
        return left

    def _and(self) -> Node:
        left = self._not()
        while self._is_kw("and"):
            self._adv()
            left = BinOpExpr(left, "and", self._not())
        return left

    def _not(self) -> Node:
        if self._is_kw("not"):
            self._adv()
            return UnaryExpr("not", self._not())
        return self._cmp()

    def _cmp(self) -> Node:
        left = self._add()
        CMP  = {"==", "!=", "<", ">", "<=", ">="}
        while True:
            if self._t().type == "OP" and self._t().value in CMP:
                op = self._adv().value
                left = BinOpExpr(left, op, self._add())
            elif self._is_kw("in"):
                self._adv()
                left = BinOpExpr(left, "in", self._add())
            elif (self._is_kw("not") and
                  self._peek().type == "KW" and self._peek().value == "in"):
                self._adv(); self._adv()
                left = BinOpExpr(left, "not in", self._add())
            else:
                break
        return left

    def _add(self) -> Node:
        left = self._mul()
        while self._t().type == "OP" and self._t().value in ("+", "-"):
            op = self._adv().value
            left = BinOpExpr(left, op, self._mul())
        return left

    def _mul(self) -> Node:
        left = self._unary()
        while self._t().type == "OP" and self._t().value in ("*", "/", "//", "%", "**"):
            op = self._adv().value
            left = BinOpExpr(left, op, self._unary())
        return left

    def _unary(self) -> Node:
        if self._is_op("-"):
            self._adv(); return UnaryExpr("-", self._unary())
        if self._is_kw("not"):
            self._adv(); return UnaryExpr("not", self._unary())
        return self._postfix()

    def _postfix(self) -> Node:
        node = self._atom()
        while True:
            if self._is_p("["):
                self._adv()
                idx = self._expr(); self._need_p("]")
                node = IndexExpr(node, idx)
            elif self._is_p("."):
                self._adv()
                attr = self._t().value; self._adv()
                if self._is_p("("):
                    self._adv()
                    args = self._call_args()
                    node = CallExpr(AttrExpr(node, attr), args)
                else:
                    node = AttrExpr(node, attr)
            elif self._is_p("("):
                self._adv()
                args = self._call_args()
                node = CallExpr(node, args)
            else:
                break
        return node

    def _call_args(self) -> list:
        args = []
        while not self._is_p(")") and self._t().type != "EOF":
            args.append(self._expr())
            if self._is_p(","):
                self._adv()
        self._need_p(")")
        return args

    def _atom(self) -> Node:
        t = self._t()

        if t.type == "PYBLOCK":
            self._adv(); return PyBlockExpr(t.value)
        if t.type == "NUM":
            self._adv(); return NumExpr(t.value)
        if t.type == "STR":
            self._adv(); return StrExpr(t.value)

        if t.type == "KW":
            v = t.value
            if v == "true":  self._adv(); return BoolExpr(True)
            if v == "false": self._adv(); return BoolExpr(False)
            if v == "none":  self._adv(); return NoneExpr()

        if t.type == "ID":
            self._adv(); return VarExpr(t.value)

        # Non-reserved keywords can also be used as variable names in expressions
        # e.g.  return add  when 'add' is a function defined by the user
        if t.type == "KW" and t.value not in self._RESERVED_NAMES:
            self._adv(); return VarExpr(t.value)

        if self._is_p("["):
            self._adv()
            items = []
            self._skip("NL", "INDENT", "DEDENT")
            while not self._is_p("]") and self._t().type != "EOF":
                items.append(self._expr())
                self._skip("NL", "INDENT", "DEDENT")
                if self._is_p(","):
                    self._adv()
                    self._skip("NL", "INDENT", "DEDENT")
            self._need_p("]")
            return ListExpr(items)

        if self._is_p("{"):
            self._adv()
            pairs = []
            self._skip("NL", "INDENT", "DEDENT")
            while not self._is_p("}") and self._t().type != "EOF":
                key = self._expr(); self._need_p(":"); val = self._expr()
                pairs.append((key, val))
                self._skip("NL", "INDENT", "DEDENT")
                if self._is_p(","):
                    self._adv()
                    self._skip("NL", "INDENT", "DEDENT")
            self._need_p("}")
            return DictExpr(pairs)

        if self._is_p("("):
            self._adv(); e = self._expr(); self._need_p(")"); return e

        raise NyxError("SyntaxError", f"Unexpected token '{t.value}'",
                       t.line, t.col, t.raw,
                       "Expected a value, variable name, or expression")
