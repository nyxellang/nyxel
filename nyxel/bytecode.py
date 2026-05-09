"""
nyxel.bytecode
"""

from enum import IntEnum, auto


# ══════════════════════════════════════════════════════════════════════════════
#  INSTRUCTION SET
# ══════════════════════════════════════════════════════════════════════════════

class Op(IntEnum):
    """
    Nyxel instruction set.

    Each instruction is stored as:
        [op: uint8,  arg: uint16]   (3 bytes per inst)

    arg is an index into the constant pool, name pool, or a jump offset,
    depending on the instruction.  Instructions that don't need an arg
    set arg = 0.
    """

    # ── stack / constants ─────────────────────────────────────────────────────
    LOAD_CONST    = auto()  # arg = const_pool index  → push constant
    LOAD_NONE     = auto()  # arg = 0                 → push None
    LOAD_TRUE     = auto()  # arg = 0                 → push True
    LOAD_FALSE    = auto()  # arg = 0                 → push False
    POP           = auto()  # arg = 0                 → discard top of stack

    # ── variables ─────────────────────────────────────────────────────────────
    LOAD          = auto()  # arg = name_pool index   → push value of variable
    STORE         = auto()  # arg = name_pool index   → pop → store in scope
    DEFINE        = auto()  # arg = name_pool index   → pop → define in scope (let)
    LOAD_ATTR     = auto()  # arg = name_pool index   → pop obj → push obj.attr
    STORE_ATTR    = auto()  # arg = name_pool index   → pop val, obj → obj.attr = val
    LOAD_INDEX    = auto()  # arg = 0                 → pop idx, obj → push obj[idx]
    STORE_INDEX   = auto()  # arg = 0                 → pop val, idx, obj → obj[idx]=val

    # ── arithmetic & comparison ───────────────────────────────────────────────
    BIN_OP        = auto()  # arg = Op index into _BIN_OPS  → pop r,l → push result
    UNARY_OP      = auto()  # arg = 0=neg / 1=not            → pop → push result
    UNARY_NEG     = auto()  # arg = 0                         → pop n → push -n
    UNARY_NOT     = auto()  # arg = 0                         → pop b → push not b

    # ── function calls ────────────────────────────────────────────────────────
    CALL          = auto()  # arg = argc               → pop argc args + callable → push result
    CALL_BUILTIN  = auto()  # arg = name_pool index    → pop argc args → push result
    RETURN        = auto()  # arg = 0                  → pop → exit function
    RETURN_NONE   = auto()  # arg = 0                  → push None → exit function

    # ── collections ───────────────────────────────────────────────────────────
    BUILD_LIST    = auto()  # arg = item_count         → pop N items → push [...]
    BUILD_DICT    = auto()  # arg = pair_count         → pop 2N items → push {...}

    # ── control flow ─────────────────────────────────────────────────────────
    JUMP          = auto()  # arg = target offset      → unconditional jump
    JUMP_IF_FALSE = auto()  # arg = target offset      → pop; jump if falsy
    JUMP_IF_TRUE  = auto()  # arg = target offset      → pop; jump if truthy
    LOOP_START    = auto()  # arg = iter_name index    → prepare iterator
    LOOP_NEXT     = auto()  # arg = exit_offset        → advance iterator or jump
    LOOP_END      = auto()  # arg = 0                  → clean up iterator

    # ── error handling ────────────────────────────────────────────────────────
    TRY_START     = auto()  # arg = catch_offset       → push exception handler
    TRY_END       = auto()  # arg = 0                  → pop exception handler
    RAISE         = auto()  # arg = 0                  → pop NyxException → raise
    CATCH_STORE   = auto()  # arg = name_pool index    → bind caught exception to name

    # ── modules ───────────────────────────────────────────────────────────────
    BRING         = auto()  # arg = name_pool index    → load module → push namespace
    BRING_FROM    = auto()  # arg = name_pool index    → load module → push specific name

    # ── structs ───────────────────────────────────────────────────────────────
    BUILD_STRUCT  = auto()  # arg = name_pool index    → pop fields → push NyxStruct

    # ── python escape hatch ───────────────────────────────────────────────────
    PY_EXEC       = auto()  # arg = const_pool index (code str) → execute Python block
    PY_EVAL       = auto()  # arg = const_pool index (code str) → execute → push result

    # ── debug / display ───────────────────────────────────────────────────────
    PRINT_EXPR    = auto()  # arg = 0  → peek top → print if not None (REPL mode)


