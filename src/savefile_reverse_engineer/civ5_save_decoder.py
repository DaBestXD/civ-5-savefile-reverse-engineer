"""Public interface for decoding supported Civilization V save files."""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from types import MappingProxyType

from ._raw.header.decoder import (
    Civ5SaveHeaderDecodeError as _RawHeaderDecodeError,
)
from ._raw.header.decoder import (
    Civ5SavePayloadDecompressionError as _RawPayloadDecompressionError,
)
from ._raw.header.decoder import (
    decode_header_bytes_impl,
    decompress_payload_bytes_impl,
)
from ._raw.header.models import Civ5SaveHeader as RawCiv5SaveHeader
from ._raw.map.decoder import CvPlotDecodeError as _RawPlotDecodeError
from ._raw.map.decoder import iterate_plots_from_payload_impl
from ._raw.map.payload_locator import (
    Civ5SavePayloadDecodeError as _RawPayloadDecodeError,
)
from ._raw.map.payload_locator import (
    CvPlotLocation,
    CvTeamLocation,
    locate_cv_plots,
    locate_cv_teams,
)
from ._raw.player.decoder import iterate_players_from_payload_impl
from ._raw.player.infrastructure import CvPlayerDecodeError as _RawPlayerDecodeError
from ._raw.player.models import CvPlayer as RawCvPlayer
from ._raw.team.decoder import CvTeamDecodeError as _RawTeamDecodeError
from ._raw.team.decoder import iterate_teams_from_payload_impl
from ._raw.team.models import CvTeam as RawCvTeam
from ._semantic import (
    make_player,
    make_player_slots,
    make_plot,
    make_settings,
    make_summary,
    make_team,
)
from .errors import (
    Civ5SaveHeaderDecodeError,
    Civ5SavePayloadDecodeError,
    Civ5SavePayloadDecompressionError,
    CvPlayerDecodeError,
    CvPlotDecodeError,
    CvTeamDecodeError,
)
from .models import (
    CvCity,
    CvPlayer,
    CvPlot,
    CvTeam,
    CvUnit,
    GameSettings,
    PlayerSlot,
    SaveSummary,
    SlotStatus,
)


