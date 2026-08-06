"""Tests for the physical Civilization V save-header decoder."""

from pathlib import Path

import pytest

from savefile_reverse_engineer import (
    Civ5SaveHeaderDecodeError,
    QuickGameMode,
    SlotClaim,
    SlotStatus,
    decode_civ5_save_header,
)

_PROJECT_ROOT = Path(__file__).parent.parent
_MULTIPLAYER_PATH = (
    _PROJECT_ROOT / "test-save-file/multi-player/AutoSave_0070 BC-0200.Civ5Save"
)
_SINGLE_PLAYER_PATH = (
    _PROJECT_ROOT / "test-save-file/single-player/before_state.Civ5Save"
)
_SAVE_CORPUS = _PROJECT_ROOT / "test-save-file"
_HAS_SAMPLE_SAVES = _MULTIPLAYER_PATH.is_file() and _SINGLE_PLAYER_PATH.is_file()
_SAVE_PATHS = tuple(path for path in _SAVE_CORPUS.rglob("*") if path.is_file())

pytestmark = pytest.mark.skipif(
    not _HAS_SAMPLE_SAVES,
    reason="local sample saves are unavailable",
)


def _replace_unsigned(data: bytes, offset: int, size: int, value: int) -> bytes:
    replacement = value.to_bytes(size, byteorder="little", signed=False)
    return data[:offset] + replacement + data[offset + size :]


def test_decodes_multiplayer_quick_header_and_chunk_boundary() -> None:
    header = decode_civ5_save_header(_MULTIPLAYER_PATH.read_bytes())
    quick = header["quick"]

    assert quick["signature"] == "CIV5"
    assert quick["outer_version"] == 8
    assert quick["game_version"] == "1.0.3.279 (403694)"
    assert quick["build"] == "403694"
    assert quick["turn"] == 70
    assert quick["game_mode"] == QuickGameMode.MULTIPLAYER
    assert quick["active_civilization"] == "CIVILIZATION_VENEZ"
    assert quick["difficulty"] == "HANDICAP_IMMORTAL"
    assert quick["current_era"] == "ERA_CLASSICAL"
    assert quick["world_size"] == "WORLDSIZE_TINY"
    assert len(quick["enabled_dlc"]) == 11
    assert quick["enabled_mods"] == ()
    assert header["first_chunk_length_offset"] == 0x2A0C
    assert header["header_length"] == 0x2A0C
    assert header["zlib_offset"] == 0x2A10
    assert header["compression_type"] == 2
    assert len(header["compressed_chunks"]) == 14
    assert header["compressed_chunks"][0]["length"] == 0x10000


def test_decodes_multiplayer_slots_and_account_metadata() -> None:
    players = decode_civ5_save_header(_MULTIPLAYER_PATH.read_bytes())["slot_hints"][
        "players"
    ]

    assert len(players) == 64
    for player in players[:3]:
        display_name = player["display_name"]
        steam_id = player["steam_id"]

        assert display_name
        assert steam_id is not None
        assert len(steam_id) == 17
        assert steam_id.isascii()
        assert steam_id.isdigit()
        assert player["raw_nickname"] == f"{display_name}@{steam_id}"

    assert players[0]["status"] == SlotStatus.TAKEN
    assert players[0]["claim"] == SlotClaim.ASSIGNED
    assert players[0]["civilization_key"] == "CIVILIZATION_VENEZ"
    assert players[0]["leader_key"] == "LEADER_VENEZ"


def test_decodes_complete_pregame_archive() -> None:
    pregame = decode_civ5_save_header(_MULTIPLAYER_PATH.read_bytes())["pregame"]

    assert pregame["version"] == 6
    assert pregame["active_player"] == 1
    assert pregame["game_name"] == "RacismLEKMOD v34.11"
    assert pregame["game_turn"] == 70
    assert pregame["version_string"] == "403694 FINAL_RELEASE"
    assert pregame["climate_info"]["type"] == "CLIMATE_TEMPERATE"
    assert pregame["sea_level_info"]["type"] == "SEALEVEL_MEDIUM"
    assert pregame["turn_timer"]["type"] == "TURNTIMER_FAST"
    assert pregame["world_info"]["version"] == 2
    assert pregame["world_info"]["type"] == "WORLDSIZE_TINY"
    assert pregame["world_info"]["grid_width"] == 56
    assert len(pregame["game_options"]) == 9
    assert pregame["map_options"] == ()
    assert len(pregame["turn_notify_email_addresses"]) == 64


