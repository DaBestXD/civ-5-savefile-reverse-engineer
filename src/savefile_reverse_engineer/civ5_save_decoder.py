"""Public interface for decoding supported Civilization V save files."""

from collections.abc import Iterator
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import NoReturn, override

from ._binary_reader import LittleEndianReader
from ._free_list import read_free_list_header
from .civ5_header import (
    decode_civ5_save_header_bytes,
    decompress_civ5_save_payload_bytes,
)
from .civ5_header_types import Civ5SaveHeader
from .cv_player import iterate_cv_players_from_payload
from .cv_player_types import CvPlayer
from .cv_plot import iterate_cv_plots_from_payload, locate_cv_plot_array_end
from .cv_plot_types import CvPlot
from .cv_team import iterate_cv_teams_from_payload, locate_cv_team_array_end
from .cv_team_types import CvTeam

_SQLITE_SIGNATURE = b"SQLite format 3\x00"
_SQLITE_LENGTH = 0xC00
_CV_MAP_VERSION = 1
_MINIMUM_CV_PLOT_LENGTH = 0x621
_PLAYER_TEAM_COUNT = 80
_CIV_PLAYER_COUNT = 64
_YIELD_COUNT = 7
_RESOURCE_COUNT = 57
_IMPROVEMENT_COUNT = 46


class Civ5SavePayloadDecodeError(ValueError):
    """Malformed or unsupported structure in a decompressed Civ V payload."""

    offset: int
    field: str

    def __init__(self, message: str, *, offset: int, field: str) -> None:
        self.offset = offset
        self.field = field
        super().__init__(
            f"{field} at decompressed byte offset 0x{offset:X}: {message}"
        )


class _PayloadReader(LittleEndianReader):
    __slots__: tuple[str, ...] = ()
    _bounds_error_suffix: str = "decompressed payload bytes"
    offset: int

    def __init__(self, data: bytes, offset: int) -> None:
        super().__init__(data)
        self.offset = offset

    @override
    def fail(
        self,
        message: str,
        *,
        offset: int | None = None,
        field: str | None = None,
    ) -> NoReturn:
        raise Civ5SavePayloadDecodeError(
            message,
            offset=self.offset if offset is None else offset,
            field="payload" if field is None else field,
        )


@dataclass(frozen=True, slots=True)
class _CvPlotLocation:
    byte_offset: int
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class _CvTeamLocation:
    byte_offset: int


@dataclass(frozen=True, slots=True)
class _CvPlayerLocation:
    byte_offset: int
    expected_totals: tuple[tuple[int, int], ...]


def _consume_hashed_array(reader: _PayloadReader, field: str) -> None:
    count = reader.u32(f"{field}.count")
    reader.ensure_count_fits(
        count,
        item_size=8,
        reserved_bytes=0,
        field=f"{field}.count",
    )
    _ = reader.read_bytes(count * 8, field)


def _skip_hashed_int_array(
    reader: _PayloadReader, *, expected_count: int, field: str
) -> None:
    count_offset = reader.offset
    count = reader.u32(f"{field}.count")
    if count != expected_count:
        reader.fail(
            f"{field}.count is {count}, expected {expected_count}",
            offset=count_offset,
            field=f"{field}.count",
        )
    for index in range(count):
        hash_value = reader.u32(f"{field}[{index}].type")
        if hash_value != 0:
            _ = reader.i32(f"{field}[{index}].value")


def _read_free_list_header(reader: _PayloadReader, field: str) -> int:
    return read_free_list_header(reader, field).live_count


def _skip_cv_area(reader: _PayloadReader, area_index: int) -> None:
    field = f"cv_map.areas[{area_index}]"
    version_offset = reader.offset
    version = reader.u32(f"{field}.version")
    if version != 1:
        reader.fail(
            f"unsupported CvArea version {version}; expected 1",
            offset=version_offset,
            field=f"{field}.version",
        )
    _ = reader.read_bytes(10 * 4, f"{field}.counters")
    _ = reader.read_bytes(4 * 4, f"{field}.boundaries")
    _ = reader.read_bool(f"{field}.water")
    _ = reader.read_bool(f"{field}.mountains")
    _ = reader.read_bytes(
        5 * _PLAYER_TEAM_COUNT * 4, f"{field}.player_team_arrays"
    )
    _ = reader.read_bytes(
        _CIV_PLAYER_COUNT * 8, f"{field}.target_city_references"
    )
    _ = reader.read_bytes(
        _CIV_PLAYER_COUNT * _YIELD_COUNT * 4,
        f"{field}.yield_rate_modifiers",
    )
    _skip_hashed_int_array(
        reader,
        expected_count=_RESOURCE_COUNT,
        field=f"{field}.resource_counts",
    )
    _skip_hashed_int_array(
        reader,
        expected_count=_IMPROVEMENT_COUNT,
        field=f"{field}.improvement_counts",
    )