@dataclass(frozen=True, slots=True)
class _CvPlayerLocation:
    byte_offset: int
    expected_totals: tuple[tuple[int, int], ...]


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
    _plot_location_cache: CvPlotLocation | None
    _player_location_cache: _CvPlayerLocation | None
    _team_location_cache: CvTeamLocation | None

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
    def _header(self) -> RawCiv5SaveHeader:
        """Return the cached private physical-header record."""
        header = self._header_cache
        if header is None:
            try:
                header = decode_header_bytes_impl(self._save_bytes)
            except _RawHeaderDecodeError as error:
                raise Civ5SaveHeaderDecodeError(
                    error.message, offset=error.offset, field=error.field
                ) from error
            self._header_cache = header
        return header

    @property
    def summary(self) -> SaveSummary:
        """Return cached common metadata from the save's quick header."""
        summary = self._summary_cache
        if summary is None:
            summary = make_summary(self._header)
            self._summary_cache = summary
        return summary

    @property
    def settings(self) -> GameSettings:
        """Return cached common, non-sensitive game settings."""
        settings = self._settings_cache
        if settings is None:
            settings = make_settings(self._header)
            self._settings_cache = settings
        return settings

    @property
    def player_slots(self) -> tuple[PlayerSlot, ...]:
        """Return cached semantic records for all 64 saved player slots."""
        slots = self._player_slots_cache
        if slots is None:
            slots = make_player_slots(self._header)
            self._player_slots_cache = slots
        return slots

    @property
    def _payload(self) -> bytes:
        """Return the cached private decompressed payload."""
        payload = self._payload_cache
        if payload is None:
            try:
                payload = decompress_payload_bytes_impl(self._save_bytes, self._header)
            except _RawPayloadDecompressionError as error:
                raise Civ5SavePayloadDecompressionError(error.message) from error
            self._payload_cache = payload
        return payload

    def _get_plot_location(self, payload: bytes) -> CvPlotLocation:
        location = self._plot_location_cache
        if location is None:
            try:
                location = locate_cv_plots(payload)
            except _RawPayloadDecodeError as error:
                raise Civ5SavePayloadDecodeError(
                    error.message, offset=error.offset, field=error.field
                ) from error
            self._plot_location_cache = location
        return location

    def _get_team_location(self, payload: bytes) -> CvTeamLocation:
        location = self._team_location_cache
        if location is None:
            try:
                location = locate_cv_teams(payload, self._get_plot_location(payload))
            except _RawPayloadDecodeError as error:
                raise Civ5SavePayloadDecodeError(
                    error.message, offset=error.offset, field=error.field
                ) from error
            except _RawPlotDecodeError as error:
                raise CvPlotDecodeError(
                    error.message,
                    offset=error.offset,
                    plot_index=error.plot_index,
                ) from error
            self._team_location_cache = location
        return location

    @property
    def plots(self) -> tuple[CvPlot, ...]:
        """Return every plot as an immutable, identity-cached tuple."""
        plots = self._plots_cache
        if plots is not None:
            return plots
        payload = self._payload
        location = self._get_plot_location(payload)
        raw_plots = iterate_plots_from_payload_impl(
            payload,
            byte_offset=location.byte_offset,
            width=location.width,
            height=location.height,
        )
        try:
            plots = tuple(make_plot(raw_plot) for raw_plot in raw_plots)
        except _RawPlotDecodeError as error:
            raise CvPlotDecodeError(
                error.message,
                offset=error.offset,
                plot_index=error.plot_index,
            ) from error
        self._plots_cache = plots
        return plots

    def _iter_raw_teams(self) -> Iterator[RawCvTeam]:
        payload = self._payload
        team_location = self._get_team_location(payload)
        return iterate_teams_from_payload_impl(
            payload, byte_offset=team_location.byte_offset
        )

    @property
    def teams(self) -> tuple[CvTeam, ...]:
        """Return participant teams as an immutable, identity-cached tuple."""
        teams = self._teams_cache
        if teams is not None:
            return teams
        participant_teams = {
            slot.team_index
            for slot in self.player_slots
            if slot.status in (SlotStatus.TAKEN, SlotStatus.COMPUTER)
        }
        try:
            teams = tuple(
                make_team(raw_team)
                for raw_team in self._iter_raw_teams()
                if raw_team.team_index in participant_teams
            )
        except _RawTeamDecodeError as error:
            raise CvTeamDecodeError(
                error.message,
                offset=error.offset,
                team_index=error.team_index,
            ) from error
        self._teams_cache = teams
        return teams

    def _iter_raw_players(self) -> Iterator[RawCvPlayer]:
        payload = self._payload
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

    @property
    def players(self) -> tuple[CvPlayer, ...]:
        """Return participating players as an immutable, identity-cached tuple."""
        players = self._players_cache
        if players is not None:
            return players
        participant_slots = {
            slot.player_index: slot
            for slot in self.player_slots
            if slot.status in (SlotStatus.TAKEN, SlotStatus.COMPUTER)
        }
        players_list: list[CvPlayer] = []
        try:
            for raw_player in self._iter_raw_players():
                slot = participant_slots.get(raw_player.player_index)
                if slot is None:
                    continue
                player = make_player(raw_player, slot=slot)
                players_list.append(player)
        except _RawPlayerDecodeError as error:
            raise CvPlayerDecodeError(
                error.message,
                offset=error.offset,
                player_index=error.player_index,
                field=error.field,
            ) from error
        except _RawTeamDecodeError as error:
            raise CvTeamDecodeError(
                error.message,
                offset=error.offset,
                team_index=error.team_index,
            ) from error
        players = tuple(players_list)
        self._players_cache = players
        return players

    @property
    def player_display_names(self) -> Mapping[int, str | None]:
        """Map each participating player index to its resolved display name."""
        names = self._player_display_names_cache
        if names is None:
            names = MappingProxyType(
                {player.player_index: player.display_name for player in self.players}
            )
            self._player_display_names_cache = names
        return names

    def get_owner_display_name(
        self, owned_object: CvCity | CvPlot | CvUnit
    ) -> str | None:
        """Return an owned object's player name, decoding players on first use."""
        return self.player_display_names.get(owned_object.owner_player_index)

    @property
    def cities(self) -> tuple[CvCity, ...]:
        """Return participant-owned cities from the cached player tuple."""
        cities = self._cities_cache
        if cities is not None:
            return cities
        cities = tuple(city for player in self.players for city in player.cities)
        self._cities_cache = cities
        return cities

    @property
    def units(self) -> tuple[CvUnit, ...]:
        """Return participant-owned units from the cached player tuple."""
        units = self._units_cache
        if units is not None:
            return units
        units = tuple(unit for player in self.players for unit in player.units)
        self._units_cache = units
        return units


__all__ = (
    "Civ5SaveDecoder",
    "Civ5SavePayloadDecodeError",
)
