"""nyxel.gui — tkinter GUI runtime."""
from __future__ import annotations

try:
    import tkinter as tk
    from tkinter import ttk, font as tkfont
except ImportError:
    tk = None

from .errors import NyxError

# ── theme ─────────────────────────────────────────────────────────────────────

_BG      = "#1e1e2e"
_SURFACE = "#2a2a3e"
_ACCENT  = "#7c6af7"
_ACCENT2 = "#5a9cf8"
_FG      = "#cdd6f4"
_FG_DIM  = "#6c7086"
_DANGER  = "#f38ba8"
_SUCCESS = "#a6e3a1"
_PAD     = 10

_AR_FONTS = ["Noto Sans Arabic", "Arabic Typesetting", "Geeza Pro",
             "Tahoma", "Arial Unicode MS", "Arial", "Helvetica"]


def _arabic(text: str) -> bool:
    return any("\u0600" <= c <= "\u06FF" or
               "\u0750" <= c <= "\u077F" or
               "\uFB50" <= c <= "\uFDFF" or
               "\uFE70" <= c <= "\uFEFF"
               for c in str(text))


def _fix_arabic(text: str) -> str:
    """
    Reshape + bidi-reorder Arabic text for tkinter.

    Tkinter doesn't handle bidirectional text or Arabic letter-joining.
    Without reshaping, letters appear disconnected and in the wrong order.
    Falls back to the raw string if the libraries aren't installed.
    Install with:  pip install arabic-reshaper python-bidi
    """
    if not _arabic(text):
        return text
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(text))
    except ImportError:
        return text


def _pick_font(size: int = 11, bold: bool = False) -> tuple:
    weight = "bold" if bold else "normal"
    if tk is None:
        return ("Arial", size, weight)
    for name in _AR_FONTS:
        try:
            f = tkfont.Font(family=name, size=size, weight=weight)
            if f.actual("family").lower() not in ("", "helvetica"):
                return (name, size, weight)
        except Exception:
            continue
    return ("Arial", size, weight)


def _apply_theme(root) -> None:
    root.configure(bg=_BG)
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    fn  = _pick_font(11)
    fnb = _pick_font(11, bold=True)
    fns = _pick_font(10)

    style.configure(".",
        background=_BG, foreground=_FG, font=fn,
        borderwidth=0, focuscolor=_ACCENT)

    style.configure("TLabel",
        background=_BG, foreground=_FG, font=fn, padding=(4, 4))

    style.configure("Dim.TLabel",
        foreground=_FG_DIM, font=fns)

    style.configure("Title.TLabel",
        foreground=_FG, font=_pick_font(13, bold=True))

    style.configure("TButton",
        background=_ACCENT, foreground="#ffffff",
        font=fnb, padding=(12, 7), relief="flat")
    style.map("TButton",
        background=[("active", "#9b8cf9"), ("pressed", "#6a5af0")])

    style.configure("Danger.TButton",
        background=_DANGER, foreground="#1e1e2e",
        font=fnb, padding=(12, 7), relief="flat")
    style.map("Danger.TButton",
        background=[("active", "#f5a3b5"), ("pressed", "#d07080")])

    style.configure("Success.TButton",
        background=_SUCCESS, foreground="#1e1e2e",
        font=fnb, padding=(12, 7), relief="flat")
    style.map("Success.TButton",
        background=[("active", "#b8f0b5"), ("pressed", "#80c47a")])

    style.configure("TEntry",
        fieldbackground=_SURFACE, foreground=_FG,
        insertcolor=_FG, font=fn, padding=(8, 6), relief="flat")
    style.map("TEntry",
        bordercolor=[("focus", _ACCENT2), ("!focus", _FG_DIM)])

    style.configure("TFrame", background=_BG)


# ── widget wrapper ────────────────────────────────────────────────────────────

