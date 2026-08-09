"""Public interface for decoding supported Civilization V save files."""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from types import MappingProxyType
from typing import NoReturn, override

from ._binary_reader import LittleEndianReader
from ._free_list import read_free_list_header
from ._semantic import (
    make_player,
    make_player_slots,
    make_plot,
    make_settings,
    make_summary,
    make_team,
)
from .civ5_header import (
    decode_header_bytes_impl,
    decompress_payload_bytes_impl,
)
from .civ5_header_types import Civ5SaveHeader as RawCiv5SaveHeader
from .cv_player import iterate_players_from_payload_impl
from .cv_player_types import CvPlayer as RawCvPlayer
from .cv_plot import iterate_plots_from_payload_impl, locate_plot_array_end_impl
from .cv_plot_types import CvPlot as RawCvPlot
from .cv_team import iterate_teams_from_payload_impl
from .cv_team_types import CvTeam as RawCvTeam
from .models import (
    CvCity,
    CvPlayer,
    CvPlot,
    CvTeam,
    CvUnit,
    GameSettings,
    PlayerSlot,
    PlayerType,
    SaveSummary,
    SlotStatus,
)

_SQLITE_SIGNATURE = b"SQLite format 3\x00"
_SQLITE_LENGTH = 0xC00
_CV_MAP_VERSION = 1
_MINIMUM_CV_PLOT_LENGTH = 0x621
_PLAYER_TEAM_COUNT = 80
_CIV_PLAYER_COUNT = 64
_YIELD_COUNT = 7
_RESOURCE_COUNT = 57
_IMPROVEMENT_COUNT = 46
_MINOR_CIVILIZATION_KEY = "CIVILIZATION_MINOR"
_BARBARIAN_CIVILIZATION_KEY = "CIVILIZATION_BARBARIAN"


def _player_display_name(player: RawCvPlayer, slot: PlayerSlot) -> str | None:
    if slot.display_name is not None:
        return slot.display_name
    if slot.status is not SlotStatus.COMPUTER:
        return None
    if slot.civilization_key != _MINOR_CIVILIZATION_KEY:
        return slot.leader_key
    if not player.cities.entries:
        return None
    return player.cities.entries[0].name_key


def _player_type(slot: PlayerSlot) -> PlayerType:
    if slot.civilization_key == _MINOR_CIVILIZATION_KEY:
        return PlayerType.CITY_STATE
    if slot.civilization_key == _BARBARIAN_CIVILIZATION_KEY:
        return PlayerType.BARBARIAN
    if slot.status is SlotStatus.TAKEN:
        return PlayerType.PLAYER
    return PlayerType.COMPUTER


class Civ5SavePayloadDecodeError(ValueError):
    """Malformed or unsupported structure in a decompressed Civ V payload."""

    offset: int
    field: str

    def __init__(self, message: str, *, offset: int, field: str) -> None:
        self.offset = offset
        self.field = field
        super().__init__(f"{field} at decompressed byte offset 0x{offset:X}: {message}")


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
    _ = reader.read_bytes(5 * _PLAYER_TEAM_COUNT * 4, f"{field}.player_team_arrays")
    _ = reader.read_bytes(_CIV_PLAYER_COUNT * 8, f"{field}.target_city_references")
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


