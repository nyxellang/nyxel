"""nyxel.gui — CustomTkinter GUI runtime."""
from __future__ import annotations

try:
    import customtkinter as ctk
except ImportError:
    ctk = None

from .errors import NyxError

_NAMED_COLORS = {
    "purple": "#7c6af7", "blue":   "#3b8ed0", "green":  "#2fa572",
    "red":    "#e05252", "orange": "#e07b39", "yellow": "#d4a017",
    "pink":   "#d45d9b", "teal":   "#2a9d8f", "white":  "#ffffff",
    "gray":   "#6c7086", "grey":   "#6c7086", "black":  "#1a1a1a",
}


def _resolve_color(c: str) -> str:
    return _NAMED_COLORS.get(str(c).strip().lower(), c)


def _arabic(text: str) -> bool:
    return any("\u0600" <= ch <= "\u06FF" or "\uFB50" <= ch <= "\uFDFF"
               for ch in str(text))


def _fix_arabic(text: str) -> str:
    """
    Reshape + bidi-reorder Arabic for CTK (which inherits tkinter's lack of
    bidirectional support).  Requires:  pip install arabic-reshaper python-bidi
    """
    if not _arabic(text):
        return text
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(text))
    except ImportError:
        return text


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
            try:    self._tk.configure(text=_fix_arabic(str(val)))
            except Exception: pass
            return
        raise NyxError("GUIError", f"Widget has no settable property '{name}'")

    def __repr__(self) -> str:
        return f"<{self._kind} widget>"


class NyxWidgetBuilder:
    __slots__ = ("_window", "_kind", "_args", "_on_click", "_x", "_y",
                 "_color", "_interp")

    def __init__(self, window, kind: str, args: list, interpreter):
        self._window   = window
        self._kind     = kind
        self._args     = args
        self._on_click = None
        self._x        = None
        self._y        = None
        self._color    = None
        self._interp   = interpreter

    def apply_modifier(self, name: str, args: list) -> None:
        if name == "on_click":
            self._on_click = args[0] if args else None
        elif name == "place":
            if len(args) < 2:
                raise NyxError("GUIError", "place() requires x and y",
                               hint="Write: place(50, 100)")
            self._x, self._y = args[0], args[1]
        elif name == "color":
            if not args:
                raise NyxError("GUIError", "color() requires a value",
                               hint='Write: color("#ff0000")  or  color("red")')
            self._color = _resolve_color(str(args[0]))
        else:
            raise NyxError("GUIError", f"Unknown modifier '{name}'",
                           hint="Known modifiers: on_click  place  color")

    def build(self) -> NyxWidget:
        root   = self._window.root
        interp = self._interp
        kind   = self._kind
        text   = _fix_arabic(str(self._args[0])) if self._args else ""
        color  = self._color

        if kind == "btn":
            kw = {"fg_color": color, "hover_color": _darken(color)} if color else {}
            w  = ctk.CTkButton(root, text=text, **kw)
            if self._on_click is not None:
                fn = self._on_click
                w.configure(command=lambda fn=fn: _safe_call(interp, fn))

        elif kind == "label":
            kw = {"text_color": color} if color else {}
            w  = ctk.CTkLabel(root, text=text,
                              anchor="e" if _arabic(text) else "w",
                              justify="right" if _arabic(text) else "left", **kw)

        elif kind == "dim_label":
            kw = {"text_color": color or "gray"}
            w  = ctk.CTkLabel(root, text=text, font=ctk.CTkFont(size=11),
                              anchor="e" if _arabic(text) else "w",
                              justify="right" if _arabic(text) else "left", **kw)

        elif kind in ("input", "input_field"):
            kw = {"border_color": color} if color else {}
            w  = ctk.CTkEntry(root, placeholder_text=text,
                              justify="right" if _arabic(text) else "left", **kw)

        elif kind == "separator":
            w = ctk.CTkFrame(root, height=2, fg_color=color or "gray30",
                             corner_radius=0)

        else:
            raise NyxError("GUIError", f"Unknown widget type '{kind}'",
                           hint="Known types: btn  label  dim_label  input  separator")

        if self._x is not None and self._y is not None:
            w.place(x=int(self._x), y=int(self._y))
        else:
            w.pack(pady=6, padx=14, fill="x")

        return NyxWidget(kind, w)


def _darken(hex_color: str) -> str:
    try:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"#{max(0,r-30):02x}{max(0,g-30):02x}{max(0,b-30):02x}"
    except Exception:
        return hex_color


def _safe_call(interp, fn) -> None:
    try:
        interp._call(fn, [])
    except Exception as e:
        print(f"\n  GUIError in callback: {e}")


class NyxWindow:
    __slots__ = ("root",)

    def __init__(self, title: str, width: int, height: int):
        if ctk is None:
            raise NyxError("GUIError", "customtkinter is not installed",
                           hint="Run:  pip install customtkinter")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        root = ctk.CTk()
        root.title(_fix_arabic(str(title)))
        root.geometry(f"{int(width)}x{int(height)}")
        root.resizable(True, True)
        root.minsize(300, 200)
        self.root = root

    def run(self) -> None:
        self.root.mainloop()