"""nyxel.tokens"""

from dataclasses import dataclass
from typing import Any


@dataclass
class Token:
    """
    type  : KW | ID | NUM | STR | OP | PUNCT | INDENT | DEDENT | NL | PYBLOCK | EOF
    value : the meaningful value
    line  : 1-based source line
    col   : 1-based column of the first character
    raw   : the full original source line (used for error display)
    """
    type  : str
    value : Any
    line  : int
    col   : int
    raw   : str = ""


# Arabic keywords are normalised to their English equivalents by the lexer.
# Everything downstream only ever sees the English value.

ARABIC_TO_ENGLISH: dict = {
    "اجعل":      "let",
    "عندما":     "when",
    "وإلا":      "otherwise",
    "إذا":       "if",
    "لكل":       "for",
    "في":        "in",
    "بينما":     "while",
    "كرر":       "repeat",
    "إلى":       "to",
    "توقف":      "break",
    "تابع":      "continue",
    "مرر":       "pass",
    "حاول":      "try",
    "اصطد":      "catch",
    "أخيرا":     "finally",
    "دالة":      "fn",
    "أرجع":      "return",
    "استورد":    "bring",
    "من":        "from",
    "كـ":        "as",
    "هيكل":      "struct",
    "أضف":       "add",
    "كل":        "each",
    "حيث":       "where",
    "صحيح":      "true",
    # خطأ means both "false" (boolean) and "error" — as a keyword it always means false.
    # Use a different catch variable name (e.g. ع) to avoid the collision.
    "خطأ":       "false",
    "لاشيء":     "none",
    "و":         "and",
    "أو":        "or",
    "ليس":       "not",
    "اذهب":      "goto",
}


KEYWORDS: frozenset = frozenset({
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
    "goto",
    "and", "or", "not",
    "true", "false", "none",
    "python",
    *ARABIC_TO_ENGLISH.keys(),
})