def _locate_cv_teams(payload: bytes, plot_location: _CvPlotLocation) -> _CvTeamLocation:
    plot_end = locate_plot_array_end_impl(
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
        "_cities_cache",
        "_header_cache",
        "_payload_cache",
        "_player_display_names_cache",
        "_player_location_cache",
        "_player_slots_cache",
        "_players_cache",
        "_plot_location_cache",
        "_plots_cache",
        "_save_bytes",
        "_settings_cache",
        "_summary_cache",
        "_team_location_cache",
        "_teams_cache",
        "_units_cache",
    )

    _save_bytes: bytes
    _header_cache: RawCiv5SaveHeader | None
    _payload_cache: bytes | None
    _summary_cache: SaveSummary | None
    _settings_cache: GameSettings | None
    _player_slots_cache: tuple[PlayerSlot, ...] | None
    _player_display_names_cache: Mapping[int, str | None] | None
    _plots_cache: tuple[CvPlot, ...] | None
    _teams_cache: tuple[CvTeam, ...] | None
    _players_cache: tuple[CvPlayer, ...] | None
    _cities_cache: tuple[CvCity, ...] | None
    _units_cache: tuple[CvUnit, ...] | None
    _plot_location_cache: _CvPlotLocation | None
    _player_location_cache: _CvPlayerLocation | None
    _team_location_cache: _CvTeamLocation | None

    def __init__(self, save_path: str | PathLike[str]) -> None:
        self._save_bytes = Path(save_path).read_bytes()
        self._header_cache = None
        self._payload_cache = None
        self._summary_cache = None
        self._settings_cache = None
        self._player_slots_cache = None
        self._player_display_names_cache = None
        self._plots_cache = None
        self._teams_cache = None
        self._players_cache = None
        self._cities_cache = None
        self._units_cache = None
        self._plot_location_cache = None
        self._player_location_cache = None
        self._team_location_cache = None

    @property
    def raw_header(self) -> RawCiv5SaveHeader:
        """Return the cached exact physical-header record."""
        header = self._header_cache
        if header is None:
            header = decode_header_bytes_impl(self._save_bytes)
            self._header_cache = header
        return header

    @property
    def summary(self) -> SaveSummary:
        """Return cached common metadata from the save's quick header."""
        summary = self._summary_cache
        if summary is None:
            summary = make_summary(self.raw_header)
            self._summary_cache = summary
        return summary

    @property
    def settings(self) -> GameSettings:
        """Return cached common, non-sensitive game settings."""
        settings = self._settings_cache
        if settings is None:
            settings = make_settings(self.raw_header)
            self._settings_cache = settings
        return settings

    @property
    def player_slots(self) -> tuple[PlayerSlot, ...]:
        """Return cached semantic records for all 64 saved player slots."""
        slots = self._player_slots_cache
        if slots is None:
            slots = make_player_slots(self.raw_header)
            self._player_slots_cache = slots
        return slots

    @property
    def payload_bytes(self) -> bytes:
        """Return and cache the complete decompressed save payload bytes."""
        payload = self._payload_cache
        if payload is None:
            payload = decompress_payload_bytes_impl(self._save_bytes, self.raw_header)
            self._payload_cache = payload
        return payload

    def _get_plot_location(self, payload: bytes) -> _CvPlotLocation:
        location = self._plot_location_cache
        if location is None:
            location = _locate_cv_plots(payload)
            self._plot_location_cache = location
        return location

    def _get_team_location(self, payload: bytes) -> _CvTeamLocation:
        location = self._team_location_cache
        if location is None:
            location = _locate_cv_teams(payload, self._get_plot_location(payload))
            self._team_location_cache = location
        return location

    def iter_plots(self) -> Iterator[CvPlot]:
        """Return a fresh lazy iterator over every plot in the save's CvMap."""
        plots = self._plots_cache
        if plots is not None:
            return iter(plots)
        payload = self.payload_bytes
        location = self._get_plot_location(payload)
        raw_plots = iterate_plots_from_payload_impl(
            payload,
            byte_offset=location.byte_offset,
            width=location.width,
            height=location.height,
        )
        return self._iter_and_cache_plots(raw_plots)

    def _iter_and_cache_plots(self, raw_plots: Iterator[RawCvPlot]) -> Iterator[CvPlot]:
        plots: list[CvPlot] = []
        for raw_plot in raw_plots:
            plot = make_plot(raw_plot)
            plots.append(plot)
            yield plot
        self._plots_cache = tuple(plots)

    def _iter_raw_teams(self) -> Iterator[RawCvTeam]:
        payload = self.payload_bytes
        team_location = self._get_team_location(payload)
        return iterate_teams_from_payload_impl(
            payload, byte_offset=team_location.byte_offset
        )

    def iter_teams(self) -> Iterator[CvTeam]:
        """Return a fresh lazy iterator over participant teams."""
        teams = self._teams_cache
        if teams is not None:
            return iter(teams)
        participant_teams = {
            slot.team_index
            for slot in self.player_slots
            if slot.status in (SlotStatus.TAKEN, SlotStatus.COMPUTER)
        }
        return self._iter_and_cache_teams(
            self._iter_raw_teams(), participant_teams=participant_teams
        )

    def _iter_and_cache_teams(
        self,
        raw_teams: Iterator[RawCvTeam],
        *,
        participant_teams: set[int],
    ) -> Iterator[CvTeam]:
        teams: list[CvTeam] = []
        for raw_team in raw_teams:
            if raw_team.team_index not in participant_teams:
                continue
            team = make_team(raw_team)
            teams.append(team)
            yield team
        self._teams_cache = tuple(teams)

    def _iter_raw_players(self) -> Iterator[RawCvPlayer]:
        payload = self.payload_bytes
        location = self._player_location_cache
        if location is None:
            team_location = self._get_team_location(payload)
            teams = tuple(
                iterate_teams_from_payload_impl(
                    payload, byte_offset=team_location.byte_offset
                )
            )
            final_team = teams[-1]
            player_offset = final_team.byte_offset + final_team.byte_length
            location = _CvPlayerLocation(
                byte_offset=player_offset,
                expected_totals=tuple(
                    (team.total_population, team.total_land) for team in teams
                ),
            )
            self._player_location_cache = location
        return iterate_players_from_payload_impl(
            payload,
            byte_offset=location.byte_offset,
            expected_totals=location.expected_totals,
        )

    def iter_players(self) -> Iterator[CvPlayer]:
        """Return players whose saved slots are human- or computer-controlled."""
        players = self._players_cache
        if players is not None:
            return iter(players)
        participant_slots = {
            slot.player_index: slot
            for slot in self.player_slots
            if slot.status in (SlotStatus.TAKEN, SlotStatus.COMPUTER)
        }
        return self._iter_and_cache_players(
            self._iter_raw_players(), participant_slots=participant_slots
        )

    def _iter_and_cache_players(
        self,
        raw_players: Iterator[RawCvPlayer],
        *,
        participant_slots: Mapping[int, PlayerSlot],
    ) -> Iterator[CvPlayer]:
        players: list[CvPlayer] = []
        for raw_player in raw_players:
            slot = participant_slots.get(raw_player.player_index)
            if slot is None:
                continue
            player = make_player(
                raw_player,
                display_name=_player_display_name(raw_player, slot),
                player_type=_player_type(slot),
            )
            players.append(player)
            yield player
        self._players_cache = tuple(players)

    @property
    def player_display_names(self) -> Mapping[int, str | None]:
        """Map each participating player index to its resolved display name."""
        names = self._player_display_names_cache
        if names is None:
            names = MappingProxyType(
                {
                    player.player_index: player.display_name
                    for player in self.iter_players()
                }
            )
            self._player_display_names_cache = names
        return names

    def get_owner_display_name(
        self, owned_object: CvCity | CvPlot | CvUnit
    ) -> str | None:
        """Return an owned object's player name, decoding players on first use."""
        return self.player_display_names.get(owned_object.owner_player_index)

    def iter_cities(self) -> Iterator[CvCity]:
        """Return a fresh lazy iterator over participant-owned cities."""
        cities = self._cities_cache
        if cities is not None:
            return iter(cities)
        return self._iter_and_cache_cities()

    def _iter_and_cache_cities(self) -> Iterator[CvCity]:
        cities: list[CvCity] = []
        for player in self.iter_players():
            for city in player.cities:
                cities.append(city)
                yield city
        self._cities_cache = tuple(cities)

    def iter_units(self) -> Iterator[CvUnit]:
        """Return a fresh lazy iterator over participant-owned units."""
        units = self._units_cache
        if units is not None:
            return iter(units)
        return self._iter_and_cache_units()

    def _iter_and_cache_units(self) -> Iterator[CvUnit]:
        units: list[CvUnit] = []
        for player in self.iter_players():
            for unit in player.units:
                units.append(unit)
                yield unit
        self._units_cache = tuple(units)


__all__ = (
    "Civ5SaveDecoder",
    "Civ5SavePayloadDecodeError",
)
