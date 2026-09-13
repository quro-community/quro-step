"""Checkpoint — a recoverable-Position declaration (E6, E8, E9).

A Position becomes *declared recoverable* together with optional metadata about
how it is meant to be re-entered::

    Checkpoint (recoverable-Position declaration)
        defaultInterpretation:  InterpretationIdentity?          // E6
        stabilityContract:      nominal | pinned = nominal        // E8 (default)
        pinnedFingerprint:      Fingerprint?                      // E9, iff pinned

This mirrors the declaration-time pattern already used for
``BacktrackAnnotation.foldMechanism``: a recoverable Position may carry declared
metadata about re-entry, and the declaration is where an explicit contract
lives instead of an implicit default.

The two invariances worth stating (E8/E9):

* an absent ``stabilityContract`` means ``nominal`` — a nominal identity claims
  no cross-environment equivalence, which is the correctly-scoped default, not
  a gap to be closed;
* ``pinned`` requires a ``pinnedFingerprint``, and ``nominal`` must not carry
  one. A ``pinned`` contract with nothing to verify against would silently
  degrade to ``nominal`` while *looking* like a stability promise.
"""

from __future__ import annotations

from dataclasses import dataclass

from .interpretation import InterpretationIdentity, Fingerprint, StabilityContract
from .position import SemanticPosition


@dataclass(frozen=True)
class Checkpoint:
    """Declared recoverability plus the interpretation contract it carries."""

    position: SemanticPosition
    default_interpretation: "InterpretationIdentity | None" = None
    stability_contract: StabilityContract = StabilityContract.NOMINAL
    pinned_fingerprint: "Fingerprint | None" = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "stability_contract", StabilityContract(self.stability_contract))
        if self.default_interpretation is not None:
            object.__setattr__(
                self,
                "default_interpretation",
                InterpretationIdentity.of(self.default_interpretation),
            )
        if self.pinned_fingerprint is not None:
            object.__setattr__(
                self, "pinned_fingerprint", Fingerprint.of(self.pinned_fingerprint)
            )
        if (
            self.stability_contract is StabilityContract.PINNED
            and self.pinned_fingerprint is None
        ):
            raise ValueError(
                "stabilityContract 'pinned' requires a pinnedFingerprint; "
                "a stability promise with nothing to verify is not a promise"
            )
        if (
            self.stability_contract is StabilityContract.NOMINAL
            and self.pinned_fingerprint is not None
        ):
            raise ValueError(
                "nominal declares no stability claim, so it must not carry a "
                "pinnedFingerprint; declare 'pinned' instead"
            )

    @property
    def is_pinned(self) -> bool:
        return self.stability_contract is StabilityContract.PINNED

    @classmethod
    def nominal(
        cls,
        position: SemanticPosition,
        default_interpretation: "InterpretationIdentity | str | None" = None,
    ) -> "Checkpoint":
        return cls(
            position=position,
            default_interpretation=(
                InterpretationIdentity.of(default_interpretation)
                if default_interpretation is not None
                else None
            ),
            stability_contract=StabilityContract.NOMINAL,
        )

    @classmethod
    def pinned(
        cls,
        position: SemanticPosition,
        fingerprint: "Fingerprint | str",
        default_interpretation: "InterpretationIdentity | str | None" = None,
    ) -> "Checkpoint":
        return cls(
            position=position,
            default_interpretation=(
                InterpretationIdentity.of(default_interpretation)
                if default_interpretation is not None
                else None
            ),
            stability_contract=StabilityContract.PINNED,
            pinned_fingerprint=Fingerprint.of(fingerprint),
        )


__all__ = ["Checkpoint"]