class NyxWidget:
    __slots__ = ("_kind", "_tk")

    def __init__(self, kind: str, tk_widget):
        self._kind = kind
        self._tk   = tk_widget

    def __getattr__(self, name: str):
        if name == "value":
            return self._tk.get() if hasattr(self._tk, "get") else None
        if name == "text":
            try:    return self._tk.cget("text")
            except Exception: return None
        raise AttributeError(f"Widget has no property '{name}'")

    def __setattr__(self, name: str, val):
        if name in ("_kind", "_tk"):
            object.__setattr__(self, name, val); return
        if name == "text":
            txt    = str(val)
            fixed  = _fix_arabic(txt)
            is_ar  = _arabic(txt)
            anchor = "e" if is_ar else "w"
            try:
                self._tk.config(text=fixed, anchor=anchor,
                                justify="right" if is_ar else "left")
            except tk.TclError:
                try:
                    self._tk.config(text=fixed)
                except Exception:
                    pass
            return
        raise NyxError("GUIError", f"Widget has no settable property '{name}'")

    def __repr__(self) -> str:
        return f"<{self._kind} widget>"


# ── widget builder ────────────────────────────────────────────────────────────

_BTN_STYLE = {
    "btn":        "TButton",
    "btn_danger": "Danger.TButton",
    "btn_ok":     "Success.TButton",
}


class NyxWidgetBuilder:
    __slots__ = ("_window", "_kind", "_args", "_on_click", "_x", "_y", "_interp")

    def __init__(self, window, kind: str, args: list, interpreter):
        self._window   = window
        self._kind     = kind
        self._args     = args
        self._on_click = None
        self._x        = None
        self._y        = None
        self._interp   = interpreter

    def apply_modifier(self, name: str, args: list) -> None:
        if name == "on_click":
            self._on_click = args[0] if args else None
        elif name == "place":
            if len(args) < 2:
                raise NyxError("GUIError", "place() requires x and y",
                               hint="Write: place(50, 100)")
            self._x, self._y = args[0], args[1]
        else:
            raise NyxError("GUIError", f"Unknown widget modifier '{name}'",
                           hint="Known modifiers: on_click  place")

    def build(self) -> NyxWidget:
        root   = self._window.root
        interp = self._interp
        kind   = self._kind
        text   = str(self._args[0]) if self._args else ""
        fixed  = _fix_arabic(text)
        is_ar  = _arabic(text)
        anchor = "e" if is_ar else "w"

        if kind in _BTN_STYLE:
            w = ttk.Button(root, text=fixed, style=_BTN_STYLE[kind])
            if self._on_click is not None:
                fn = self._on_click
                w.config(command=lambda fn=fn: _safe_call(interp, fn))

        elif kind == "label":
            w = ttk.Label(root, text=fixed, style="TLabel",
                          anchor=anchor, justify="right" if is_ar else "left")

        elif kind == "dim_label":
            w = ttk.Label(root, text=fixed, style="Dim.TLabel",
                          anchor=anchor, justify="right" if is_ar else "left")

        elif kind in ("input", "input_field"):
            w = ttk.Entry(root, justify="right" if is_ar else "left")
            if self._args:
                w.insert(0, fixed)

        elif kind == "separator":
            w = ttk.Separator(root, orient="horizontal")

        else:
            raise NyxError("GUIError", f"Unknown widget type '{kind}'",
                           hint="Known types: btn  btn_danger  btn_ok  label  dim_label  input  separator")

        if self._x is not None and self._y is not None:
            w.place(x=int(self._x), y=int(self._y))
        else:
            w.pack(pady=5, padx=_PAD, fill="x")

        return NyxWidget(kind, w)


def _safe_call(interp, fn) -> None:
    try:
        interp._call(fn, [])
    except Exception as e:
        print(f"\n  GUIError in callback: {e}")


# ── window ────────────────────────────────────────────────────────────────────

class NyxWindow:
    __slots__ = ("root",)

    def __init__(self, title: str, width: int, height: int):
        if tk is None:
            raise NyxError("GUIError", "tkinter is not available",
                           hint="tkinter is bundled with Python — check your installation")
        root = tk.Tk()
        root.title(_fix_arabic(str(title)))
        root.geometry(f"{int(width)}x{int(height)}")
        root.resizable(True, True)
        root.minsize(300, 200)
        _apply_theme(root)
        self.root = root

    def run(self) -> None:
        self.root.mainloop()