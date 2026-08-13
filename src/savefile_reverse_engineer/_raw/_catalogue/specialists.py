"""Pinned Lekmod v34.11 specialist hashes in database order."""

from .._shared.firaxis_hash import firaxis_hash

SPECIALIST_NAMES = (
    "SPECIALIST_CITIZEN",
    "SPECIALIST_WRITER",
    "SPECIALIST_ARTIST",
    "SPECIALIST_MUSICIAN",
    "SPECIALIST_SCIENTIST",
    "SPECIALIST_MERCHANT",
    "SPECIALIST_ENGINEER",
)

SPECIALIST_HASH_NAMES = {firaxis_hash(name): name for name in SPECIALIST_NAMES}
SPECIALIST_HASHES = tuple(firaxis_hash(name) for name in SPECIALIST_NAMES)

__all__: tuple[str, ...] = ()
