"""Where a workdir's durable state lives, and the one rule about path shape.

`docs/design/Q4-Kernel-Domain-Infrastructure.md` §8 proposes a layout and says what the
two objects are. This module is that layout **as paths, and nothing else**: it reads no
byte and writes none, so a caller can ask where something *would* live before anything
exists, and a check can assert a path without creating it.

```text
WORKSPACE   the durable, shared subject. Identity is the SUBJECT.
            Holds the material, the domain declaration, and the reading declaration —
            none of which are in the model.
SESSION     one run of Control against a workspace. Identity is the RUN.
            Holds `(C, P)`, the bodies, and the round reports.
```

**Why this is not a constant in some other module.** A `.quro/` root is found by walking
up from a working directory, the way `.git` is. That makes the layout a *function of
where you are*, and a function that two modules each implement their own way is the
duplication this repository has paid for twice (`LF-5`) — the two would agree until the
day one of them learned about a new subdirectory.

## What it refuses

An identifier becomes a path component, so an identifier that is not a safe component is
refused **by name** rather than joined. This is not hygiene: a layout that resolved
outside its data root would write a session somewhere the next process does not look, and
the failure would present as a reconstruction that lost state rather than as a refused
path. The rule is the codec's own — refuse rather than produce something well-formed and
wrong.
"""

from __future__ import annotations

import pathlib
import re

#: The tool family's data root, and this tool's namespace inside it. Siblings of
#: :data:`TOOL` are other tools' state; nothing here may assume it is the only one.
DATA_ROOT = ".quro"
TOOL = "step"

WORKSPACE_DIR = "workspace"
SESSION_DIR = "session"
SOURCE_DIR = "source"
BODIES_DIR = "artifacts"
PLANS_DIR = "plans"
ROUNDS_DIR = "rounds"

#: The file a workspace states itself in — its domain, its reading declaration, its
#: fingerprint. **Not the resolver**: a resolver is a live domain capability and the
#: codec refuses to carry it, so a format that looked self-contained and was not would
#: be the silent-substitution shape this architecture refuses everywhere else.
WORKSPACE_FILE = "workspace.json"

#: The ledger — `(C, P)` references, with artifact bodies and plan versions beside it.
LEDGER_FILE = "ledger.json"

#: A path component. Anchored, and the first character must be alphanumeric — which is
#: what makes `..`, a leading `.`, and an absolute path unrepresentable rather than
#: filtered. Everything after may carry the separators this model's ids actually use
#: (`:` in `fold::<unit><instance>`, `-`, `_`, `.`).
SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class LayoutError(ValueError):
    """The path cannot be built — named rather than produced somewhere unintended."""


def component(value: object, *, what: str) -> str:
    """``value`` as a safe single path component, or a refusal naming it."""
    if value is None:
        raise LayoutError(
            f"{what} is missing (None). `str(None)` is the four characters 'None', which "
            "is a perfectly legal directory name — so this would have created something "
            "under a name no caller meant and no caller can find again. Refused rather "
            "than performed."
        )
    text = str(value)
    if not SAFE_COMPONENT.match(text):
        raise LayoutError(
            f"{what} is not a usable path component: {text!r}. It must start with a "
            "letter or digit and hold only letters, digits, '.', '_', ':' or '-', "
            "at most 128 characters."
        )
    return text


def find_workdir(start: "pathlib.Path | str | None" = None) -> "pathlib.Path | None":
    """The nearest directory at or above ``start`` that holds a `.quro/`.

    ``None`` when there is none, because "no project here" and "the project is here"
    are different answers and a function that conflated them would make the caller
    guess which one it got. The default start is the current directory, which is what
    makes ``.quro/`` behave the way a reader expects a per-project directory to.
    """
    here = pathlib.Path(start if start is not None else pathlib.Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / DATA_ROOT).is_dir():
            return candidate
    return None


