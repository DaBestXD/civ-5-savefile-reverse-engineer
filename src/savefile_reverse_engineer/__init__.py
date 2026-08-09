"""Public semantic API for reading supported Civilization V save files."""

from .civ5_header import (
    Civ5SaveHeaderDecodeError,
    Civ5SavePayloadDecompressionError,
)
from .civ5_save_decoder import Civ5SaveDecoder, Civ5SavePayloadDecodeError
from .cv_player import CvPlayerDecodeError
from .cv_plot import CvPlotDecodeError
from .cv_team import CvTeamDecodeError
from .models import (
    CvCity,
    CvPlayer,
    CvPlot,
    CvTeam,
    CvUnit,
    GameMode,
    GameSettings,
    GameType,
    PlayerSlot,
    PlotType,
    RouteType,
    SaveSummary,
    SlotClaim,
    SlotStatus,
    TerrainType,
)

__all__ = (
    "Civ5SaveDecoder",
    "Civ5SaveHeaderDecodeError",
    "Civ5SavePayloadDecodeError",
    "Civ5SavePayloadDecompressionError",
    "CvCity",
    "CvPlayer",
    "CvPlayerDecodeError",
    "CvPlot",
    "CvPlotDecodeError",
    "CvTeam",
    "CvTeamDecodeError",
    "CvUnit",
    "GameMode",
    "GameSettings",
    "GameType",
    "PlayerSlot",
    "PlotType",
    "RouteType",
    "SaveSummary",
    "SlotClaim",
    "SlotStatus",
    "TerrainType",
)
