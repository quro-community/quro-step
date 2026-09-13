"""Mount boundary: resolution, validation and materialization (design doc §10).

Two resolutions happen here, both explicit and neither substitutable:

* **structural** (:mod:`.structural`) — which ExecUnit the Position designates;
* **interpretation** (:mod:`.resolver`, :mod:`.interpretation`) — which reading
  applies, and (under a ``pinned`` contract) whether it still verifies.
"""

from .interpretation import check_stability, resolve_interpretation
from .mounter import Mounter
from .resolver import DomainResolver, MappingResolver, resolved_fingerprint, resolver
from .structural import resolve_unit_at
from .validation import validate_position

__all__ = [
    "DomainResolver",
    "MappingResolver",
    "Mounter",
    "check_stability",
    "resolved_fingerprint",
    "resolve_interpretation",
    "resolve_unit_at",
    "resolver",
    "validate_position",
]
