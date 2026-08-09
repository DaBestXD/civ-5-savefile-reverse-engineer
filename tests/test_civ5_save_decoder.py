"""Tests for the complete-file Civ5SaveDecoder interface."""

import zlib
from pathlib import Path

import pytest

from savefile_reverse_engineer import (
    Civ5SaveDecoder,
    Civ5SavePayloadDecodeError,
    CvPlotDecodeError,
    CvTeamDecodeError,
)

_PROJECT_ROOT = Path(__file__).parent.parent
_MULTIPLAYER_PATH = (
    _PROJECT_ROOT / "test-save-file/multi-player/AutoSave_0070 BC-0200.Civ5Save"
)
_SINGLE_PLAYER_PATH = (
    _PROJECT_ROOT / "test-save-file/single-player/before_state.Civ5Save"
)
_HAS_SAMPLE_SAVES = _MULTIPLAYER_PATH.is_file() and _SINGLE_PLAYER_PATH.is_file()
_SQLITE_SIGNATURE = b"SQLite format 3\x00"

pytestmark = pytest.mark.skipif(
    not _HAS_SAMPLE_SAVES,
    reason="local sample saves are unavailable",
)


def _decoder_with_payload(tmp_path: Path, payload: bytes, name: str) -> Civ5SaveDecoder:
    source = Civ5SaveDecoder(_MULTIPLAYER_PATH)
    compressed = zlib.compress(payload)
    save_bytes = _MULTIPLAYER_PATH.read_bytes()
    header_prefix = save_bytes[: source.raw_header.header_length]
    physical_save = (
        header_prefix + len(compressed).to_bytes(4, byteorder="little") + compressed
    )
    path = tmp_path / name
    _ = path.write_bytes(physical_save)
    return Civ5SaveDecoder(path)


def test_iterates_multiplayer_plots_as_semantic_records() -> None:
    decoder = Civ5SaveDecoder(_MULTIPLAYER_PATH)
    plots = tuple(decoder.iter_plots())

    assert len(plots) == 2_016
    assert (plots[0].x, plots[0].y) == (0, 0)
    assert (plots[-1].x, plots[-1].y) == (47, 41)

    repeated_first = next(decoder.iter_plots())
    assert repeated_first == plots[0]
    assert repeated_first is plots[0]


def test_iterates_single_player_map_size() -> None:
    plots = tuple(Civ5SaveDecoder(_SINGLE_PLAYER_PATH).iter_plots())

    assert len(plots) == 3_016
    assert (plots[-1].x, plots[-1].y) == (57, 51)


def test_rejects_missing_or_invalid_sqlite_framing(tmp_path: Path) -> None:
    payload = Civ5SaveDecoder(_MULTIPLAYER_PATH).payload_bytes
    sqlite_offset = payload.index(_SQLITE_SIGNATURE)

    missing_signature = bytearray(payload)
    missing_signature[sqlite_offset : sqlite_offset + len(_SQLITE_SIGNATURE)] = (
        b"Not a SQLite DB!"
    )
    missing_decoder = _decoder_with_payload(
        tmp_path, bytes(missing_signature), "missing-sqlite.Civ5Save"
    )
    with pytest.raises(Civ5SavePayloadDecodeError, match="was not found"):
        _ = missing_decoder.iter_plots()

    duplicate_signature = bytearray(payload)
    duplicate_signature[: len(_SQLITE_SIGNATURE)] = _SQLITE_SIGNATURE
    duplicate_decoder = _decoder_with_payload(
        tmp_path, bytes(duplicate_signature), "duplicate-sqlite.Civ5Save"
    )
    with pytest.raises(Civ5SavePayloadDecodeError, match="multiple"):
        _ = duplicate_decoder.iter_plots()

    invalid_length = bytearray(payload)
    invalid_length[sqlite_offset - 4 : sqlite_offset] = (1).to_bytes(
        4, byteorder="little"
    )
    length_decoder = _decoder_with_payload(
        tmp_path, bytes(invalid_length), "bad-sqlite-length.Civ5Save"
    )
    with pytest.raises(Civ5SavePayloadDecodeError, match="SQLite length"):
        _ = length_decoder.iter_plots()