# Operator codes used as the 'arg' of BIN_OP
_BIN_OPS = ["+", "-", "*", "/", "//", "%", "**",
            "==", "!=", "<", ">", "<=", ">=",
            "and", "or", "in", "not in"]


# ══════════════════════════════════════════════════════════════════════════════
#  INSTRUCTION  (single compiled instruction)
# ══════════════════════════════════════════════════════════════════════════════

class Instruction:
    """One compiled instruction with its opcode, argument, and source line."""
    __slots__ = ("op", "arg", "line")

    def __init__(self, op: Op, arg: int = 0, line: int = 0):
        self.op   = op
        self.arg  = arg
        self.line = line

    def __repr__(self) -> str:
        return f"{self.op.name:<16}  {self.arg}"


# ══════════════════════════════════════════════════════════════════════════════
#  CODE OBJECT  (compiled unit — function, module, or block)
# ══════════════════════════════════════════════════════════════════════════════

class CodeObject:
    """
    The result of compiling one Nyxel scope (module, function body, etc.).

    const_pool  — list of literal values (strings, numbers)
    name_pool   — list of variable/attribute names (strings)
    instructions — ordered list of Instruction objects
    """

    def __init__(self, name: str = "<module>"):
        self.name         : str            = name
        self.const_pool   : list           = []
        self.name_pool    : list           = []
        self.instructions : list           = []

    def add_const(self, val) -> int:
        """Intern a constant and return its pool index."""
        if val not in self.const_pool:
            self.const_pool.append(val)
        return self.const_pool.index(val)

    def add_name(self, name: str) -> int:
        """Intern a name and return its pool index."""
        if name not in self.name_pool:
            self.name_pool.append(name)
        return self.name_pool.index(name)

    def emit(self, op: Op, arg: int = 0, line: int = 0) -> int:
        """Append an instruction and return its index."""
        self.instructions.append(Instruction(op, arg, line))
        return len(self.instructions) - 1

    def patch(self, idx: int, arg: int) -> None:
        """Back-patch a jump target once the destination is known."""
        self.instructions[idx].arg = arg

    def disassemble(self) -> str:
        """Return a human-readable listing of the bytecode."""
        lines = [f"  CodeObject '{self.name}'",
                 f"  constants : {self.const_pool}",
                 f"  names     : {self.name_pool}",
                 "  ─" * 20]
        for i, ins in enumerate(self.instructions):
            line_info = f"L{ins.line:3}" if ins.line else "    "
            lines.append(f"  {i:4}  {line_info}  {ins.op.name:<18}  {ins.arg}")
        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
#  COMPILER  (AST → CodeObject)  — SKELETON
# ══════════════════════════════════════════════════════════════════════════════

