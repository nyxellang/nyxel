"""
nyxel.gui — optional GUI module

    bring gui
    bring gui as g

    let win = gui.window("My App", 800, 600)

    fn on_click():
        lbl.text = "clicked!"

    let lbl = win.add(gui.label("Hello"))
    let btn = win.add(gui.btn("Click me").on_click(on_click).color("green"))
    win.run()
"""
from __future__ import annotations

try:
    import customtkinter as ctk
except ImportError:
    ctk = None

from .errors  import NyxError
from .runtime import NyxObject, Environment

_NAMED_COLORS = {
    "purple": "#7c6af7", "blue":   "#3b8ed0", "green":  "#2fa572",
    "red":    "#e05252", "orange": "#e07b39", "yellow": "#d4a017",
    "pink":   "#d45d9b", "teal":   "#2a9d8f", "white":  "#ffffff",
    "gray":   "#6c7086", "grey":   "#6c7086", "black":  "#1a1a1a",
}


def _resolve_color(c):
    return _NAMED_COLORS.get(str(c).strip().lower(), str(c))


def _arabic(text):
    return any("\u0600" <= ch <= "\u06FF" or "\uFB50" <= ch <= "\uFDFF"
               for ch in str(text))


def _fix_arabic(text):
    """
    Reshape + bidi-reorder for CTK.
    Requires:  pip install arabic-reshaper python-bidi
    """
    if not _arabic(text):
        return text
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(text))
    except ImportError:
        return text


def _darken(hex_color):
    try:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"#{max(0,r-30):02x}{max(0,g-30):02x}{max(0,b-30):02x}"
    except Exception:
        return hex_color


def _safe_call(interp, fn):
    try:
        interp._call(fn, [])
    except Exception as e:
        print(f"\n  GUIError in callback: {e}")


# ── live widget handle ────────────────────────────────────────────────────────

class NyxWidget:
    """Handle to a live CTK widget. Supports .value, .text, .append(), .clear()"""

    def __init__(self, kind, tk_widget, var=None):
        object.__setattr__(self, "_kind",   kind)
        object.__setattr__(self, "_tk",     tk_widget)
        object.__setattr__(self, "_var",    var)

    def __getattr__(self, name):
        kind = object.__getattribute__(self, "_kind")
        tk   = object.__getattribute__(self, "_tk")
        var  = object.__getattribute__(self, "_var")

        if name == "value":
            return var.get() if var is not None else (tk.get() if hasattr(tk, "get") else None)
        if name == "text":
            try:    return tk.cget("text")
            except Exception: return None
        if name == "checked":
            return bool(var.get()) if var is not None else False
        raise AttributeError(f"Widget has no property '{name}'")

    def __setattr__(self, name, val):
        tk  = object.__getattribute__(self, "_tk")
        var = object.__getattribute__(self, "_var")
        if name == "text":
            try:    tk.configure(text=_fix_arabic(str(val)))
            except Exception: pass
            return
        if name == "value":
            if var is not None:
                var.set(float(val))
            else:
                try:    tk.set(float(val))
                except Exception: pass
            return
        raise NyxError("GUIError", f"Widget has no settable property '{name}'")

    def append(self, text):
        tk = object.__getattribute__(self, "_tk")
        tk.configure(state="normal")
        tk.insert("end", _fix_arabic(str(text)) + "\n")
        tk.configure(state="disabled")
        tk.see("end")

    def clear(self):
        tk = object.__getattribute__(self, "_tk")
        tk.configure(state="normal")
        tk.delete("1.0", "end")
        tk.configure(state="disabled")

    def __repr__(self):
        return f"<{object.__getattribute__(self, '_kind')} widget>"


# ── widget builder — chainable config object ──────────────────────────────────

