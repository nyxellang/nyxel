"""nyxel.compiler — transpile Nyxel AST to Python source."""

from .nyx_ast import (
    Node,
    LetStmt, AssignStmt, IfStmt, RepeatStmt, RepeatRangeStmt,
    ForStmt, WhileStmt,
    TryStmt, DefStmt, ReturnStmt, BreakStmt, ContinueStmt, PassStmt,
    ExprStmt, PyBlockStmt, BringStmt, BringFromStmt, StructStmt, AddToStmt,
    NumExpr, StrExpr, BoolExpr, NoneExpr,
    ListExpr, DictExpr, VarExpr,
    BinOpExpr, UnaryExpr, CallExpr, IndexExpr, SliceExpr, AttrExpr, PyBlockExpr,
    WhereExpr,
)
from .errors import NyxError
import textwrap


_NYX_TRUE = "True"
_NYX_FALSE = "False"
_NYX_NONE = "None"

_NYXEL_ATTR_PROPS = {
    "length": "__nyx_len",
    "is_empty": "__nyx_is_empty",
    "sorted": "__nyx_list_sorted",
    "reversed": "__nyx_list_reversed",
    "first": "__nyx_list_first",
    "last": "__nyx_list_last",
}

_NYXEL_METHOD_REWRITE = {
    "starts_with": "startswith",
    "ends_with": "endswith",
    "to_int": "__nyx_to_int",
    "to_float": "__nyx_to_float",
}


