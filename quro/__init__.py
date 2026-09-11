"""quro-step.

The minimal Kernel lives under :mod:`quro.kernel`. Everything else named in the
architecture (Steering, Compaction, Backtrack, Fork, Axiom Folding, ContextView,
...) is intentionally *outside* this package and must not be imported by it.
"""

__all__ = ["kernel"]
