"""Stable byte-level API for exact Civilization V serialization records."""

from collections.abc import Iterator

from ..civ5_header import (
    Civ5SaveHeaderDecodeError,
    Civ5SavePayloadDecompressionError,
)
from ..civ5_header import (
    decode_header_bytes_impl as _decode_header_bytes_impl,
)
from ..civ5_header import (
    decompress_payload_bytes_impl as _decompress_payload_bytes_impl,
)
from ..civ5_header_types import (
    ArchiveGameMode,
    BaseInfo,
    Civ5SaveHeader,
    ClimateInfo,
    CompressedChunk,
    CustomOption,
    EnabledDlc,
    EnabledMod,
    GameMapType,
    PlayerSlot,
    PreGameArchive,
    QuickGameMode,
    QuickHeader,
    SeaLevelInfo,
    SlotClaim,
    SlotHints,
    SlotStatus,
    TurnTimerInfo,
    UnknownHeaderSpan,
    WorldInfo,
)
from ..civ5_save_decoder import Civ5SavePayloadDecodeError
from ..cv_city_types import (
    CityBuildingState,
    CvCity,
    CvCityBuildings,
    ProductionOrder,
    ProductionOrderType,
)
from ..cv_player import (
    CvPlayerDecodeError,
)
from ..cv_player import (
    decode_player_array_bytes_impl as _decode_player_array_bytes_impl,
)
from ..cv_player_types import (
    CvPlayer,
    CvPlayerPolicy,
    CvPlayerPolicyBranch,
    CvPlayerPolicyInformation,
    SerializedFreeList,
)
from ..cv_plot import (
    CvPlotDecodeError,
)
from ..cv_plot import (
    decode_plot_array_bytes_impl as _decode_plot_array_bytes_impl,
)
from ..cv_plot_types import (
    ArchaeologyData,
    BuildProgress,
    CvPlot,
    FlowDirection,
    HashedType,
    ObjectReference,
    PlotFlags,
    PlotType,
    PlotYields,
    RouteType,
    TerrainType,
)
from ..cv_team import (
    CvTeamDecodeError,
)
from ..cv_team import (
    decode_team_array_bytes_impl as _decode_team_array_bytes_impl,
)
from ..cv_team_types import (
    CvTeam,
    HashedValue,
    ProjectArt,
    TeamFlags,
    TeamTechnology,
    TeamYieldChanges,
)
from ..cv_unit_types import CvUnit


def decode_header_bytes(save_bytes: bytes) -> Civ5SaveHeader:
    """Decode an exact physical save header from complete file bytes."""
    return _decode_header_bytes_impl(save_bytes)


def decompress_payload_bytes(save_bytes: bytes, header: Civ5SaveHeader) -> bytes:
    """Decompress the complete payload using an exact decoded header."""
    return _decompress_payload_bytes_impl(save_bytes, header)


def decode_plot_array_bytes(plot_array_bytes: bytes) -> Iterator[CvPlot]:
    """Return a lazy iterator over an exact serialized plot array."""
    return _decode_plot_array_bytes_impl(plot_array_bytes)


def decode_team_array_bytes(team_array_bytes: bytes) -> Iterator[CvTeam]:
    """Return a lazy iterator over an exact 64-team array."""
    return _decode_team_array_bytes_impl(team_array_bytes)


def decode_player_array_bytes(player_array_bytes: bytes) -> Iterator[CvPlayer]:
    """Return a lazy iterator over an exact 64-player array."""
    return _decode_player_array_bytes_impl(player_array_bytes)


__all__ = (
    "ArchaeologyData",
    "ArchiveGameMode",
    "BaseInfo",
    "BuildProgress",
    "CityBuildingState",
    "Civ5SaveHeader",
    "Civ5SaveHeaderDecodeError",
    "Civ5SavePayloadDecodeError",
    "Civ5SavePayloadDecompressionError",
    "ClimateInfo",
    "CompressedChunk",
    "CustomOption",
    "CvCity",
    "CvCityBuildings",
    "CvPlayer",
    "CvPlayerDecodeError",
    "CvPlayerPolicy",
    "CvPlayerPolicyBranch",
    "CvPlayerPolicyInformation",
    "CvPlot",
    "CvPlotDecodeError",
    "CvTeam",
    "CvTeamDecodeError",
    "CvUnit",
    "EnabledDlc",
    "EnabledMod",
    "FlowDirection",
    "GameMapType",
    "HashedType",
    "HashedValue",
    "ObjectReference",
    "PlayerSlot",
    "PlotFlags",
    "PlotType",
    "PlotYields",
    "PreGameArchive",
    "ProductionOrder",
    "ProductionOrderType",
    "ProjectArt",
    "QuickGameMode",
    "QuickHeader",
    "RouteType",
    "SeaLevelInfo",
    "SerializedFreeList",
    "SlotClaim",
    "SlotHints",
    "SlotStatus",
    "TeamFlags",
    "TeamTechnology",
    "TeamYieldChanges",
    "TerrainType",
    "TurnTimerInfo",
    "UnknownHeaderSpan",
    "WorldInfo",
    "decode_header_bytes",
    "decode_player_array_bytes",
    "decode_plot_array_bytes",
    "decode_team_array_bytes",
    "decompress_payload_bytes",
)
