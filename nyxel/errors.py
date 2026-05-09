"""
nyxel.errors
────────────
NyxError  — user-facing language error with source location, display, and hint.
_Return, _Break, _Continue  — internal control-flow signals (not errors).

Every error should answer three questions:
  1. What went wrong?     (kind + message)
  2. Where did it happen? (line + source line + caret)
  3. What should I do?    (hint)

"""

import difflib


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN ERROR CLASS
# ══════════════════════════════════════════════════════════════════════════════

class NyxError(Exception):
    """
    A language-level error.

    Attributes
    ──────────
    kind   e.g. "NameError", "TypeError", "SyntaxError"
    msg    Human-readable explanation (no jargon).
    line   1-based source line (0 = unknown).
    col    1-based column (0 = unknown).
    raw    The original source line (shown with a caret pointer).
    hint   What the user should do next.
    """

    def __init__(
        self,
        kind : str,
        msg  : str,
        line : int = 0,
        col  : int = 0,
        raw  : str = "",
        hint : str = "",
    ):
        self.kind = kind
        self.msg  = msg
        self.line = line
        self.col  = col
        self.raw  = raw
        self.hint = hint
        super().__init__(self._fmt())

    def _fmt(self) -> str:
        bar = "─" * 60
        out = f"\n{bar}\n  {self.kind}"
        if self.line:
            out += f"  (line {self.line})"
        if self.col:
            out += f", col {self.col}"
        out += f"\n{bar}\n"

        if self.raw:
            out += f"  {self.raw.strip()}\n"
            if self.col > 0:
                out += f"  {' ' * (self.col - 1)}^\n"

        out += f"\n  {self.msg}\n"

        if self.hint:
            out += f"\n  → {self.hint}\n"

        return out + f"{bar}\n"

    def __repr__(self) -> str:          # pragma: no cover
        return f"NyxError({self.kind!r}, {self.msg!r})"


# ══════════════════════════════════════════════════════════════════════════════
#  SUGGESTION HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def suggest_name(name: str, known: list, cutoff: float = 0.6) -> str:
    """
    Return "Did you mean 'X'?" if a close enough match exists.
    Returns "" if nothing is close enough to suggest.
    """
    if not known:
        return ""
    matches = difflib.get_close_matches(name, known, n=1, cutoff=cutoff)
    return f"Did you mean '{matches[0]}'?" if matches else ""


def suggest_attr(attr: str, obj_fields: list) -> str:
    """
    Return a field suggestion when dot-access fails on a NyxObject.

    - Close match  → "Did you mean '.name'?"
    - No match     → "Available fields: 'name', 'age', …"
    - Empty object → "This object has no fields."
    """
    if not obj_fields:
        return "This object has no fields."

    matches = difflib.get_close_matches(attr, obj_fields, n=1, cutoff=0.55)
    if matches:
        return f"Did you mean '.{matches[0]}'?"

    shown = obj_fields[:6]
    more  = len(obj_fields) - len(shown)
    names = ", ".join(f"'{f}'" for f in shown)
    if more:
        names += f"  (+{more} more)"
    return f"Available fields: {names}"


def suggest_callable(name: str, known: list) -> str:
    """
    Suggest the right Nyxel name for common mistakes.

    Checks a hard-coded alias table first (print → say, etc.),
    then falls back to fuzzy matching.
    """
    # Hard-coded: these are so common they deserve a specific message
    KNOWN_ALIASES = {
        "print" : "say",
        "echo"  : "say",
        "input" : "ask  (not built-in — read from a file or pass as an arg)",
        "import": "bring",
        "lambda": "fn",
        "class" : "struct",
    }
    if name in KNOWN_ALIASES:
        return f"In Nyxel, use '{KNOWN_ALIASES[name]}' instead"

    matches = difflib.get_close_matches(name, known, n=1, cutoff=0.55)
    return f"Did you mean '{matches[0]}'?" if matches else ""


# ── Teacher-style message builders ───────────────────────────────────────────
# These produce consistent, friendly phrasing for common runtime errors.

def name_error_hint(name: str, all_names: list) -> str:
    """Build a helpful hint for a NameError."""
    hint = suggest_callable(name, all_names)
    if not hint:
        hint = suggest_name(name, all_names)
    if not hint:
        hint = f"Create it first:  let {name} = ..."
    return hint


def type_error_add_hint(left_type: str, right_type: str) -> str:
    """Hint for  number + text  style type errors."""
    if left_type == "number":
        return f"Convert the number first:  str(the_number) + the_text"
    if right_type == "number":
        return f"Convert the number first:  the_text + str(the_number)"
    return f"Make sure both sides are the same type before adding"


def index_error_hint(idx, collection_len: int) -> str:
    """Hint for out-of-range index access."""
    if isinstance(idx, int) and collection_len > 0:
        valid = f"Valid indexes are 0 to {collection_len - 1}"
        if idx < 0:
            return f"Negative indexes are not supported yet.  {valid}"
        return f"Index {idx} is past the end.  {valid}"
    return "Check that the index is within the list's length"


# ══════════════════════════════════════════════════════════════════════════════
#  INTERNAL CONTROL-FLOW SIGNALS
# ══════════════════════════════════════════════════════════════════════════════

class _Return(Exception):
    __slots__ = ("value",)
    def __init__(self, v): self.value = v

class _Break(Exception):
    __slots__ = ()

class _Continue(Exception):
    __slots__ = ()
