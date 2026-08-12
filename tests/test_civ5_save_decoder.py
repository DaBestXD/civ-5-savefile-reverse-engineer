"""Tests for the complete-file Civ5SaveDecoder interface."""

import zlib
from pathlib import Path

import pytest

from savefile_reverse_engineer import (
    Civ5SaveDecoder,
    Civ5SaveHeaderDecodeError,
    Civ5SavePayloadDecodeError,
    Civ5SavePayloadDecompressionError,
    CvPlayerDecodeError,
    CvPlotDecodeError,
    CvTeamDecodeError,
)
from savefile_reverse_engineer._raw.header.decoder import (
    Civ5SaveHeaderDecodeError as RawHeaderDecodeError,
)
from savefile_reverse_engineer._raw.header.decoder import (
    Civ5SavePayloadDecompressionError as RawPayloadDecompressionError,
)
from savefile_reverse_engineer._raw.header.decoder import (
    decode_header_bytes_impl,
    decompress_payload_bytes_impl,
)
from savefile_reverse_engineer._raw.map.decoder import (
    CvPlotDecodeError as RawPlotDecodeError,
)
from savefile_reverse_engineer._raw.map.decoder import locate_plot_array_end_impl
from savefile_reverse_engineer._raw.map.payload_locator import (
    Civ5SavePayloadDecodeError as RawPayloadDecodeError,
)
from savefile_reverse_engineer._raw.map.payload_locator import (
    locate_cv_plots,
    locate_cv_teams,
)
from savefile_reverse_engineer._raw.player.decoder import (
    iterate_players_from_payload_impl,
)
from savefile_reverse_engineer._raw.player.infrastructure import (
    CvPlayerDecodeError as RawPlayerDecodeError,
)
from savefile_reverse_engineer._raw.team.decoder import (
    CvTeamDecodeError as RawTeamDecodeError,
)
from savefile_reverse_engineer._raw.team.decoder import iterate_teams_from_payload_impl

_PROJECT_ROOT = Path(__file__).parent.parent
_MULTIPLAYER_PATH = (
    _PROJECT_ROOT / "test-save-file/multi-player/AutoSave_0070 BC-0200.Civ5Save"
)
_SINGLE_PLAYER_PATH = (
    _PROJECT_ROOT / "test-save-file/single-player/before_state.Civ5Save"
)
_PLAYER_PATH = (
    _PROJECT_ROOT / "test-save-file/multi-player/AutoSave_Post_0076 AD-0040.Civ5Save"
)
_HAS_SAMPLE_SAVES = _MULTIPLAYER_PATH.is_file() and _SINGLE_PLAYER_PATH.is_file()
_SQLITE_SIGNATURE = b"SQLite format 3\x00"

pytestmark = pytest.mark.skipif(
    not _HAS_SAMPLE_SAVES,
    reason="local sample saves are unavailable",
)


def _decoder_with_payload(
    tmp_path: Path,
    payload: bytes,
    name: str,
    *,
    source_path: Path = _MULTIPLAYER_PATH,
) -> Civ5SaveDecoder:
    compressed = zlib.compress(payload)
    save_bytes = source_path.read_bytes()
    header = decode_header_bytes_impl(save_bytes)
    header_prefix = save_bytes[: header.header_length]
    physical_save = (
        header_prefix + len(compressed).to_bytes(4, byteorder="little") + compressed
    )
    path = tmp_path / name
    _ = path.write_bytes(physical_save)
    return Civ5SaveDecoder(path)


def _decoder_for_bytes(tmp_path: Path, data: bytes, name: str) -> Civ5SaveDecoder:
    path = tmp_path / name
    _ = path.write_bytes(data)
    return Civ5SaveDecoder(path)


def _payload(path: Path) -> bytes:
    save_bytes = path.read_bytes()
    return decompress_payload_bytes_impl(
        save_bytes, decode_header_bytes_impl(save_bytes)
    )


def test_public_header_errors_preserve_raw_context(tmp_path: Path) -> None:
    save_bytes = _MULTIPLAYER_PATH.read_bytes()
    decoder = _decoder_for_bytes(
        tmp_path, b"NOPE" + save_bytes[4:], "bad-signature.Civ5Save"
    )

    with pytest.raises(Civ5SaveHeaderDecodeError) as raised:
        _ = decoder.summary

    assert raised.value.offset == 0
    assert raised.value.field == "quick.signature"
    assert str(raised.value).startswith("quick.signature at physical byte offset 0x0")
    assert isinstance(raised.value.__cause__, RawHeaderDecodeError)