class Compiler:
    def __init__(self):
        self._indent = 0
        self._lines: list[str] = []

    def compile(self, stmts: list[Node]) -> str:
        self._lines = []
        self._indent = 0
        for stmt in stmts:
            self._stmt(stmt)
        return "\n".join(self._lines)

    def _line(self, code: str = ""):
        self._lines.append("    " * self._indent + code)

    def _stmt(self, node: Node):
        t = type(node)

        if t is LetStmt:
            self._line(f"{node.name} = {self._expr(node.expr)}")
            return

        if t is AssignStmt:
            target = node.target
            if target[0] == "var":
                self._line(f"{target[1]} = {self._expr(node.expr)}")
            elif target[0] == "index":
                obj = self._expr(target[1])
                idx = self._expr(target[2])
                self._line(f"{obj}[{idx}] = {self._expr(node.expr)}")
            elif target[0] == "attr":
                obj = self._expr(target[1])
                self._line(f"{obj}.{target[2]} = {self._expr(node.expr)}")
            return

        if t is IfStmt:
            self._line(f"if {self._expr(node.cond)}:")
            self._indent += 1
            for s in node.body:
                self._stmt(s)
            self._indent -= 1
            for ec, eb in node.elifs:
                self._line(f"elif {self._expr(ec)}:")
                self._indent += 1
                for s in eb:
                    self._stmt(s)
                self._indent -= 1
            if node.else_body:
                self._line("else:")
                self._indent += 1
                for s in node.else_body:
                    self._stmt(s)
                self._indent -= 1
            return

        if t is ForStmt:
            self._line(f"for {node.var} in {self._expr(node.iterable)}:")
            self._indent += 1
            for s in node.body:
                self._stmt(s)
            self._indent -= 1
            return

        if t is WhileStmt:
            self._line(f"while {self._expr(node.cond)}:")
            self._indent += 1
            for s in node.body:
                self._stmt(s)
            self._indent -= 1
            return

        if t is RepeatStmt:
            count = self._expr(node.count)
            var = node.as_var or "_"
            self._line(f"for {var} in range(int({count})):")
            self._indent += 1
            for s in node.body:
                self._stmt(s)
            self._indent -= 1
            return

        if t is RepeatRangeStmt:
            start = self._expr(node.start)
            end = self._expr(node.end)
            self._line(f"for {node.var} in range(int({start}), int({end}) + 1):")
            self._indent += 1
            for s in node.body:
                self._stmt(s)
            self._indent -= 1
            return

        if t is TryStmt:
            self._line("try:")
            self._indent += 1
            for s in node.body:
                self._stmt(s)
            self._indent -= 1
            if node.catch_body:
                self._line("except (_Return, _Break, _Continue):")
                self._indent += 1
                self._line("raise")
                self._indent -= 1
                if node.catch_var:
                    self._line("except Exception as __nyx_err:")
                    self._indent += 1
                    self._line(f"{node.catch_var} = NyxException(*__nyx_catch_convert(__nyx_err))")
                    for s in node.catch_body:
                        self._stmt(s)
                    self._indent -= 1
                else:
                    self._line("except Exception:")
                    self._indent += 1
                    for s in node.catch_body:
                        self._stmt(s)
                    self._indent -= 1
            if node.finally_body:
                self._line("finally:")
                self._indent += 1
                for s in node.finally_body:
                    self._stmt(s)
                self._indent -= 1
            return

        if t is DefStmt:
            params = ", ".join(
                p if d is None else f"{p}={self._expr(d)}"
                for p, d in node.params
            )
            self._line(f"def {node.name}({params}):")
            self._indent += 1
            for s in node.body:
                self._stmt(s)
            self._indent -= 1
            return

        if t is ReturnStmt:
            self._line(f"return {self._expr(node.expr)}")
            return

        if t is BreakStmt:
            self._line("break"); return

        if t is ContinueStmt:
            self._line("continue"); return

        if t is PassStmt:
            self._line("pass"); return

        if t is ExprStmt:
            self._line(self._expr(node.expr))
            return

        if t is PyBlockStmt:
            for line in node.code.split("\n"):
                self._line(line)
            return

        if t is BringStmt:
            self._line(f"{node.alias} = __nyx_bring__({node.module_name!r})")
            return

        if t is BringFromStmt:
            parts = ", ".join(f"{o!r}: {a!r}" for o, a in node.names)
            self._line(f"__nyx_bring_from__({node.module_name!r}, {{{parts}}})")
            return

        if t is StructStmt:
            fields = []
            defaults = {}
            for fname, default_expr in node.fields:
                fields.append(fname)
                if default_expr is not None:
                    defaults[fname] = default_expr
            fields_str = ", ".join(repr(f) for f in fields)
            defaults_str = ", ".join(
                f"{k!r}: {self._expr(v)}" for k, v in defaults.items()
            )
            self._line(f"{node.name} = __nyx_struct__({node.name!r}, [{fields_str}], {{{defaults_str}}})")
            return

        if t is AddToStmt:
            self._line(f"{node.list_name}.append({self._expr(node.value_expr)})")
            return

        raise NyxError("InternalError", f"Unknown statement: {type(node).__name__}")

    def _expr(self, node: Node) -> str:
        t = type(node)

        if t is NumExpr:
            return repr(node.v)

        if t is StrExpr:
            return repr(node.v)

        if t is BoolExpr:
            return _NYX_TRUE if node.v else _NYX_FALSE

        if t is NoneExpr:
            return _NYX_NONE

        if t is VarExpr:
            return node.name

        if t is ListExpr:
            items = ", ".join(self._expr(item) for item in node.items)
            return f"[{items}]"

        if t is DictExpr:
            pairs = ", ".join(
                f"{self._expr(k)}: {self._expr(v)}" for k, v in node.pairs
            )
            return f"NyxObject({{{pairs}}})"

        if t is BinOpExpr:
            l = self._expr(node.l)
            r = self._expr(node.r)
            if node.op in ("and", "or"):
                return f"({l} {node.op} {r})"
            if node.op == "in":
                return f"({l} in {r})"
            if node.op == "not in":
                return f"({l} not in {r})"
            return f"({l} {node.op} {r})"

        if t is UnaryExpr:
            e = self._expr(node.e)
            return f"({node.op} {e})"

        if t is CallExpr:
            args = ", ".join(self._expr(a) for a in node.args)
            if type(node.func) is AttrExpr and node.func.attr in _NYXEL_METHOD_REWRITE:
                mapping = _NYXEL_METHOD_REWRITE[node.func.attr]
                obj = self._expr(node.func.obj)
                if mapping == "__nyx_to_int":
                    return f"int({obj})"
                if mapping == "__nyx_to_float":
                    return f"float({obj})"
                return f"{obj}.{mapping}({args})"
            if type(node.func) is AttrExpr and node.func.attr == "contains":
                obj = self._expr(node.func.obj)
                arg = args
                return f"({arg} in {obj})"
            func = self._expr(node.func)
            return f"{func}({args})"

        if t is IndexExpr:
            obj = self._expr(node.obj)
            idx = self._expr(node.idx)
            return f"{obj}[{idx}]"

        if t is SliceExpr:
            obj = self._expr(node.obj)
            start = self._expr(node.start) if node.start is not None else ""
            end = self._expr(node.end) if node.end is not None else ""
            return f"{obj}[{start}:{end}]"

        if t is AttrExpr:
            obj = self._expr(node.obj)
            attr = node.attr
            if attr in _NYXEL_ATTR_PROPS:
                return f"{_NYXEL_ATTR_PROPS[attr]}({obj})"
            if attr == "copy":
                return f"{obj}.copy"
            return f"{obj}.{attr}"

        if t is PyBlockExpr:
            return f"__nyx_pyblock__({node.code!r})"

        if t is WhereExpr:
            return self._compile_where(node)

        raise NyxError("InternalError", f"Unknown expression: {type(node).__name__}")

    def _compile_where(self, node: WhereExpr) -> str:
        collection = self._expr(node.collection)
        condition = self._expr(node.condition)
        return f"__nyx_where__({collection}, {condition!r})"