class Compiler:
    """
    Walks the AST and emits bytecode instructions.

    Status: DESIGN ONLY not yet working.

    Usage (future):
        from nyxel.bytecode import Compiler
        compiler = Compiler()
        code = compiler.compile(stmts)
        vm = VM(code)
        vm.run()
    """

    def __init__(self):
        self._code: CodeObject = CodeObject()

    def compile(self, stmts: list) -> CodeObject:
        """Compile a list of statement nodes into a CodeObject."""
        for stmt in stmts:
            self._stmt(stmt)
        return self._code

    # ── statement dispatch ────────────────────────────────────────────────────

    def _stmt(self, node) -> None:
        nn = type(node).__name__

        if nn == "LetStmt":
            self._expr(node.expr)
            idx = self._code.add_name(node.name)
            self._code.emit(Op.DEFINE, idx, node.expr)

        elif nn == "AssignStmt":
            self._expr(node.expr)
            if node.target[0] == "var":
                idx = self._code.add_name(node.target[1])
                self._code.emit(Op.STORE, idx)
            elif node.target[0] == "index":
                self._expr(node.target[1])
                self._expr(node.target[2])
                self._code.emit(Op.STORE_INDEX)
            elif node.target[0] == "attr":
                self._expr(node.target[1])
                idx = self._code.add_name(node.target[2])
                self._code.emit(Op.STORE_ATTR, idx)

        elif nn == "SayStmt":          # convenience wrapper for ExprStmt(CallExpr(say,...))
            self._expr(node.expr)
            self._code.emit(Op.POP)

        elif nn == "ExprStmt":
            self._expr(node.expr)
            self._code.emit(Op.POP)

        elif nn == "ReturnStmt":
            self._expr(node.expr)
            self._code.emit(Op.RETURN)

        elif nn == "IfStmt":
            self._compile_if(node)

        elif nn == "WhileStmt":
            self._compile_while(node)

        elif nn == "ForStmt":
            self._compile_for(node)

        elif nn == "RepeatStmt":
            self._compile_repeat(node)

        elif nn == "DefStmt":
            self._compile_def(node)

        elif nn == "BringStmt":
            idx = self._code.add_name(node.module_name)
            self._code.emit(Op.BRING, idx)
            name_idx = self._code.add_name(node.alias)
            self._code.emit(Op.DEFINE, name_idx)

        elif nn == "BreakStmt":
            # Emit a JUMP that will be back-patched by the enclosing loop
            self._code.emit(Op.JUMP, 0)   # placeholder

        elif nn == "ContinueStmt":
            self._code.emit(Op.JUMP, 0)   # placeholder — back-patched

        elif nn == "PassStmt":
            pass  # no instruction needed

        elif nn == "TryStmt":
            self._compile_try(node)

        elif nn == "PyBlockStmt":
            idx = self._code.add_const(node.code)
            self._code.emit(Op.PY_EXEC, idx)

    # ── expression dispatch ───────────────────────────────────────────────────

    def _expr(self, node) -> None:
        nn = type(node).__name__

        if nn == "NumExpr":
            idx = self._code.add_const(node.v)
            self._code.emit(Op.LOAD_CONST, idx)

        elif nn == "StrExpr":
            idx = self._code.add_const(node.v)
            self._code.emit(Op.LOAD_CONST, idx)

        elif nn == "BoolExpr":
            self._code.emit(Op.LOAD_TRUE if node.v else Op.LOAD_FALSE)

        elif nn == "NoneExpr":
            self._code.emit(Op.LOAD_NONE)

        elif nn == "VarExpr":
            idx = self._code.add_name(node.name)
            self._code.emit(Op.LOAD, idx)

        elif nn == "ListExpr":
            for item in node.items:
                self._expr(item)
            self._code.emit(Op.BUILD_LIST, len(node.items))

        elif nn == "DictExpr":
            for k, v in node.pairs:
                self._expr(k); self._expr(v)
            self._code.emit(Op.BUILD_DICT, len(node.pairs))

        elif nn == "BinOpExpr":
            # Short-circuit 'and'/'or' need jumps — simplified here
            self._expr(node.l)
            self._expr(node.r)
            op_idx = _BIN_OPS.index(node.op) if node.op in _BIN_OPS else 0
            self._code.emit(Op.BIN_OP, op_idx)

        elif nn == "UnaryExpr":
            self._expr(node.e)
            self._code.emit(Op.UNARY_NEG if node.op == "-" else Op.UNARY_NOT)

        elif nn == "CallExpr":
            for arg in node.args:
                self._expr(arg)
            self._expr(node.func)
            self._code.emit(Op.CALL, len(node.args))

        elif nn == "IndexExpr":
            self._expr(node.obj)
            self._expr(node.idx)
            self._code.emit(Op.LOAD_INDEX)

        elif nn == "AttrExpr":
            self._expr(node.obj)
            idx = self._code.add_name(node.attr)
            self._code.emit(Op.LOAD_ATTR, idx)

        elif nn == "PyBlockExpr":
            idx = self._code.add_const(node.code)
            self._code.emit(Op.PY_EVAL, idx)

    # ── control-flow helpers ──────────────────────────────────────────────────

    def _compile_if(self, node) -> None:
        self._expr(node.cond)
        jump_false = self._code.emit(Op.JUMP_IF_FALSE, 0)   # placeholder

        for stmt in node.body:
            self._stmt(stmt)

        jump_end = self._code.emit(Op.JUMP, 0)               # placeholder

        # Patch the false jump to here (start of else/end)
        self._code.patch(jump_false, len(self._code.instructions))

        for ec, eb in node.elifs:
            self._expr(ec)
            j = self._code.emit(Op.JUMP_IF_FALSE, 0)
            for s in eb: self._stmt(s)
            je = self._code.emit(Op.JUMP, 0)
            self._code.patch(j, len(self._code.instructions))
            jump_end = je   # keep patching the latest end jump

        for stmt in node.else_body:
            self._stmt(stmt)

        self._code.patch(jump_end, len(self._code.instructions))

    def _compile_while(self, node) -> None:
        loop_start = len(self._code.instructions)
        self._expr(node.cond)
        jump_false = self._code.emit(Op.JUMP_IF_FALSE, 0)
        for stmt in node.body:
            self._stmt(stmt)
        self._code.emit(Op.JUMP, loop_start)
        self._code.patch(jump_false, len(self._code.instructions))

    def _compile_for(self, node) -> None:
        self._expr(node.iterable)
        idx = self._code.add_name(node.var)
        loop_next = self._code.emit(Op.LOOP_NEXT, 0)   # exit placeholder
        self._code.emit(Op.STORE, idx)
        for stmt in node.body:
            self._stmt(stmt)
        self._code.emit(Op.JUMP, loop_next)
        self._code.patch(loop_next, len(self._code.instructions))
        self._code.emit(Op.LOOP_END)

    def _compile_repeat(self, node) -> None:
        # Emit a counted loop: push count, count down to 0
        self._expr(node.count)
        loop_start = len(self._code.instructions)
        self._code.emit(Op.LOAD_CONST, self._code.add_const(0))
        self._code.emit(Op.BIN_OP, _BIN_OPS.index(">"))
        jump_false = self._code.emit(Op.JUMP_IF_FALSE, 0)
        for stmt in node.body:
            self._stmt(stmt)
        # Decrement counter
        self._code.emit(Op.LOAD_CONST, self._code.add_const(1))
        self._code.emit(Op.BIN_OP, _BIN_OPS.index("-"))
        self._code.emit(Op.JUMP, loop_start)
        self._code.patch(jump_false, len(self._code.instructions))
        self._code.emit(Op.POP)   # discard final counter

    def _compile_def(self, node) -> None:
        # In the full implementation, compile the body into a nested CodeObject
        # and emit MAKE_FUNCTION.  Stubbed here.
        pass

    def _compile_try(self, node) -> None:
        catch_placeholder = self._code.emit(Op.TRY_START, 0)
        for stmt in node.body:
            self._stmt(stmt)
        self._code.emit(Op.TRY_END)
        jump_end = self._code.emit(Op.JUMP, 0)
        self._code.patch(catch_placeholder, len(self._code.instructions))
        if node.catch_var:
            idx = self._code.add_name(node.catch_var)
            self._code.emit(Op.CATCH_STORE, idx)
        for stmt in node.catch_body:
            self._stmt(stmt)
        self._code.patch(jump_end, len(self._code.instructions))
        for stmt in node.finally_body:
            self._stmt(stmt)


