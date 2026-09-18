"""Kernel persistence — the durable model's representation (backlog item B-10).

    Position + Continuity  →  encode  →  plain JSON  →  decode  →  mount

**Not a store.** No filesystem, no URI scheme, no database, no topology: v0.2 §36
delegates persistence to stores, and this package is the half a store cannot supply —
what the bytes mean. Nothing here writes a byte.

What it is here to prevent is narrow and was measured: a codec that encodes a field and
never decodes it does not look like a broken codec, it looks like a broken model.
Milestone 3 wrote exactly that one, and what it produced was a continuity-scoped
binding case that failed while blaming the ownership policy it was testing.
`codec.py` states the obligation once, in a form both ends read — the type's own
`dataclasses.fields` — so a field the model grows cannot be dropped in silence.
"""

# Re-exported wholesale rather than re-listed: `codec.__all__` is already the single
# statement of this surface, and a second hand-kept copy of it is the duplication this
# repository keeps paying for (LF-5). A name added there appears here for free.
from .codec import *  # noqa: F401,F403
from .codec import __all__ as __all__