def test_decodes_single_player_without_inferring_mod_version() -> None:
    header = decode_civ5_save_header(_SINGLE_PLAYER_PATH.read_bytes())
    quick = header["quick"]

    assert quick["turn"] == 4
    assert quick["game_mode"] == QuickGameMode.SINGLE_PLAYER
    assert quick["active_civilization"] == "CIVILIZATION_AMERICA"
    assert quick["difficulty"] == "HANDICAP_PRINCE"
    assert quick["world_size"] == "WORLDSIZE_SMALL"
    assert len(quick["enabled_dlc"]) == 14
    assert quick["enabled_mods"] == ()
    assert header["pregame"]["game_name"] == "My Game"
    assert header["pregame"]["version_string"] == "403694 FINAL_RELEASE"
    assert header["zlib_offset"] == 0x2820
    assert header["slot_hints"]["players"][0]["steam_id"] is None


def test_preserves_unknown_bridge_spans() -> None:
    header = decode_civ5_save_header(_MULTIPLAYER_PATH.read_bytes())
    spans = header["unknown_spans"]

    assert len(spans) == 4
    for span in spans:
        start = span["byte_offset"]
        end = start + span["byte_length"]
        assert span["data"] == _MULTIPLAYER_PATH.read_bytes()[start:end]


def test_boundary_is_structural_and_supports_multiple_chunks() -> None:
    data = _MULTIPLAYER_PATH.read_bytes()
    decoded = decode_civ5_save_header(data)
    header_end = decoded["header_length"]
    metadata_offset = decoded["unknown_spans"][2]["byte_offset"]
    data_with_embedded_zlib = (
        data[:metadata_offset] + b"\x78\x9c" + data[metadata_offset + 2 : header_end]
    )
    synthetic_tail = b"\x04\x00\x00\x00\x78\x9cAA\x03\x00\x00\x00BBB"

    result = decode_civ5_save_header(data_with_embedded_zlib + synthetic_tail)

    assert result["zlib_offset"] == header_end + 4
    assert len(result["compressed_chunks"]) == 2
    assert result["compressed_chunks"][1]["length"] == 3


def test_rejects_invalid_signature_version_and_chunks() -> None:
    data = _MULTIPLAYER_PATH.read_bytes()
    decoded = decode_civ5_save_header(data)
    header_end = decoded["header_length"]

    with pytest.raises(Civ5SaveHeaderDecodeError, match="quick.signature"):
        _ = decode_civ5_save_header(b"NOPE" + data[4:])
    with pytest.raises(Civ5SaveHeaderDecodeError, match="outer_version"):
        _ = decode_civ5_save_header(_replace_unsigned(data, 4, 4, 7))
    with pytest.raises(Civ5SaveHeaderDecodeError, match="length is zero"):
        _ = decode_civ5_save_header(data[:header_end] + b"\x00\x00\x00\x00")
    with pytest.raises(Civ5SaveHeaderDecodeError, match="invalid RFC 1950"):
        _ = decode_civ5_save_header(data[:header_end] + b"\x02\x00\x00\x00NO")
    with pytest.raises(Civ5SaveHeaderDecodeError, match="truncated"):
        _ = decode_civ5_save_header(data[:header_end] + b"\x05\x00\x00\x00\x78\x9c")


def test_supplied_save_count() -> None:
    assert len(_SAVE_PATHS) == 61


@pytest.mark.parametrize(
    "path",
    _SAVE_PATHS,
    ids=tuple(path.name for path in _SAVE_PATHS),
)
def test_supplied_save_decodes(path: Path) -> None:
    header = decode_civ5_save_header(path.read_bytes())

    assert header["quick"]["build"] == "403694"
    assert header["pregame"]["version"] == 6
    assert len(header["compressed_chunks"]) > 0
