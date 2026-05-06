"""
nyxel.tokens
────────────
Token  — a single lexical unit produced by the lexer.
KEYWORDS  — the set of reserved words in the Nyxel language (English + Arabic).
ARABIC_TO_ENGLISH — maps Arabic keywords to their English equivalents.

Arabic support
──────────────
Arabic keywords are normalised to their English equivalents by the lexer
before any token reaches the parser. The parser only ever sees English
keyword values — so adding Arabic costs zero changes to the parser,
interpreter, or runtime.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class Token:
    """
    A single lexical token.

    type  : KW | ID | NUM | STR | OP | PUNCT | INDENT | DEDENT | NL | PYBLOCK | EOF
    value : the meaningful value (keyword string, number, etc.)
    line  : 1-based source line
    col   : 1-based column of the first character
    raw   : the full original source line (used for error display)
    """
    type  : str
    value : Any
    line  : int
    col   : int
    raw   : str = ""


# ── Arabic → English normalisation map ───────────────────────────────────────
# The lexer converts Arabic keywords to their English equivalents immediately.
# Everything downstream only ever sees the English value.

ARABIC_TO_ENGLISH: dict = {
    # variables
    "اجعل":      "let",
    # conditionals
    "عندما":     "when",
    "وإلا":      "otherwise",
    "إذا":       "if",
    # loops
    "لكل":       "for",
    "في":        "in",
    "بينما":     "while",
    "كرر":       "repeat",
    "إلى":       "to",
    "توقف":      "break",
    "تابع":      "continue",
    "مرر":       "pass",
    # error handling
    "حاول":      "try",
    "اصطد":      "catch",
    "أخيرا":     "finally",
    # functions
    "دالة":      "fn",
    "أرجع":      "return",
    # modules
    "استورد":    "bring",
    "من":        "from",
    "كـ":        "as",
    # structs
    "هيكل":      "struct",
    # list helpers
    "أضف":       "add",
    "كل":        "each",
    # filtering
    "حيث":       "where",
    # boolean / null
    "صحيح":      "true",
    # NOTE: خطأ means both "false" (boolean) and "error" (common word) in Arabic.
    # As a keyword it always means false. Use a different name (e.g. ع) as a
    # catch variable to avoid the collision:
    #   اصطد ع:        ← correct
    #   اصطد خطأ:      ← خطأ becomes 'false', causing a syntax error
    "خطأ":       "false",
    "لاشيء":     "none",
    # logical operators
    "و":         "and",
    "أو":        "or",
    "ليس":       "not",
}


KEYWORDS: frozenset = frozenset({
    # ── English keywords ──────────────────────────────────────────────────────
    "let",
    "when", "otherwise",
    "if", "elif", "else",
    "for", "in", "while",
    "repeat", "to",
    "break", "continue", "pass",
    "try", "catch", "finally",
    "fn", "def", "return",
    "bring", "from", "as",
    "struct",
    "add", "each",
    "where",
    "and", "or", "not",
    "true", "false", "none",
    "python",

    # ── Arabic keywords (all values — normalised to English by the lexer) ─────
    *ARABIC_TO_ENGLISH.keys(),
})