class WidgetBuilder:
    """
    Returned by gui.btn(), gui.label(), etc.
    Chain modifiers then pass to win.add() to actually build the widget.

        win.add(gui.btn("Save").color("green").on_click(save_fn).place(20, 50))
    """

    def __init__(self, kind, args):
        self._kind      = kind
        self._args      = args
        self._color     = None
        self._on_click  = None
        self._on_change = None
        self._x         = None
        self._y         = None

    def color(self, c):
        self._color = _resolve_color(c)
        return self

    def on_click(self, fn):
        self._on_click = fn
        return self

    def on_change(self, fn):
        self._on_change = fn
        return self

    def place(self, x, y):
        self._x, self._y = x, y
        return self

    def build(self, win: "NyxWindowObj", interp) -> NyxWidget:
        root  = win._root
        kind  = self._kind
        text  = _fix_arabic(str(self._args[0])) if self._args else ""
        color = self._color
        var   = None

        if kind == "btn":
            kw = {"fg_color": color, "hover_color": _darken(color)} if color else {}
            w  = ctk.CTkButton(root, text=text, **kw)
            if self._on_click:
                fn = self._on_click
                w.configure(command=lambda fn=fn: _safe_call(interp, fn))

        elif kind == "label":
            kw = {"text_color": color} if color else {}
            w  = ctk.CTkLabel(root, text=text,
                              anchor="e" if _arabic(text) else "w",
                              justify="right" if _arabic(text) else "left", **kw)

        elif kind == "dim_label":
            w = ctk.CTkLabel(root, text=text,
                             text_color=color or "gray",
                             font=ctk.CTkFont(size=11),
                             anchor="e" if _arabic(text) else "w",
                             justify="right" if _arabic(text) else "left")

        elif kind in ("input", "input_field"):
            kw = {"border_color": color} if color else {}
            w  = ctk.CTkEntry(root, placeholder_text=text,
                              justify="right" if _arabic(text) else "left", **kw)

        elif kind == "textbox":
            h = int(self._args[1]) if len(self._args) > 1 else 200
            w = ctk.CTkTextbox(root, height=h, state="disabled", wrap="word")

        elif kind == "checkbox":
            var = ctk.BooleanVar(value=False)
            kw  = {"checkmark_color": color} if color else {}
            w   = ctk.CTkCheckBox(root, text=text, variable=var, **kw)
            if self._on_click:
                fn = self._on_click
                w.configure(command=lambda fn=fn: _safe_call(interp, fn))
            if self._on_change:
                fn = self._on_change
                var.trace_add("write", lambda *_, fn=fn: _safe_call(interp, fn))

        elif kind == "switch":
            var = ctk.BooleanVar(value=False)
            kw  = {"progress_color": color} if color else {}
            w   = ctk.CTkSwitch(root, text=text, variable=var, **kw)
            if self._on_change:
                fn = self._on_change
                var.trace_add("write", lambda *_, fn=fn: _safe_call(interp, fn))

        elif kind == "slider":
            lo  = float(self._args[0]) if self._args else 0
            hi  = float(self._args[1]) if len(self._args) > 1 else 100
            var = ctk.DoubleVar(value=lo)
            kw  = {"button_color": color, "progress_color": color} if color else {}
            w   = ctk.CTkSlider(root, from_=lo, to=hi, variable=var, **kw)
            if self._on_change:
                fn = self._on_change
                w.configure(command=lambda v, fn=fn: _safe_call(interp, fn))

        elif kind == "progressbar":
            var = ctk.DoubleVar(value=0)
            kw  = {"progress_color": color} if color else {}
            w   = ctk.CTkProgressBar(root, variable=var, **kw)
            w.set(0)

        elif kind == "dropdown":
            options = [str(a) for a in self._args] if self._args else [""]
            var     = ctk.StringVar(value=options[0])
            kw      = {"button_color": color, "fg_color": color} if color else {}
            w       = ctk.CTkOptionMenu(root, values=options, variable=var, **kw)
            if self._on_change:
                fn = self._on_change
                w.configure(command=lambda v, fn=fn: _safe_call(interp, fn))

        elif kind == "radio":
            group = str(self._args[1]) if len(self._args) > 1 else "default"
            var   = win._radio_vars.setdefault(group, ctk.StringVar(value=""))
            kw    = {"fg_color": color} if color else {}
            w     = ctk.CTkRadioButton(root, text=text, variable=var, value=text, **kw)
            if self._on_click:
                fn = self._on_click
                w.configure(command=lambda fn=fn: _safe_call(interp, fn))

        elif kind == "separator":
            w = ctk.CTkFrame(root, height=2,
                             fg_color=color or "gray30", corner_radius=0)

        else:
            raise NyxError("GUIError", f"Unknown widget type '{kind}'",
                           hint="Known types: btn  label  dim_label  input  textbox  "
                                "checkbox  switch  slider  progressbar  dropdown  radio  separator")

        if self._x is not None and self._y is not None:
            w.place(x=int(self._x), y=int(self._y))
        else:
            w.pack(pady=6, padx=14, fill="x")

        return NyxWidget(kind, w, var)

    def __repr__(self):
        return f"<{self._kind} builder>"


