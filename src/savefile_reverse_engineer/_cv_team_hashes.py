"""Pinned Lekmod v34.11 database hash names used by CvTeam."""

from ._cv_plot_hashes import (
    BUILD_HASH_NAMES,
    IMPROVEMENT_HASH_NAMES,
    RESOURCE_HASH_NAMES,
    firaxis_hash,
)
from ._cv_team_hash_catalog import TEAM_TYPE_NAMES

_VOTE_SOURCE_NAMES = ("DIPLOVOTE_POPE", "DIPLOVOTE_UN")


TEAM_HASH_NAMES = {
    **BUILD_HASH_NAMES,
    **IMPROVEMENT_HASH_NAMES,
    **RESOURCE_HASH_NAMES,
    **{firaxis_hash(name): name for name in TEAM_TYPE_NAMES},
    **{firaxis_hash(name): name for name in _VOTE_SOURCE_NAMES},
}