def _body_nodes(node: Node) -> list:
    t = type(node)
    if t is IfStmt:
        result = list(node.body)
        for _, eb in node.elifs:
            result.extend(eb)
        if node.else_body:
            result.extend(node.else_body)
        return result
    if t is ForStmt: return list(node.body)
    if t is WhileStmt: return list(node.body)
    if t is RepeatStmt: return list(node.body)
    if t is RepeatRangeStmt: return list(node.body)
    if t is TryStmt:
        result = list(node.body)
        if node.catch_body:
            result.extend(node.catch_body)
        if node.finally_body:
            result.extend(node.finally_body)
        return result
    return []


def _collect_globals(stmts: list[Node]) -> set:
    names: set = set()
    def walk(nodes):
        for stmt in nodes:
            t = type(stmt)
            if t is DefStmt:
                names.add(stmt.name)
                continue
            if t is StructStmt:
                names.add(stmt.name)
                continue
            if t is LetStmt:
                names.add(stmt.name)
            elif t is AssignStmt and stmt.target[0] == "var":
                names.add(stmt.target[1])
            elif t is ForStmt:
                names.add(stmt.var)
            walk(_body_nodes(stmt))
    walk(stmts)
    return names


def _has_top_return(stmts: list[Node]) -> bool:
    """Check if any ReturnStmt exists at the top level (not inside functions/structs)."""
    def walk(nodes):
        for stmt in nodes:
            if isinstance(stmt, ReturnStmt):
                return True
            if isinstance(stmt, (DefStmt, StructStmt)):
                continue
            if walk(_body_nodes(stmt)):
                return True
        return False
    return walk(stmts)


def transpile(stmts: list[Node], source_name: str = "<input>") -> str:
    body = Compiler().compile(stmts)
    if _has_top_return(stmts):
        indented = textwrap.indent(body, "    ")
        gnames = _collect_globals(stmts)
        gdecl = f"    global {', '.join(sorted(gnames))}\n" if gnames else ""
        return (
            f"def __nyx_main__():\n"
            f"{gdecl}"
            f"{indented}\n"
            f"\n"
            f"__nyx_main__()\n"
        )
    return body
