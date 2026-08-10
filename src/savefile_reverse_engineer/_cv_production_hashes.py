"""Pinned Lekmod v34.11 database hash names used by city production orders."""

from ._cv_team_hash_catalog import TEAM_TYPE_NAMES
from ._firaxis_hash import firaxis_hash

PROJECT_HASH_NAMES = {
    firaxis_hash(name): name for name in TEAM_TYPE_NAMES if name.startswith("PROJECT_")
}

__all__: tuple[str, ...] = ()
