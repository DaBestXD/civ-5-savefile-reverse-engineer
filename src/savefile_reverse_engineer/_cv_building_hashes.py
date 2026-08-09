"""Pinned Lekmod v34.11 database hash names used by CvCityBuildings."""

from ._cv_team_hash_catalog import TEAM_TYPE_NAMES
from ._firaxis_hash import firaxis_hash

BUILDING_HASH_NAMES = {
    firaxis_hash(name): name for name in TEAM_TYPE_NAMES if name.startswith("BUILDING_")
}