def _skip_cv_landmass(reader: _PayloadReader, landmass_index: int) -> None:
    field = f"cv_map.landmasses[{landmass_index}]"
    version_offset = reader.offset
    version = reader.u32(f"{field}.version")
    if version != 1:
        reader.fail(
            f"unsupported CvLandmass version {version}; expected 1",
            offset=version_offset,
            field=f"{field}.version",
        )
    _ = reader.read_bytes(4 * 4, f"{field}.fixed_values")
    _ = reader.read_bool(f"{field}.water")
    _ = reader.i8(f"{field}.continent_type")


def _locate_cv_teams(
    payload: bytes, plot_location: _CvPlotLocation
) -> _CvTeamLocation:
    plot_end = locate_cv_plot_array_end(
        payload,
        byte_offset=plot_location.byte_offset,
        width=plot_location.width,
        height=plot_location.height,
    )
    reader = _PayloadReader(payload, plot_end)
    area_count = _read_free_list_header(reader, "cv_map.areas")
    for area_index in range(area_count):
        _skip_cv_area(reader, area_index)
    landmass_count = _read_free_list_header(reader, "cv_map.landmasses")
    for landmass_index in range(landmass_count):
        _skip_cv_landmass(reader, landmass_index)
    _ = reader.i32("cv_map.ai_map_hints")
    return _CvTeamLocation(byte_offset=reader.offset)


def _locate_cv_plots(payload: bytes) -> _CvPlotLocation:
    sqlite_offset = payload.find(_SQLITE_SIGNATURE)
    if sqlite_offset < 0:
        raise Civ5SavePayloadDecodeError(
            "embedded SQLite signature was not found",
            offset=0,
            field="embedded_sqlite.signature",
        )

    duplicate_offset = payload.find(_SQLITE_SIGNATURE, sqlite_offset + 1)
    if duplicate_offset >= 0:
        raise Civ5SavePayloadDecodeError(
            "multiple embedded SQLite signatures were found",
            offset=duplicate_offset,
            field="embedded_sqlite.signature",
        )
    if sqlite_offset < 4:
        raise Civ5SavePayloadDecodeError(
            "embedded SQLite signature has no preceding length",
            offset=sqlite_offset,
            field="embedded_sqlite.length",
        )

    sqlite_length_offset = sqlite_offset - 4
    sqlite_length = int.from_bytes(
        payload[sqlite_length_offset:sqlite_offset], byteorder="little"
    )
    if sqlite_length != _SQLITE_LENGTH:
        message = (
            f"unsupported embedded SQLite length {sqlite_length}; "
            + f"expected {_SQLITE_LENGTH}"
        )
        raise Civ5SavePayloadDecodeError(
            message,
            offset=sqlite_length_offset,
            field="embedded_sqlite.length",
        )

    cv_map_offset = sqlite_offset + sqlite_length
    reader = _PayloadReader(payload, cv_map_offset)
    version_offset = reader.offset
    version = reader.u32("cv_map.version")
    if version != _CV_MAP_VERSION:
        reader.fail(
            f"unsupported CvMap version {version}; expected {_CV_MAP_VERSION}",
            offset=version_offset,
            field="cv_map.version",
        )

    width_offset = reader.offset
    width = reader.i32("cv_map.width")
    height_offset = reader.offset
    height = reader.i32("cv_map.height")
    if width <= 0:
        reader.fail(
            f"map width is {width}; expected a positive value",
            offset=width_offset,
            field="cv_map.width",
        )
    if height <= 0:
        reader.fail(
            f"map height is {height}; expected a positive value",
            offset=height_offset,
            field="cv_map.height",
        )

    _ = reader.i32("cv_map.land_plot_count")
    _ = reader.i32("cv_map.owned_plot_count")
    _ = reader.i32("cv_map.natural_wonder_count")
    _ = reader.i32("cv_map.top_latitude")
    _ = reader.i32("cv_map.bottom_latitude")
    _ = reader.read_bool("cv_map.wrap_x")
    _ = reader.read_bool("cv_map.wrap_y")
    _ = reader.read_bytes(16, "cv_map.guid")
    _consume_hashed_array(reader, "cv_map.total_resources")
    _consume_hashed_array(reader, "cv_map.land_resources")

    plot_offset = reader.offset
    plot_count = width * height
    if plot_count > reader.remaining // _MINIMUM_CV_PLOT_LENGTH:
        reader.fail(
            f"{plot_count} plots cannot fit in the remaining payload bytes",
            offset=plot_offset,
            field="cv_map.plots",
        )

    return _CvPlotLocation(byte_offset=plot_offset, width=width, height=height)


