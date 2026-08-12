"""Pinned Lekmod v34.11 database hash names used by CvTeam."""

from .._shared.firaxis_hash import firaxis_hash
from .team_types import TEAM_TYPE_NAMES

_VOTE_SOURCE_NAMES = ("DIPLOVOTE_POPE", "DIPLOVOTE_UN")


TEAM_HASH_NAMES = {
    **{firaxis_hash(name): name for name in TEAM_TYPE_NAMES},
    **{firaxis_hash(name): name for name in _VOTE_SOURCE_NAMES},
}
