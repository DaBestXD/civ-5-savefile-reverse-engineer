"""Pinned Lekmod v34.11 database hash names used by city production orders."""

from .._shared.firaxis_hash import firaxis_hash
from .team_types import TEAM_TYPE_NAMES

PROJECT_HASH_NAMES = {
    firaxis_hash(name): name for name in TEAM_TYPE_NAMES if name.startswith("PROJECT_")
}

__all__: tuple[str, ...] = ()
