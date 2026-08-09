"""Tests for the curated semantic and advanced raw API surfaces."""

from dataclasses import fields
from importlib import import_module
from pathlib import Path

import pytest

import savefile_reverse_engineer as public_api
import savefile_reverse_engineer.raw as raw_api
from savefile_reverse_engineer import (
    Civ5SaveDecoder,
    GameMode,
    SlotStatus,
)

_PROJECT_ROOT = Path(__file__).parent.parent
_SAVE_PATH = (
    _PROJECT_ROOT / "test-save-file/multi-player/AutoSave_Post_0076 AD-0040.Civ5Save"
)

pytestmark = pytest.mark.skipif(
    not _SAVE_PATH.is_file(), reason="the local Lekmod v34.11 save is unavailable"
)


def test_package_root_exports_only_the_curated_api() -> None:
    exports = set(public_api.__all__)

    assert "Civ5SaveDecoder" in exports
    assert "SaveSummary" in exports
    assert "GameSettings" in exports
    assert "SerializedFreeList" not in exports
    assert "CompressedChunk" not in exports
    assert "UnknownHeaderSpan" not in exports
    assert "PreGameArchive" not in exports
    assert "ObjectReference" not in exports
    assert "PlotFlags" not in exports


def test_raw_namespace_exports_exact_decoders_and_records() -> None:
    exports = set(raw_api.__all__)

    assert {
        "decode_header_bytes",
        "decompress_payload_bytes",
        "decode_plot_array_bytes",
        "decode_team_array_bytes",
        "decode_player_array_bytes",
        "Civ5SaveHeader",
        "SerializedFreeList",
    } <= exports
    assert all(not name.startswith("_") for name in exports)


def test_old_byte_decoder_import_names_are_removed() -> None:
    plot_module = import_module("savefile_reverse_engineer.cv_plot")
    team_module = import_module("savefile_reverse_engineer.cv_team")
    player_module = import_module("savefile_reverse_engineer.cv_player")

    assert not hasattr(plot_module, "decode_cv_plot_array_bytes")
    assert not hasattr(team_module, "decode_cv_team_array_bytes")
    assert not hasattr(player_module, "decode_cv_player_array_bytes")


def test_raw_header_and_payload_functions_match_the_decoder() -> None:
    decoder = Civ5SaveDecoder(_SAVE_PATH)
    save_bytes = _SAVE_PATH.read_bytes()
    header = raw_api.decode_header_bytes(save_bytes)

    assert header == decoder.raw_header
    assert raw_api.decompress_payload_bytes(save_bytes, header) == decoder.payload_bytes


def test_summary_settings_and_slots_are_cached_semantic_views() -> None:
    decoder = Civ5SaveDecoder(_SAVE_PATH)

    assert decoder.summary is decoder.summary
    assert decoder.settings is decoder.settings
    assert decoder.player_slots is decoder.player_slots
    assert decoder.raw_header is decoder.raw_header
    assert decoder.payload_bytes is decoder.payload_bytes

    assert decoder.summary.turn == 76
    assert decoder.summary.game_mode is GameMode.MULTIPLAYER
    assert decoder.summary.active_civilization_key == "CIVILIZATION_VENEZ"
    assert decoder.settings.game_name == "RacismLEKMOD v34.11"
    assert decoder.settings.climate_key == "CLIMATE_TEMPERATE"
    assert decoder.settings.world.grid_width == 56
    assert len(decoder.player_slots) == 64
    assert decoder.player_slots[0].player_index == 0
    assert decoder.player_slots[0].status is SlotStatus.TAKEN


def test_settings_omit_sensitive_and_format_only_fields() -> None:
    field_names = {field.name for field in fields(Civ5SaveDecoder(_SAVE_PATH).settings)}

    assert "admin_password" not in field_names
    assert "email_addresses" not in field_names
    assert "smtp_host" not in field_names
    assert "dummy_value" not in field_names
    assert "version" not in field_names


def test_city_and_unit_iterators_preserve_semantic_ownership() -> None:
    decoder = Civ5SaveDecoder(_SAVE_PATH)
    cities = tuple(decoder.iter_cities())
    units = tuple(decoder.iter_units())

    assert cities
    assert units
    assert all(city.owner_player_index >= 0 for city in cities)
    assert all(unit.owner_player_index >= 0 for unit in units)
    assert cities[0] == next(decoder.iter_players()).cities[0]