# ── window object ─────────────────────────────────────────────────────────────

class NyxWindowObj:
    """Returned by gui.window(). Call .add(builder) then .run()"""

    def __init__(self, root, interp):
        self._root       = root
        self._interp     = interp
        self._radio_vars = {}
        self._key_handlers = []

    def add(self, builder) -> NyxWidget:
        if not isinstance(builder, WidgetBuilder):
            raise NyxError("GUIError",
                           "win.add() expects a widget builder like gui.btn('text')",
                           hint="Write:  win.add(gui.btn('Click me'))")
        return builder.build(self, self._interp)

    def on_key(self, key, fn):
        """win.on_key('escape', my_fn) — fires fn when key is pressed."""
        k = str(key).lower()
        def _handler(event, fn=fn):
            pressed = event.keysym.lower()
            if pressed == k:
                _safe_call(self._interp, fn)
            elif event.char and event.char.lower() == k:
                _safe_call(self._interp, fn)
        self._key_handlers.append(_handler)
        self._root.bind("<Key>", self._dispatch_key)

    def _dispatch_key(self, event):
        for h in self._key_handlers:
            h(event)

    def run(self):
        try:
            self._root.mainloop()
        except KeyboardInterrupt:
            pass

    def quit(self):
        """win.quit() — close the window and exit the app."""
        self._root.destroy()

    def __repr__(self):
        return f"<window '{self._root.title()}'>"


# ── module namespace exposed to Nyxel via bring ───────────────────────────────

def make_gui_module(interp) -> NyxObject:
    """
    Called by the interpreter's bring handler when 'bring gui' is executed.
    Returns a NyxObject whose fields are the gui API functions.
    """
    if ctk is None:
        raise NyxError("ImportError", "customtkinter is not installed",
                       hint="Run:  pip install customtkinter")

    def _window(title, width=800, height=600):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        root = ctk.CTk()
        root.title(_fix_arabic(str(title)))
        root.geometry(f"{int(width)}x{int(height)}")
        root.resizable(True, True)
        root.minsize(300, 200)
        return NyxWindowObj(root, interp)

    def _make_builder(kind):
        return lambda *args: WidgetBuilder(kind, list(args))

    return NyxObject({
        "window":      _window,
        "btn":         _make_builder("btn"),
        "label":       _make_builder("label"),
        "dim_label":   _make_builder("dim_label"),
        "input":       _make_builder("input"),
        "textbox":     _make_builder("textbox"),
        "checkbox":    _make_builder("checkbox"),
        "switch":      _make_builder("switch"),
        "slider":      _make_builder("slider"),
        "progressbar": _make_builder("progressbar"),
        "dropdown":    _make_builder("dropdown"),
        "radio":       _make_builder("radio"),
        "separator":   _make_builder("separator"),
    })