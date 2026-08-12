"""Conversion helpers shared by semantic domains."""

from .._raw._shared.types import HashedType as RawHashedType
from ..models import GameType


def game_type(value: RawHashedType) -> GameType:
    """Create a public database type from its raw serialized representation."""
    return GameType(hash_value=value.hash_value, key=value.name)


__all__: tuple[str, ...] = ()