class Layout:
    """``<workdir>/.quro/step`` — the paths, and no I/O.

    Constructed rather than discovered by default: a caller that has already resolved a
    workdir should not have to make the filesystem answer again, and a caller that has
    not says so by using :meth:`discover`.
    """

    def __init__(self, workdir: "pathlib.Path | str") -> None:
        self.workdir = pathlib.Path(workdir)
        self.root = self.workdir / DATA_ROOT / TOOL

    # -- construction -----------------------------------------------------
    @classmethod
    def under(cls, workdir: "pathlib.Path | str") -> "Layout":
        """The layout of a workdir already in hand — no discovery, no filesystem read."""
        return cls(workdir)

    @classmethod
    def discover(cls, start: "pathlib.Path | str | None" = None) -> "Layout":
        """The layout of the nearest workdir, or a refusal naming where was searched.

        Refuses rather than falling back to the current directory: a tool that created
        `.quro/step/` wherever it happened to be run would scatter durable state across
        the filesystem, and the state would look correct from inside each copy.
        """
        found = find_workdir(start)
        if found is None:
            origin = pathlib.Path(start if start is not None else pathlib.Path.cwd())
            raise LayoutError(
                f"no {DATA_ROOT}/ found at or above {origin.resolve()}. Create one, or "
                f"name a workdir explicitly with Layout.under(...)."
            )
        return cls(found)

    # -- the two objects --------------------------------------------------
    def workspace(self, workspace_id: object) -> pathlib.Path:
        return self.root / WORKSPACE_DIR / component(workspace_id, what="a workspace id")

    def workspace_source(self, workspace_id: object) -> pathlib.Path:
        """Where the material lives **when the workspace owns it**.

        A workspace may instead declare a location elsewhere — v0.2 §36 requires logical
        resource identity to be stable independently of physical storage, and a path is
        not part of an identity. This is the default realization, not the definition.
        """
        return self.workspace(workspace_id) / SOURCE_DIR

    def workspace_file(self, workspace_id: object) -> pathlib.Path:
        return self.workspace(workspace_id) / WORKSPACE_FILE

    def session(self, session_id: object) -> pathlib.Path:
        return self.root / SESSION_DIR / component(session_id, what="a session id")

    def ledger(self, session_id: object) -> pathlib.Path:
        """The small session root a fresh process follows to its declared durable values."""
        return self.session(session_id) / LEDGER_FILE

    def bodies(self, session_id: object) -> pathlib.Path:
        return self.session(session_id) / BODIES_DIR

    def plans(self, session_id: object) -> pathlib.Path:
        """The immutable plan versions a session ledger may reference."""
        return self.session(session_id) / PLANS_DIR

    def plan(self, session_id: object, name: object) -> pathlib.Path:
        """One content-addressed plan version, named by the ledger's reference."""
        return self.plans(session_id) / component(name, what="a plan version")

    def body(self, session_id: object, name: object) -> pathlib.Path:
        """One artifact body, by the name the ledger declared for it.

        A *name*, not an id: which name a given id gets is the pair's business, and the
        ledger is where the two are bound together and made readable.
        """
        return self.bodies(session_id) / component(name, what="a body name")

    def rounds(self, session_id: object) -> pathlib.Path:
        return self.session(session_id) / ROUNDS_DIR

    def round_report(self, session_id: object, index: object) -> pathlib.Path:
        return self.rounds(session_id) / f"{int(index):03d}.json"

    # -- reporting --------------------------------------------------------
    def as_dict(self) -> dict:
        return {"workdir": str(self.workdir), "root": str(self.root)}

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"Layout({str(self.root)!r})"


__all__ = [
    "BODIES_DIR",
    "DATA_ROOT",
    "LEDGER_FILE",
    "Layout",
    "LayoutError",
    "PLANS_DIR",
    "ROUNDS_DIR",
    "SAFE_COMPONENT",
    "SESSION_DIR",
    "SOURCE_DIR",
    "TOOL",
    "WORKSPACE_DIR",
    "WORKSPACE_FILE",
    "component",
    "find_workdir",
]
