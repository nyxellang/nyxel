"""
nyxel.lexer
───────────
Converts Nyxel source text into a flat list of Token objects.

"""

import re
from typing import List

from .errors import NyxError
from .tokens import Token, KEYWORDS, ARABIC_TO_ENGLISH


# ── internal: tokenise one non-indentation source line ───────────────────────

def _lex_line(text: str, line_num: int, raw: str) -> List[Token]:
    """
    Tokenise a single line of Nyxel source.
    Does *not* handle indentation — that is handled by the caller (lex).
    """
    toks: List[Token] = []
    col = 0
    n   = len(text)

    while col < n:
        ch = text[col]

        # whitespace
        if ch in " \t":
            col += 1
            continue

        # line comment
        if ch == "#":
            break

        # string literals  " … "  or  ' … '
        if ch in ('"', "'"):
            q   = ch
            end = col + 1
            buf: List[str] = []
            while end < n:
                c = text[end]
                if c == "\\" and end + 1 < n:
                    nxt = text[end + 1]
                    buf.append(
                        {"n": "\n", "t": "\t", "r": "\r",
                         '"': '"', "'": "'", "\\": "\\"}.get(nxt, "\\" + nxt)
                    )
                    end += 2
                    continue
                if c == q:
                    end += 1
                    break
                buf.append(c)
                end += 1
            else:
                raise NyxError(
                    "SyntaxError", "Unterminated string",
                    line_num, col + 1, raw, f"Add a closing {q}",
                )
            toks.append(Token("STR", "".join(buf), line_num, col + 1, raw))
            col = end
            continue

        # two-character operators
        if col + 1 < n:
            two = text[col : col + 2]
            if two in ("==", "!=", "<=", ">=", "**", "//", "+=", "-=", "*=", "/="):
                toks.append(Token("OP", two, line_num, col + 1, raw))
                col += 2
                continue

        # single-character operators
        if ch in "=<>+-*/%":
            toks.append(Token("OP", ch, line_num, col + 1, raw))
            col += 1
            continue

        # punctuation
        if ch in "()[]{}:,.":
            toks.append(Token("PUNCT", ch, line_num, col + 1, raw))
            col += 1
            continue

        # numeric literals  12  3.14  1e10
        if ch.isdigit():
            m = re.match(r"\d+\.?\d*([eE][+-]?\d+)?", text[col:])
            if m:
                s   = m.group()
                val = float(s) if ("." in s or "e" in s.lower()) else int(s)
                toks.append(Token("NUM", val, line_num, col + 1, raw))
                col += len(s)
                continue

        # identifiers and keywords — support ASCII and Arabic Unicode
        if ch.isalpha() or ch == "_":
            # Match any sequence of Unicode letters, digits, underscores,
            # or Arabic-specific characters (including hamza, tatweel, etc.)
            end = col
            while end < n and (text[end].isalnum() or text[end] == "_"
                                or ("\u0600" <= text[end] <= "\u06FF")   # Arabic block
                                or ("\u0750" <= text[end] <= "\u077F")   # Arabic Supplement
                                or ("\uFB50" <= text[end] <= "\uFDFF")   # Arabic Pres. A
                                or ("\uFE70" <= text[end] <= "\uFEFF")): # Arabic Pres. B
                end += 1
            word = text[col:end]

            # Normalise Arabic keywords → English equivalents
            if word in ARABIC_TO_ENGLISH:
                toks.append(Token("KW", ARABIC_TO_ENGLISH[word],
                                  line_num, col + 1, raw))
            elif word.lower() in KEYWORDS:
                toks.append(Token("KW", word.lower(), line_num, col + 1, raw))
            else:
                toks.append(Token("ID", word, line_num, col + 1, raw))

            col = end
            continue

        # Arabic-starting characters not caught above (standalone Arabic letters)
        if "\u0600" <= ch <= "\u06FF" or "\u0750" <= ch <= "\u077F":
            end = col
            while end < n and (text[end].isalnum() or text[end] == "_"
                                or "\u0600" <= text[end] <= "\u06FF"
                                or "\u0750" <= text[end] <= "\u077F"
                                or "\uFB50" <= text[end] <= "\uFDFF"
                                or "\uFE70" <= text[end] <= "\uFEFF"):
                end += 1
            word = text[col:end]
            if word in ARABIC_TO_ENGLISH:
                toks.append(Token("KW", ARABIC_TO_ENGLISH[word],
                                  line_num, col + 1, raw))
            else:
                toks.append(Token("ID", word, line_num, col + 1, raw))
            col = end
            continue

        # skip anything unrecognised
        col += 1

    return toks


# ── public API ────────────────────────────────────────────────────────────────

def lex(source: str, filename: str = "<input>") -> List[Token]:
    """
    Tokenise a complete Nyxel source string.

    Returns a flat list of Token objects ending with a single EOF token.
    Indentation changes are represented by INDENT / DEDENT tokens.
    Python escape-hatch blocks are collected into PYBLOCK tokens.
    """
    lines        = source.splitlines()
    toks: List[Token] = []
    indent_stack = [0]
    i            = 0
    n            = len(lines)

    while i < n:
        raw      = lines[i]
        stripped = raw.strip()

        # blank lines and full-line comments
        if not stripped or stripped.startswith("#"):
            toks.append(Token("NL", "\n", i + 1, 0, raw))
            i += 1
            continue

        indent = len(raw) - len(raw.lstrip())

        # emit INDENT / DEDENT tokens
        if indent > indent_stack[-1]:
            indent_stack.append(indent)
            toks.append(Token("INDENT", indent, i + 1, 0, raw))
        else:
            while indent < indent_stack[-1]:
                indent_stack.pop()
                toks.append(Token("DEDENT", indent, i + 1, 0, raw))

        # ── python: … end  block ──────────────────────────────────────────
        if stripped.endswith("python:"):
            base_indent = indent

            # tokenise any prefix to the left of `python:`
            # e.g.  `let result = python:`  →  lex `let result =` normally
            prefix = stripped[:-7].rstrip()
            if prefix:
                toks.extend(_lex_line(raw[: indent + len(prefix)], i + 1, raw))

            block_lines: List[str] = []
            block_indent: int | None = None
            i += 1

            while i < n:
                bl          = lines[i]
                bl_stripped = bl.strip()

                # preserve blank lines inside the block
                if not bl_stripped:
                    block_lines.append("")
                    i += 1
                    continue

                bl_indent = len(bl) - len(bl.lstrip())

                # `end` at or below the opening indent closes the block
                if bl_stripped == "end" and bl_indent <= base_indent:
                    i += 1
                    break

                if block_indent is None:
                    block_indent = bl_indent

                # strip the consistent leading indent from block lines
                strip_n = block_indent or 0
                block_lines.append(
                    bl[strip_n:] if len(bl) >= strip_n else bl.lstrip()
                )
                i += 1

            py_code = "\n".join(block_lines).rstrip()
            toks.append(Token("PYBLOCK", py_code, i, 0, ""))
            toks.append(Token("NL",      "\n",    i, 0, ""))
            continue

        # ── normal source line ────────────────────────────────────────────
        toks.extend(_lex_line(raw, i + 1, raw))
        toks.append(Token("NL", "\n", i + 1, len(raw), raw))
        i += 1

    # close any remaining open indent levels
    while len(indent_stack) > 1:
        indent_stack.pop()
        toks.append(Token("DEDENT", 0, n, 0, ""))

    toks.append(Token("EOF", None, n + 1, 0, ""))
    return toks