# ══════════════════════════════════════════════════════════════════════════════
#  VIRTUAL MACHINE  — SKELETON
# ══════════════════════════════════════════════════════════════════════════════

class VM:
    """
    Stack-based virtual machine for executing Nyxel bytecode.

    Status: DESIGN ONLY — not yet connected to the runtime.

    The VM maintains:
      stack      — operand stack (list used as a stack)
      call_stack — list of (CodeObject, instruction pointer, local_vars)
      globals    — module-level variable dict
    """

    def __init__(self, code: CodeObject, globals_: dict = None):
        self._code    = code
        self._stack   : list = []
        self._globals : dict = globals_ or {}
        self._ip      : int  = 0            # instruction pointer

    def run(self):
        """
        Main dispatch loop.

        In production this becomes:
            while True:
                ins = fetch()
                match ins.op:
                    case Op.LOAD_CONST: ...
                    case Op.BIN_OP: ...
                    ...
        """
        while self._ip < len(self._code.instructions):
            ins = self._code.instructions[self._ip]
            self._ip += 1
            self._dispatch(ins)

    def _dispatch(self, ins: Instruction) -> None:
        op = ins.op

        if op == Op.LOAD_CONST:
            self._stack.append(self._code.const_pool[ins.arg])

        elif op == Op.LOAD_NONE:  self._stack.append(None)
        elif op == Op.LOAD_TRUE:  self._stack.append(True)
        elif op == Op.LOAD_FALSE: self._stack.append(False)

        elif op == Op.POP:
            self._stack.pop()

        elif op == Op.LOAD:
            name = self._code.name_pool[ins.arg]
            self._stack.append(self._globals.get(name))

        elif op == Op.STORE:
            name = self._code.name_pool[ins.arg]
            self._globals[name] = self._stack.pop()

        elif op == Op.DEFINE:
            name = self._code.name_pool[ins.arg]
            self._globals[name] = self._stack.pop()

        elif op == Op.BIN_OP:
            r = self._stack.pop()
            l = self._stack.pop()
            op_str = _BIN_OPS[ins.arg]
            self._stack.append(self._eval_binop(op_str, l, r))

        elif op == Op.UNARY_NEG:
            self._stack.append(-self._stack.pop())

        elif op == Op.UNARY_NOT:
            self._stack.append(not self._stack.pop())

        elif op == Op.JUMP:
            self._ip = ins.arg

        elif op == Op.JUMP_IF_FALSE:
            if not self._stack.pop():
                self._ip = ins.arg

        elif op == Op.JUMP_IF_TRUE:
            if self._stack.pop():
                self._ip = ins.arg

        elif op == Op.BUILD_LIST:
            items = [self._stack.pop() for _ in range(ins.arg)]
            self._stack.append(list(reversed(items)))

        elif op == Op.BUILD_DICT:
            pairs = [(self._stack.pop(), self._stack.pop())
                     for _ in range(ins.arg)]
            self._stack.append(dict(reversed(pairs)))


    @staticmethod
    def _eval_binop(op: str, l, r):
        ops = {
            "+": lambda a, b: a + b,  "-": lambda a, b: a - b,
            "*": lambda a, b: a * b,  "/": lambda a, b: a / b,
            "//": lambda a, b: a // b, "%": lambda a, b: a % b,
            "**": lambda a, b: a ** b, "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b, "<":  lambda a, b: a < b,
            ">":  lambda a, b: a > b,  "<=": lambda a, b: a <= b,
            ">=": lambda a, b: a >= b, "in": lambda a, b: a in b,
        }
        return ops.get(op, lambda a, b: None)(l, r)

