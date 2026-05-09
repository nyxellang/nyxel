"""
nyxel.runtime
─────────────
Runtime data structures used by the interpreter.

  Environment   — lexically-scoped variable store
  Param         — typed named tuple for function parameters
  NyxFunction   — a user-defined Nyxel function (closure)
  NyxObject     — dot-accessible dict wrapper
  NyxStruct     — struct constructor
  NyxException  — error object exposed in catch blocks
  _wrap/_unwrap — reference-preserving conversion helpers

──────────────────────────────────────────────────────────────────
Reference-semantics contract
──────────────────────────────────────────────────────────────────
Nyxel uses REFERENCE semantics for objects (dicts / NyxObjects).
This is a deliberate design decision, consistent with Python and JS.

  let a = {"x": 1}
  let b = a
  b.x = 99
  say(a.x)          # → 99  (a and b are the same object)

_wrap() wraps a Python dict in NyxObject WITHOUT copying.
This keeps API responses, module namespaces, and struct instances
cheap to pass around. It also means mutations are visible everywhere
the object is referenced — exactly what scripting users expect.

If you need an independent copy:
  let b = a.copy()   # NyxObject.copy() returns a shallow copy

When we move to a bytecode VM, value-semantic structs can be added
as a separate type. For now: objects are references. Period.
──────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

from typing import Any, Dict, List, NamedTuple, Optional

from .errors import NyxError, name_error_hint


# ══════════════════════════════════════════════════════════════════════════════
#  Param  — typed representation of a function parameter
# ══════════════════════════════════════════════════════════════════════════════

class Param(NamedTuple):
    """
    A single function parameter.

    name     — the parameter name (str)
    default  — an AST Node to evaluate if no argument is supplied,
               or None if the parameter is required.

    Using a NamedTuple instead of a raw tuple makes the code
    self-documenting and prevents the (name, default) ordering from
    being accidentally reversed.

    Before this existed, NyxFunction.params was annotated List[str]
    but actually held List[Tuple[str, Node|None]] — a latent bug.
    """
    name   : str
    default: Any    # Optional[ast.Node] — kept as Any to avoid circular import


# ══════════════════════════════════════════════════════════════════════════════
#  Environment
# ══════════════════════════════════════════════════════════════════════════════

class Environment:
    """
    A single lexical scope frame that optionally chains to a parent.

      define(name, val)  — create a new binding in *this* frame.
      get(name)          — resolve a name walking up the chain.
      set(name, val)     — reassign the nearest existing binding;
                           falls back to defining in the current frame
                           (so bare assignment  x = 1  works at top level).
    """

    def __init__(self, parent: Optional[Environment] = None):
        self._v      : Dict[str, Any]       = {}
        self._parent : Optional[Environment] = parent

    def define(self, name: str, val: Any) -> None:
        self._v[name] = val

    def get(self, name: str) -> Any:
        if name in self._v:
            return self._v[name]
        if self._parent is not None:
            return self._parent.get(name)

        all_names = list(self.flat().keys())
        hint = name_error_hint(name, all_names)
        raise NyxError("NameError", f"'{name}' doesn't exist yet", hint=hint)

    def set(self, name: str, val: Any) -> None:
        if name in self._v:
            self._v[name] = val
            return
        if self._parent is not None and self._parent._has(name):
            self._parent.set(name, val)
            return
        self._v[name] = val     # first assignment at current scope

    def _has(self, name: str) -> bool:
        return name in self._v or (
            self._parent is not None and self._parent._has(name)
        )

    def flat(self) -> Dict[str, Any]:
        """Flatten the entire scope chain (child overrides parent)."""
        base = self._parent.flat() if self._parent is not None else {}
        base.update(self._v)
        return base


# ══════════════════════════════════════════════════════════════════════════════
#  NyxFunction
# ══════════════════════════════════════════════════════════════════════════════

class NyxFunction:
    """
    A user-defined Nyxel function, capturing its lexical closure.

    params  — List[Param]  — ordered list of (name, default_node) pairs.
              default_node is None for required parameters.
    """

    __slots__ = ("name", "params", "body", "closure")

    def __init__(
        self,
        name    : str,
        params  : List[Param],
        body    : list,
        closure : Environment,
    ):
        self.name    = name
        self.params  = params  # List[Param] — always, no exceptions
        self.body    = body
        self.closure = closure

    @property
    def required_count(self) -> int:
        """Number of parameters with no default."""
        return sum(1 for p in self.params if p.default is None)

    @property
    def param_names(self) -> List[str]:
        """Just the names, for display purposes."""
        return [p.name for p in self.params]

    def __repr__(self) -> str:
        sig = ", ".join(
            p.name if p.default is None else f"{p.name} = ..."
            for p in self.params
        )
        return f"<fn {self.name}({sig})>"


# ══════════════════════════════════════════════════════════════════════════════
#  NyxObject  — dot-accessible dict wrapper
# ══════════════════════════════════════════════════════════════════════════════

class NyxObject:
    """
    Wraps a Python dict so its keys are accessible as attributes.

    Reference semantics: NyxObject shares the underlying dict with its
    creator and with any other NyxObject wrapping the same dict.
    Mutations are visible to all references.  See module docstring.

    Use  obj.copy()  to get an independent shallow copy.
    """

    __slots__ = ("_d",)

    def __init__(self, d: dict):
        object.__setattr__(self, "_d", d)

    # ── attribute access ──────────────────────────────────────────────────────

    def __getattr__(self, key: str) -> Any:
        d = object.__getattribute__(self, "_d")
        if key in d:
            return _wrap(d[key])
        raise AttributeError(
            f"No attribute '{key}'  (available: {list(d.keys())})"
        )

    def __setattr__(self, key: str, val: Any) -> None:
        object.__getattribute__(self, "_d")[key] = val

    # ── dict-style access ─────────────────────────────────────────────────────

    def __getitem__(self, key: Any) -> Any:
        d = object.__getattribute__(self, "_d")
        try:
            return _wrap(d[key])
        except KeyError:
            raise NyxError("KeyError", f"Key '{key}' not found in dict")

    def __setitem__(self, key: Any, val: Any) -> None:
        object.__getattribute__(self, "_d")[key] = val

    def __contains__(self, key: Any) -> bool:
        return key in object.__getattribute__(self, "_d")

    # ── Python dunder forwarding ──────────────────────────────────────────────

    def __len__(self)  -> int:  return len(object.__getattribute__(self, "_d"))
    def __bool__(self) -> bool: return bool(object.__getattribute__(self, "_d"))
    def __iter__(self):          return iter(object.__getattribute__(self, "_d"))
    def __repr__(self) -> str:  return repr(object.__getattribute__(self, "_d"))

    # ── dict method forwarding ────────────────────────────────────────────────

    def keys(self):
        return object.__getattribute__(self, "_d").keys()

    def values(self):
        return object.__getattribute__(self, "_d").values()

    def items(self):
        return object.__getattribute__(self, "_d").items()

    def get(self, key: Any, default: Any = None) -> Any:
        return _wrap(object.__getattribute__(self, "_d").get(key, default))

    def copy(self) -> "NyxObject":
        """
        Return a new NyxObject with a shallow copy of the underlying dict.

        Use this when you need an independent object that won't be affected
        by mutations to the original:

            let a = {"x": 1}
            let b = a.copy()
            b.x = 99
            say(a.x)   # → 1  (unchanged)
        """
        return NyxObject(dict(object.__getattribute__(self, "_d")))

    def _raw(self) -> dict:
        """Return the underlying Python dict (for serialisation / internals)."""
        return object.__getattribute__(self, "_d")


# ══════════════════════════════════════════════════════════════════════════════
#  wrap / unwrap
# ══════════════════════════════════════════════════════════════════════════════

def _wrap(val: Any) -> Any:
    """
    Convert Python dicts and lists into NyxObjects / wrapped lists.

    REFERENCE SEMANTICS: dicts are wrapped without copying.
    The NyxObject shares the underlying dict with any other reference.
    See the module docstring for the full rationale.

    Use _wrap_copy() if you need an independent copy.
    """
    if isinstance(val, NyxObject):
        return val              # already wrapped — don't double-wrap
    if isinstance(val, dict):
        return NyxObject(val)
    if isinstance(val, list):
        return [_wrap(v) for v in val]
    return val


def _wrap_copy(val: Any) -> Any:
    """
    Like _wrap(), but copies dicts before wrapping.

    Use this when you need value semantics — e.g. struct construction,
    where each instance must own its own data.
    """
    if isinstance(val, dict):
        return NyxObject(dict(val))
    if isinstance(val, list):
        return [_wrap_copy(v) for v in val]
    return val


def _unwrap(val: Any) -> Any:
    """
    Strip NyxObject wrappers back to plain Python dicts.
    Used for JSON serialisation and python: block injection.
    """
    if isinstance(val, NyxObject):
        return {k: _unwrap(v) for k, v in val._raw().items()}
    if isinstance(val, list):
        return [_unwrap(v) for v in val]
    return val


# ══════════════════════════════════════════════════════════════════════════════
#  NyxStruct
# ══════════════════════════════════════════════════════════════════════════════

class NyxStruct:
    """
    A named constructor produced by  struct Name: … .

    Calling a NyxStruct produces a NyxObject whose dict is freshly
    allocated for that instance (_wrap_copy semantics), so each
    struct instance owns its own data independently.

        struct Point:
            x
            y = 0

        let a = Point(1, 2)
        let b = Point(3, 4)
        a.x = 99
        say(b.x)   # → 3  (independent)
    """

    __slots__ = ("name", "fields", "defaults")

    def __init__(self, name: str, fields: List[str], defaults: dict):
        self.name     = name
        self.fields   = fields
        self.defaults = defaults   # field_name → pre-evaluated default value

    def __call__(self, *args) -> NyxObject:
        if len(args) > len(self.fields):
            raise NyxError(
                "TypeError",
                f"{self.name}() takes at most {len(self.fields)} argument(s), "
                f"got {len(args)}",
            )
        d: Dict[str, Any] = {}
        for i, fname in enumerate(self.fields):
            if i < len(args):
                d[fname] = args[i]
            elif fname in self.defaults:
                d[fname] = self.defaults[fname]
            else:
                raise NyxError(
                    "TypeError",
                    f"{self.name}() missing required field '{fname}'",
                    hint=f"Pass a value for '{fname}', or give it a default in the struct",
                )
        # Each instance gets its own dict — value-semantic construction
        return NyxObject(d)

    def __repr__(self) -> str:
        return f"<struct {self.name}>"


# ══════════════════════════════════════════════════════════════════════════════
#  NyxException
# ══════════════════════════════════════════════════════════════════════════════

class NyxException(NyxObject):
    """
    The error object surfaced in catch e: blocks.

    Placement justification : The NyxException is in this location as runtime.py near to this line.

    (NyxObject) and not in interpreter.py as it IS a runtime value
    It is saved in catch as an other NyxObject and goes into the States:
    Readable by e.kind and e.message. It is not a machine language to perform; 

    It is data: years, weeks, days, hours,  even seconds, uncounted,  making the whole work become indefinite and into huge amount of data totally.

    Adding a VM / bytecode layer, NyxException would still be present at

    The runtime layer,  as long as the VM creates instances on catching an error.
        try:
            risky()
        catch e:
            say(e.kind)       # e.g. "MathError"
            say(e.message)    # e.g. "Division by zero"
    """

    def __init__(self, kind: str, message: str):
        super().__init__({"kind": kind, "message": message})

    def __repr__(self) -> str:
        return self._raw().get("message", "unknown error")
