# Nyxel — Design Decisions

This document records the key design choices made for Nyxel, *why* they were
made, and what alternatives were consciously rejected.  Reading this before
adding a feature is mandatory.

---

## 1. Path A: Scripting Language (not performance language)

Nyxel is on **Path A**.  This is a deliberate, locked decision.

**Path A** — expressive scripting language
- Focus: ergonomics, readability, helpful errors
- Runtime: tree-walk interpreter (Python-backed)
- Target: automation, glue code, learning, small tools
- Speed: "fast enough for scripting"

**Path B** — performance language (rejected for now)
- Would require: bytecode VM, JIT, static analysis, dropping Python
- Would break: fast iteration, Python interop, simple embedding
- Timeline: possible in Stage 3/4, not now

**Consequence**: do not optimise the interpreter for speed.  Do not add
static types to improve performance.  Do not add a JIT.  If a user hits
a performance wall, the answer is `python: … end`, not a faster Nyxel.

The bytecode design in `nyxel/bytecode.py` is a *specification* for a
possible Stage 2.  It is not a priority.

---

## 2. Reference semantics for objects

NyxObjects use **reference semantics**.  Two variables pointing to the same
dict share it — mutations are visible to both.

```
let a = {"x": 1}
let b = a
b.x = 99
say(a.x)   # → 99
```

**Why**: consistent with Python and JS, which is what users already know.
Copying on every assignment would be surprising and expensive.

**Escape hatch**: `a.copy()` returns a shallow-copied independent object.

**Future**: when structs become more serious, we can add a `copy-on-write`
mode or an `immutable` keyword.  For now: objects are references.

---

## 3. `Param` namedtuple for function parameters

Function parameters are stored as `List[Param]` where `Param` is a
`NamedTuple(name: str, default: Optional[Node])`.

**Why**: the original code annotated params as `List[str]` but actually
stored `List[Tuple[str, Node|None]]`.  This caused silent breakage whenever
code assumed the simple type.  The `Param` namedtuple makes the structure
self-documenting and catches misuse at the point of access.

**Rule**: never create a raw `(name, default)` tuple for params.  Always
use `Param(name=..., default=...)`.

---

## 4. `when / otherwise` vs `if / elif / else`

Both work.  They produce identical AST nodes.  `when / otherwise` is the
Nyxel-idiomatic style; `if / elif / else` is kept as an alias.

**Why keep the alias**: removing `if` would break muscle memory without
adding clarity.  The alias costs nothing and makes the language less
surprising to Python users.

**Rule**: examples and documentation should prefer `when / otherwise`.
Tests may use either.

---

## 5. `fn` vs `def`

Both work.  Same rule as above.  `fn` is preferred in new Nyxel code.

---

## 6. REPL block detection is heuristic-based

The REPL uses a keyword + colon heuristic to detect block openers, not a
full parser.  See the comment in `nyxel/repl.py` for details and the
known limitation.

**Why not parser-based**: expensive, complicates error display, unnecessary
for current syntax.

**Upgrade trigger**: if Nyxel gains syntax where `:` can appear at end of
line without opening a block (decorators, inline dicts, lambdas), switch to
a lightweight pre-parse pass.

---

## 7. `NyxException` lives in `runtime.py`

`NyxException` is a runtime value (a `NyxObject` with `.kind` and `.message`
fields), not execution machinery.  It belongs in `runtime.py` alongside
`NyxObject`, not in `interpreter.py` alongside the execution engine.

When a VM layer is added, the VM will construct `NyxException` instances
at the runtime layer, just as the interpreter does now.

---

## 8. Module exports exclude built-ins

When a module is loaded via `bring`, only names *defined by the module*
are exported.  Built-in names (`say`, `get`, `len`, …) are available
inside the module during execution but are NOT re-exported.

**Why**: if built-ins were re-exported, `bring utils` would pollute the
caller's namespace with all of Nyxel's built-ins, making name collisions
unpredictable.

---

## 9. `where` uses reference-preserving item wrapping

`people where age >= 18` returns a new list, but the items in that list
are the *same* NyxObjects as in the original list (reference semantics).
Mutating a filtered item mutates the original.

This is consistent with rule 2 and consistent with how Python's `filter`
works.

---

## 10. Things that were deliberately removed

| Feature          | Reason removed |
|------------------|----------------|
| `\|>` pipe       | Too clever — decodes rather than reads |
| `?.` safe access | Too clever — adds symbol noise |
| `??` null coalesce | Too clever — use `when` instead |
| `->` arrow fn    | Inconsistent with `fn` style |
| `print` alias    | One output function — `say` |
| `import` keyword | `bring` is the Nyxel way |

**Rule**: don't add these back, even "just for compatibility."
