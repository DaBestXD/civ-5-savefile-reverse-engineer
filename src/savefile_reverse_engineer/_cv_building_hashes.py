"""Pinned Lekmod v34.11 database hash names used by CvCityBuildings."""

from ._cv_plot_hashes import firaxis_hash
from ._cv_team_hash_catalog import TEAM_TYPE_NAMES

BUILDING_HASH_NAMES = {
    firaxis_hash(name): name
    for name in TEAM_TYPE_NAMES
    if name.startswith("BUILDING_")
}