def test_public_decompression_errors_preserve_raw_cause(tmp_path: Path) -> None:
    save_bytes = _MULTIPLAYER_PATH.read_bytes()
    header = decode_header_bytes_impl(save_bytes)
    malformed_chunk = b"\x03\x00\x00\x00\x78\x9c\xff"
    decoder = _decoder_for_bytes(
        tmp_path,
        save_bytes[: header.header_length] + malformed_chunk,
        "invalid-zlib.Civ5Save",
    )

    with pytest.raises(Civ5SavePayloadDecompressionError, match="zlib payload") as raised:
        _ = decoder.plots

    cause = raised.value.__cause__
    assert isinstance(cause, RawPayloadDecompressionError)
    assert raised.value.args == (cause.message,)


def test_iterates_multiplayer_plots_as_semantic_records() -> None:
    decoder = Civ5SaveDecoder(_MULTIPLAYER_PATH)
    plots = decoder.plots

    assert len(plots) == 2_016
    assert (plots[0].x, plots[0].y) == (0, 0)
    assert (plots[-1].x, plots[-1].y) == (47, 41)

    assert decoder.plots is plots


def test_iterates_single_player_map_size() -> None:
    plots = Civ5SaveDecoder(_SINGLE_PLAYER_PATH).plots

    assert len(plots) == 3_016
    assert (plots[-1].x, plots[-1].y) == (57, 51)


def test_rejects_missing_or_invalid_sqlite_framing(tmp_path: Path) -> None:
    payload = _payload(_MULTIPLAYER_PATH)
    sqlite_offset = payload.index(_SQLITE_SIGNATURE)

    missing_signature = bytearray(payload)
    missing_signature[sqlite_offset : sqlite_offset + len(_SQLITE_SIGNATURE)] = (
        b"Not a SQLite DB!"
    )
    missing_decoder = _decoder_with_payload(
        tmp_path, bytes(missing_signature), "missing-sqlite.Civ5Save"
    )
    with pytest.raises(Civ5SavePayloadDecodeError, match="was not found") as raised:
        _ = missing_decoder.plots

    assert raised.value.offset == 0
    assert raised.value.field == "embedded_sqlite.signature"
    assert isinstance(raised.value.__cause__, RawPayloadDecodeError)

    duplicate_signature = bytearray(payload)
    duplicate_signature[: len(_SQLITE_SIGNATURE)] = _SQLITE_SIGNATURE
    duplicate_decoder = _decoder_with_payload(
        tmp_path, bytes(duplicate_signature), "duplicate-sqlite.Civ5Save"
    )
    with pytest.raises(Civ5SavePayloadDecodeError, match="multiple"):
        _ = duplicate_decoder.plots

    invalid_length = bytearray(payload)
    invalid_length[sqlite_offset - 4 : sqlite_offset] = (1).to_bytes(
        4, byteorder="little"
    )
    length_decoder = _decoder_with_payload(
        tmp_path, bytes(invalid_length), "bad-sqlite-length.Civ5Save"
    )
    with pytest.raises(Civ5SavePayloadDecodeError, match="SQLite length"):
        _ = length_decoder.plots


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
    payload = _payload(_MULTIPLAYER_PATH)
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
        _ = decoder.plots


def test_plot_errors_report_absolute_payload_offsets(tmp_path: Path) -> None:
    payload = bytearray(_payload(_MULTIPLAYER_PATH))
    first_plot_offset = locate_cv_plots(bytes(payload)).byte_offset
    payload[first_plot_offset : first_plot_offset + 4] = (6).to_bytes(
        4, byteorder="little"
    )
    decoder = _decoder_with_payload(tmp_path, bytes(payload), "bad-first-plot.Civ5Save")
    with pytest.raises(CvPlotDecodeError) as raised:
        _ = decoder.plots

    assert raised.value.offset == first_plot_offset
    assert raised.value.plot_index == 0
    assert str(raised.value).startswith(
        f"plot 0 at byte offset 0x{first_plot_offset:X}: unsupported CvPlot version"
    )
    assert isinstance(raised.value.__cause__, RawPlotDecodeError)


def test_iterates_multiplayer_participant_teams() -> None:
    decoder = Civ5SaveDecoder(_MULTIPLAYER_PATH)
    teams = decoder.teams

    assert [team.team_index for team in teams] == [0, 1, 2, 22, 23, 24, 25, 63]

    assert decoder.teams is teams

    first_team = teams[0]
    assert len(first_team.technologies) == 81
    agriculture = first_team.technologies[0]
    assert agriculture.technology.key == "TECH_AGRICULTURE"
    assert agriculture.unlocked
    assert agriculture.research_progress >= 0