class Civ5SaveDecoder:
    """Decode one stable in-memory snapshot of a supported Civ V save file."""

    __slots__: tuple[str, ...] = (
        "_header_cache",
        "_payload_cache",
        "_player_location_cache",
        "_plot_location_cache",
        "_save_bytes",
        "_team_location_cache",
    )

    _save_bytes: bytes
    _header_cache: Civ5SaveHeader | None
    _payload_cache: bytes | None
    _plot_location_cache: _CvPlotLocation | None
    _player_location_cache: _CvPlayerLocation | None
    _team_location_cache: _CvTeamLocation | None

    def __init__(self, save_path: str | PathLike[str]) -> None:
        self._save_bytes = Path(save_path).read_bytes()
        self._header_cache = None
        self._payload_cache = None
        self._plot_location_cache = None
        self._player_location_cache = None
        self._team_location_cache = None

    @property
    def header(self) -> Civ5SaveHeader:
        """Return the decoded physical header, decoding and caching it once."""
        header = self._header_cache
        if header is None:
            header = decode_civ5_save_header_bytes(self._save_bytes)
            self._header_cache = header
        return header

    def decompress_payload(self) -> bytes:
        """Return and cache the complete decompressed save payload."""
        payload = self._payload_cache
        if payload is None:
            payload = decompress_civ5_save_payload_bytes(
                self._save_bytes, self.header
            )
            self._payload_cache = payload
        return payload

    def iter_cv_plots(self) -> Iterator[CvPlot]:
        """Return a fresh lazy iterator over every plot in the save's CvMap."""
        payload = self.decompress_payload()
        location = self._plot_location_cache
        if location is None:
            location = _locate_cv_plots(payload)
            self._plot_location_cache = location
        return iterate_cv_plots_from_payload(
            payload,
            byte_offset=location.byte_offset,
            width=location.width,
            height=location.height,
        )

    def iter_cv_teams(self) -> Iterator[CvTeam]:
        """Return a fresh lazy iterator over all 64 teams in the save."""
        payload = self.decompress_payload()
        plot_location = self._plot_location_cache
        if plot_location is None:
            plot_location = _locate_cv_plots(payload)
            self._plot_location_cache = plot_location
        team_location = self._team_location_cache
        if team_location is None:
            team_location = _locate_cv_teams(payload, plot_location)
            self._team_location_cache = team_location
        return iterate_cv_teams_from_payload(
            payload, byte_offset=team_location.byte_offset
        )

    def iter_cv_players(self) -> Iterator[CvPlayer]:
        """Return a fresh lazy iterator over all 64 players and nested objects."""
        payload = self.decompress_payload()
        location = self._player_location_cache
        if location is None:
            plot_location = self._plot_location_cache
            if plot_location is None:
                plot_location = _locate_cv_plots(payload)
                self._plot_location_cache = plot_location
            team_location = self._team_location_cache
            if team_location is None:
                team_location = _locate_cv_teams(payload, plot_location)
                self._team_location_cache = team_location
            teams = tuple(
                iterate_cv_teams_from_payload(
                    payload, byte_offset=team_location.byte_offset
                )
            )
            player_offset = locate_cv_team_array_end(
                payload, byte_offset=team_location.byte_offset
            )
            location = _CvPlayerLocation(
                byte_offset=player_offset,
                expected_totals=tuple(
                    (team.total_population, team.total_land) for team in teams
                ),
            )
            self._player_location_cache = location
        return iterate_cv_players_from_payload(
            payload,
            byte_offset=location.byte_offset,
            expected_totals=location.expected_totals,
        )
