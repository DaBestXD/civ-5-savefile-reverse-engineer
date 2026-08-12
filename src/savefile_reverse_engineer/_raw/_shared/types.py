"""Raw serialized types shared by multiple decoder domains."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import IntEnum
from typing import override


class RouteType(IntEnum):
    """Serialized route types shared by CvPlot and CvTeam."""

    NONE = -1
    ROAD = 0
    RAILROAD = 1


@dataclass(slots=True)
class HashedType:
    """A serialized database hash and its known Lekmod v34.11 type name."""

    hash_value: int
    name: str | None

    @override
    def __str__(self) -> str:
        return self.name if self.name else "Unknown"


def resolve_hashed_type(hash_value: int, names: Mapping[int, str]) -> HashedType:
    """Return a raw hashed type with its known catalogue name, if any."""
    return HashedType(hash_value=hash_value, name=names.get(hash_value))


__all__: tuple[str, ...] = ()