def test_iterates_single_player_teams_after_variable_map_tail() -> None:
    teams = Civ5SaveDecoder(_SINGLE_PLAYER_PATH).teams

    assert teams
    assert all(team.team_index >= 0 for team in teams)


def test_rejects_invalid_cv_map_free_list_framing(tmp_path: Path) -> None:
    payload = bytearray(_payload(_MULTIPLAYER_PATH))
    valid_payload = bytes(payload)
    plot_location = locate_cv_plots(valid_payload)
    area_list_offset = locate_plot_array_end_impl(
        valid_payload,
        byte_offset=plot_location.byte_offset,
        width=plot_location.width,
        height=plot_location.height,
    )
    payload[area_list_offset : area_list_offset + 4] = (0xFFFFFFFF).to_bytes(
        4, byteorder="little"
    )
    decoder = _decoder_with_payload(
        tmp_path, bytes(payload), "bad-area-free-list.Civ5Save"
    )

    with pytest.raises(Civ5SavePayloadDecodeError) as raised:
        _ = decoder.teams

    assert raised.value.offset == area_list_offset
    assert raised.value.field == "cv_map.areas.slot_count"
    assert isinstance(raised.value.__cause__, RawPayloadDecodeError)


def test_accepts_maximum_cv_map_free_list_capacity(tmp_path: Path) -> None:
    payload = bytearray(_payload(_MULTIPLAYER_PATH))
    valid_payload = bytes(payload)
    plot_location = locate_cv_plots(valid_payload)
    area_list_offset = locate_plot_array_end_impl(
        valid_payload,
        byte_offset=plot_location.byte_offset,
        width=plot_location.width,
        height=plot_location.height,
    )
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

    teams = decoder.teams

    assert len(teams) == 8


def test_team_errors_report_absolute_payload_offsets(tmp_path: Path) -> None:
    payload = bytearray(_payload(_MULTIPLAYER_PATH))
    valid_payload = bytes(payload)
    plot_location = locate_cv_plots(valid_payload)
    first_team_offset = locate_cv_teams(valid_payload, plot_location).byte_offset
    payload[first_team_offset : first_team_offset + 4] = (2).to_bytes(
        4, byteorder="little"
    )
    decoder = _decoder_with_payload(tmp_path, bytes(payload), "bad-team.Civ5Save")

    with pytest.raises(CvTeamDecodeError) as raised:
        _ = decoder.teams

    assert raised.value.team_index == 0
    assert raised.value.offset == first_team_offset
    assert str(raised.value).startswith(
        f"team 0 at byte offset 0x{first_team_offset:X}: unsupported CvTeam version"
    )
    assert isinstance(raised.value.__cause__, RawTeamDecodeError)


@pytest.mark.skipif(
    not _PLAYER_PATH.is_file(), reason="the player-decoding save is unavailable"
)
def test_player_errors_cross_the_public_boundary(tmp_path: Path) -> None:
    payload = bytearray(_payload(_PLAYER_PATH))
    valid_payload = bytes(payload)
    plot_location = locate_cv_plots(valid_payload)
    team_location = locate_cv_teams(valid_payload, plot_location)
    teams = tuple(
        iterate_teams_from_payload_impl(
            valid_payload, byte_offset=team_location.byte_offset
        )
    )
    player_offset = teams[-1].byte_offset + teams[-1].byte_length
    expected_totals = tuple(
        (team.total_population, team.total_land) for team in teams
    )
    first_player = next(
        iterate_players_from_payload_impl(
            valid_payload,
            byte_offset=player_offset,
            expected_totals=expected_totals,
        )
    )
    invalid_version_offset = first_player.cities.entries[0].byte_offset
    payload[invalid_version_offset : invalid_version_offset + 4] = (7).to_bytes(
        4, "little"
    )
    decoder = _decoder_with_payload(
        tmp_path,
        bytes(payload),
        "bad-player-city.Civ5Save",
        source_path=_PLAYER_PATH,
    )

    with pytest.raises(CvPlayerDecodeError) as raised:
        _ = decoder.players

    assert raised.value.offset == invalid_version_offset
    assert raised.value.player_index == 0
    assert raised.value.field == "cities.entries[0].version"
    assert str(raised.value).startswith(
        "player 0 cities.entries[0].version at byte offset "
    )
    assert "unsupported version 7" in str(raised.value)
    assert isinstance(raised.value.__cause__, RawPlayerDecodeError)