@pytest.mark.parametrize(
    ("relative_offset", "replacement", "message"),
    (
        (0, (2).to_bytes(4, byteorder="little"), "CvMap version"),
        (4, (0).to_bytes(4, byteorder="little", signed=True), "map width"),
        (
            0x32,
            (0xFFFFFFFF).to_bytes(4, byteorder="little"),
            "count.*extends beyond",
        ),
    ),
)
def test_rejects_invalid_cv_map_framing(
    tmp_path: Path, relative_offset: int, replacement: bytes, message: str
) -> None:
    payload = Civ5SaveDecoder(_MULTIPLAYER_PATH).payload_bytes
    sqlite_offset = payload.index(_SQLITE_SIGNATURE)
    cv_map_offset = sqlite_offset + 0xC00
    invalid_payload = bytearray(payload)
    start = cv_map_offset + relative_offset
    invalid_payload[start : start + len(replacement)] = replacement
    decoder = _decoder_with_payload(
        tmp_path,
        bytes(invalid_payload),
        f"bad-cv-map-{relative_offset}.Civ5Save",
    )

    with pytest.raises(Civ5SavePayloadDecodeError, match=message):
        _ = decoder.iter_plots()


def test_plot_errors_report_absolute_payload_offsets(tmp_path: Path) -> None:
    payload = bytearray(Civ5SaveDecoder(_MULTIPLAYER_PATH).payload_bytes)
    first_plot_offset = 0x7EFF
    payload[first_plot_offset : first_plot_offset + 4] = (6).to_bytes(
        4, byteorder="little"
    )
    decoder = _decoder_with_payload(tmp_path, bytes(payload), "bad-first-plot.Civ5Save")
    plots = decoder.iter_plots()

    with pytest.raises(CvPlotDecodeError) as raised:
        _ = next(plots)

    assert raised.value.offset == first_plot_offset


def test_iterates_multiplayer_participant_teams() -> None:
    decoder = Civ5SaveDecoder(_MULTIPLAYER_PATH)
    teams = tuple(decoder.iter_teams())

    assert [team.team_index for team in teams] == [0, 1, 2, 22, 23, 24, 25, 63]

    repeated_first = next(decoder.iter_teams())
    assert repeated_first == teams[0]
    assert repeated_first is teams[0]


def test_iterates_single_player_teams_after_variable_map_tail() -> None:
    teams = tuple(Civ5SaveDecoder(_SINGLE_PLAYER_PATH).iter_teams())

    assert teams
    assert all(team.team_index >= 0 for team in teams)


def test_rejects_invalid_cv_map_free_list_framing(tmp_path: Path) -> None:
    payload = bytearray(Civ5SaveDecoder(_MULTIPLAYER_PATH).payload_bytes)
    area_list_offset = 0x31DB17
    payload[area_list_offset : area_list_offset + 4] = (0xFFFFFFFF).to_bytes(
        4, byteorder="little"
    )
    decoder = _decoder_with_payload(
        tmp_path, bytes(payload), "bad-area-free-list.Civ5Save"
    )

    with pytest.raises(Civ5SavePayloadDecodeError) as raised:
        _ = decoder.iter_teams()

    assert raised.value.offset == area_list_offset
    assert raised.value.field == "cv_map.areas.slot_count"


def test_accepts_maximum_cv_map_free_list_capacity(tmp_path: Path) -> None:
    payload = bytearray(Civ5SaveDecoder(_MULTIPLAYER_PATH).payload_bytes)
    area_list_offset = 0x31DB17
    original_slot_count = 64
    maximum_slot_count = 1 << 13
    payload[area_list_offset : area_list_offset + 4] = maximum_slot_count.to_bytes(
        4, byteorder="little"
    )
    next_free_indices_end = area_list_offset + 20 + original_slot_count * 4
    added_indices = b"\xff\xff\xff\xff" * (maximum_slot_count - original_slot_count)
    payload[next_free_indices_end:next_free_indices_end] = added_indices
    decoder = _decoder_with_payload(
        tmp_path, bytes(payload), "maximum-area-free-list.Civ5Save"
    )

    teams = tuple(decoder.iter_teams())

    assert len(teams) == 8


def test_team_errors_report_absolute_payload_offsets(tmp_path: Path) -> None:
    payload = bytearray(Civ5SaveDecoder(_MULTIPLAYER_PATH).payload_bytes)
    first_team_offset = 0x35298D
    payload[first_team_offset : first_team_offset + 4] = (2).to_bytes(
        4, byteorder="little"
    )
    decoder = _decoder_with_payload(tmp_path, bytes(payload), "bad-team.Civ5Save")

    teams = decoder.iter_teams()
    with pytest.raises(CvTeamDecodeError) as raised:
        _ = next(teams)

    assert raised.value.team_index == 0
    assert raised.value.offset == first_team_offset
