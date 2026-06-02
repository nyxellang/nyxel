"""nyxel.ast"""


class Node:
    __slots__ = ()


# ══════════════════════════════════════════════════════════════════════════════
#  STATEMENTS
# ══════════════════════════════════════════════════════════════════════════════

class LetStmt(Node):
    __slots__ = ("name", "expr")
    def __init__(self, name, expr):
        self.name = name; self.expr = expr

class AssignStmt(Node):
    """
    target variants:
      ('var',   name)
      ('index', obj_expr, idx_expr)
      ('attr',  obj_expr, attr_str)
    """
    __slots__ = ("target", "expr")
    def __init__(self, target, expr):
        self.target = target; self.expr = expr

class IfStmt(Node):
    __slots__ = ("cond", "body", "elifs", "else_body")
    def __init__(self, cond, body, elifs, else_body):
        self.cond = cond; self.body = body
        self.elifs = elifs; self.else_body = else_body

class RepeatStmt(Node):
    __slots__ = ("count", "as_var", "body")
    def __init__(self, count, body, as_var=None):
        self.count  = count
        self.as_var = as_var
        self.body   = body

class RepeatRangeStmt(Node):
    __slots__ = ("var", "start", "end", "body")
    def __init__(self, var, start, end, body):
        self.var = var; self.start = start; self.end = end; self.body = body

class ForStmt(Node):
    __slots__ = ("var", "iterable", "body")
    def __init__(self, var, iterable, body):
        self.var = var; self.iterable = iterable; self.body = body

class WhileStmt(Node):
    __slots__ = ("cond", "body")
    def __init__(self, cond, body):
        self.cond = cond; self.body = body

class TryStmt(Node):
    __slots__ = ("body", "catch_var", "catch_body", "finally_body")
    def __init__(self, body, catch_var, catch_body, finally_body):
        self.body = body; self.catch_var = catch_var
        self.catch_body = catch_body; self.finally_body = finally_body

class DefStmt(Node):
    __slots__ = ("name", "params", "body")
    def __init__(self, name, params, body):
        self.name = name; self.params = params; self.body = body

class ReturnStmt(Node):
    __slots__ = ("expr",)
    def __init__(self, expr): self.expr = expr

class BreakStmt(Node):    __slots__ = ()
class ContinueStmt(Node): __slots__ = ()
class PassStmt(Node):     __slots__ = ()

class ExprStmt(Node):
    __slots__ = ("expr",)
    def __init__(self, expr): self.expr = expr

class PyBlockStmt(Node):
    __slots__ = ("code",)
    def __init__(self, code): self.code = code

class BringStmt(Node):
    __slots__ = ("module_name", "alias")
    def __init__(self, module_name, alias):
        self.module_name = module_name; self.alias = alias

class BringFromStmt(Node):
    __slots__ = ("module_name", "names")
    def __init__(self, module_name, names):
        self.module_name = module_name; self.names = names

class StructStmt(Node):
    __slots__ = ("name", "fields")
    def __init__(self, name, fields):
        self.name = name; self.fields = fields

class AddToStmt(Node):
    """add value to list_name  — sugar for list.append()"""
    __slots__ = ("value_expr", "list_name")
    def __init__(self, value_expr, list_name):
        self.value_expr = value_expr
        self.list_name  = list_name


class LabelStmt(Node):
    """N:  — a numeric label that goto can jump to."""
    __slots__ = ("target",)
    def __init__(self, target): self.target = target


class GotoStmt(Node):
    """goto N  — jump to label N."""
    __slots__ = ("target",)
    def __init__(self, target): self.target = target




# ══════════════════════════════════════════════════════════════════════════════
#  EXPRESSIONS
# ══════════════════════════════════════════════════════════════════════════════

class NumExpr(Node):
    __slots__ = ("v",)
    def __init__(self, v): self.v = v

class StrExpr(Node):
    __slots__ = ("v",)
    def __init__(self, v): self.v = v

class BoolExpr(Node):
    __slots__ = ("v",)
    def __init__(self, v): self.v = v

class NoneExpr(Node):
    __slots__ = ()

class ListExpr(Node):
    __slots__ = ("items",)
    def __init__(self, items): self.items = items

class DictExpr(Node):
    __slots__ = ("pairs",)
    def __init__(self, pairs): self.pairs = pairs

class VarExpr(Node):
    __slots__ = ("name",)
    def __init__(self, name): self.name = name

class BinOpExpr(Node):
    __slots__ = ("l", "op", "r")
    def __init__(self, l, op, r):
        self.l = l; self.op = op; self.r = r

class UnaryExpr(Node):
    __slots__ = ("op", "e")
    def __init__(self, op, e):
        self.op = op; self.e = e

class CallExpr(Node):
    __slots__ = ("func", "args")
    def __init__(self, func, args):
        self.func = func; self.args = args

class IndexExpr(Node):
    __slots__ = ("obj", "idx")
    def __init__(self, obj, idx):
        self.obj = obj; self.idx = idx

class SliceExpr(Node):
    __slots__ = ("obj", "start", "end")
    def __init__(self, obj, start, end):
        self.obj = obj; self.start = start; self.end = end

class AttrExpr(Node):
    __slots__ = ("obj", "attr")
    def __init__(self, obj, attr):
        self.obj = obj; self.attr = attr

class PyBlockExpr(Node):
    __slots__ = ("code",)
    def __init__(self, code): self.code = code

class WhereExpr(Node):
    """
    collection where condition

    'item' is the canonical name for the current element during the condition check.
    Fields of NyxObjects are also promoted into scope automatically.
    """
    __slots__ = ("collection", "condition")
    def __init__(self, collection, condition):
        self.collection = collection
        self.condition  = condition