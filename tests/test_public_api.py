"""Tests for the curated public semantic API surfaces."""

from dataclasses import fields
from importlib.util import find_spec
from pathlib import Path
from typing import get_type_hints

import pytest

import savefile_reverse_engineer as public_api
import savefile_reverse_engineer.errors as errors_api
import savefile_reverse_engineer.game as game_api
import savefile_reverse_engineer.map as map_api
import savefile_reverse_engineer.player as player_api
import savefile_reverse_engineer.team as team_api
from savefile_reverse_engineer import (
    Civ5SaveDecoder,
    GameMode,
    PlayerType,
    SlotStatus,
)

_PROJECT_ROOT = Path(__file__).parent.parent
_SAVE_PATH = (
    _PROJECT_ROOT / "test-save-file/multi-player/AutoSave_Post_0076 AD-0040.Civ5Save"
)
_SINGLE_PLAYER_PATH = (
    _PROJECT_ROOT / "test-save-file/single-player/j-AutoSave_0040 BC-1600.Civ5Save"
)

_requires_save = pytest.mark.skipif(
    not _SAVE_PATH.is_file(), reason="the local Lekmod v34.11 save is unavailable"
)


def test_package_root_exports_only_the_curated_api() -> None:
    exports = set(public_api.__all__)

    assert exports == {
        "CityBuildingSpecialistState",
        "CityCitizenState",
        "CitySpecialistState",
        "CityYieldValues",
        "CityYieldVectors",
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
        "PlayerPolicyBranch",
        "PlayerPolicyInformation",
        "PlayerSlot",
        "PlayerType",
        "PlotType",
        "ProductionOrder",
        "ProductionOrderType",
        "RouteType",
        "SaveSummary",
        "SlotClaim",
        "SlotStatus",
        "TeamTechnology",
        "TerrainType",
    }


def test_domain_modules_export_only_their_public_models() -> None:
    assert set(game_api.__all__) == {
        "EnabledContent",
        "GameMode",
        "GameOption",
        "GameSettings",
        "GameType",
        "PlayerSlot",
        "SaveSummary",
        "SlotClaim",
        "SlotStatus",
        "WorldSettings",
    }
    assert set(map_api.__all__) == {
        "CvPlot",
        "FlowDirection",
        "ObjectReference",
        "PlotFlags",
        "PlotType",
        "PlotYields",
        "RouteType",
        "TerrainType",
    }
    assert set(player_api.__all__) == {
        "CityBuildingState",
        "CityBuildingSpecialistState",
        "CityBuildingStats",
        "CityCitizenState",
        "CitySpecialistState",
        "CityYieldValues",
        "CityYieldVectors",
        "CvCity",
        "CvPlayer",
        "CvUnit",
        "PlayerPolicyBranch",
        "PlayerPolicyInformation",
        "PlayerType",
        "ProductionOrder",
        "ProductionOrderType",
    }
    assert set(team_api.__all__) == {"CvTeam", "TeamTechnology"}
    assert set(errors_api.__all__) == {
        "Civ5SaveHeaderDecodeError",
        "Civ5SavePayloadDecodeError",
        "Civ5SavePayloadDecompressionError",
        "CvPlayerDecodeError",
        "CvPlotDecodeError",
        "CvTeamDecodeError",
    }


def test_former_public_raw_namespace_is_absent() -> None:
    assert find_spec("savefile_reverse_engineer.raw") is None


def test_old_byte_decoder_import_names_are_removed() -> None:
    assert find_spec("savefile_reverse_engineer.civ5_header") is None
    assert find_spec("savefile_reverse_engineer.cv_plot") is None
    assert find_spec("savefile_reverse_engineer.cv_team") is None
    assert find_spec("savefile_reverse_engineer.cv_player") is None


@_requires_save
def test_decoder_does_not_expose_raw_header_or_payload() -> None:
    decoder = Civ5SaveDecoder(_SAVE_PATH)

    assert not hasattr(decoder, "raw_header")
    assert not hasattr(decoder, "payload_bytes")
    assert not any(
        hasattr(decoder, name)
        for name in (
            "iter_players",
            "iter_teams",
            "iter_plots",
            "iter_cities",
            "iter_units",
        )
    )


def test_public_decoder_annotations_do_not_expose_raw_types() -> None:
    public_getters = (
        Civ5SaveDecoder.summary.fget,
        Civ5SaveDecoder.settings.fget,
        Civ5SaveDecoder.player_slots.fget,
        Civ5SaveDecoder.plots.fget,
        Civ5SaveDecoder.teams.fget,
        Civ5SaveDecoder.players.fget,
        Civ5SaveDecoder.player_display_names.fget,
        Civ5SaveDecoder.cities.fget,
        Civ5SaveDecoder.units.fget,
    )
    for getter in public_getters:
        assert getter is not None
        annotations = get_type_hints(getter)
        assert "savefile_reverse_engineer._raw" not in repr(annotations)

    method_annotations = get_type_hints(Civ5SaveDecoder.get_owner_display_name)
    assert "savefile_reverse_engineer._raw" not in repr(method_annotations)


@_requires_save
def test_summary_settings_and_slots_are_cached_semantic_views() -> None:
    decoder = Civ5SaveDecoder(_SAVE_PATH)

    assert decoder.summary is decoder.summary
    assert decoder.settings is decoder.settings
    assert decoder.player_slots is decoder.player_slots

    assert decoder.summary.turn == 76
    assert decoder.summary.game_mode is GameMode.MULTIPLAYER
    assert decoder.summary.active_civilization_key == "CIVILIZATION_VENEZ"
    assert decoder.settings.game_name == "RacismLEKMOD v34.11"
    assert decoder.settings.climate_key == "CLIMATE_TEMPERATE"
    assert decoder.settings.world.grid_width == 56
    assert len(decoder.player_slots) == 64
    assert decoder.player_slots[0].player_index == 0
    assert decoder.player_slots[0].status is SlotStatus.TAKEN


@_requires_save
def test_settings_omit_sensitive_and_format_only_fields() -> None:
    field_names = {field.name for field in fields(Civ5SaveDecoder(_SAVE_PATH).settings)}

    assert "admin_password" not in field_names
    assert "email_addresses" not in field_names
    assert "smtp_host" not in field_names
    assert "dummy_value" not in field_names
    assert "version" not in field_names


@_requires_save
def test_city_and_unit_properties_preserve_semantic_ownership() -> None:
    decoder = Civ5SaveDecoder(_SAVE_PATH)
    cities = decoder.cities
    units = decoder.units

    assert cities
    assert units
    assert all(city.owner_player_index >= 0 for city in cities)
    assert cities[0].name_key == "TXT_KEY_CITY_NAME_VENEZ"
    assert all(unit.owner_player_index >= 0 for unit in units)
    assert decoder.cities is cities
    assert decoder.units is units
    assert cities[0] is decoder.players[0].cities[0]
    assert decoder.get_owner_display_name(cities[0]) == "Brad, From Algebra"
    assert decoder.get_owner_display_name(units[0]) == "Brad, From Algebra"


@_requires_save
def test_get_owner_display_name_supports_plots_and_loads_players() -> None:
    decoder = Civ5SaveDecoder(_SAVE_PATH)
    plots = decoder.plots
    owned_plot = next(plot for plot in plots if plot.owner_player_index == 0)
    unowned_plot = next(plot for plot in plots if plot.owner_player_index < 0)

    assert decoder.get_owner_display_name(owned_plot) == "Brad, From Algebra"
    assert decoder.get_owner_display_name(unowned_plot) is None
    assert decoder.players[0].display_name == "Brad, From Algebra"


@_requires_save
def test_player_property_includes_saved_display_names() -> None:
    decoder = Civ5SaveDecoder(_SAVE_PATH)
    players = decoder.players

    assert players[0].display_name == "Brad, From Algebra"
    assert players[0].player_type is PlayerType.PLAYER
    assert players[3].display_name == "TXT_KEY_CITYSTATE_MEXICO"
    assert players[3].player_type is PlayerType.CITY_STATE
    assert decoder.players is players
    assert decoder.player_display_names is decoder.player_display_names
    assert decoder.player_display_names[0] == "Brad, From Algebra"
    assert decoder.player_display_names[22] == "TXT_KEY_CITYSTATE_MEXICO"
    assert set(decoder.player_display_names) == {
        player.player_index for player in players
    }


@pytest.mark.skipif(
    not _SINGLE_PLAYER_PATH.is_file(),
    reason="the local single-player Lekmod save is unavailable",
)
def test_computer_display_names_use_leader_or_city_name_keys() -> None:
    decoder = Civ5SaveDecoder(_SINGLE_PLAYER_PATH)
    players = {player.player_index: player for player in decoder.players}

    assert players[1].display_name == "LEADER_MACEDON"
    assert players[1].player_type is PlayerType.COMPUTER
    assert players[22].display_name == "TXT_KEY_CITYSTATE_KYRENE"
    assert players[22].player_type is PlayerType.CITY_STATE
    assert players[32].display_name == "TXT_KEY_CITYSTATE_GENEVA"
    assert players[63].display_name == "LEADER_BARBARIAN"
    assert players[63].player_type is PlayerType.BARBARIAN
    assert decoder.player_display_names[22] == "TXT_KEY_CITYSTATE_KYRENE"
    assert decoder.player_display_names[63] == "LEADER_BARBARIAN"
