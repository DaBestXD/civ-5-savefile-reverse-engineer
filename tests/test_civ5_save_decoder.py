"""Tests for the complete-file Civ5SaveDecoder interface."""

import zlib
from pathlib import Path

import pytest

from savefile_reverse_engineer import (
    Civ5SaveDecoder,
    Civ5SavePayloadDecodeError,
    CvPlotDecodeError,
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


def _decoder_with_payload(
    tmp_path: Path, payload: bytes, name: str
) -> Civ5SaveDecoder:
    source = Civ5SaveDecoder(_MULTIPLAYER_PATH)
    compressed = zlib.compress(payload)
    save_bytes = _MULTIPLAYER_PATH.read_bytes()
    header_prefix = save_bytes[: source.header.header_length]
    physical_save = (
        header_prefix
        + len(compressed).to_bytes(4, byteorder="little")
        + compressed
    )
    path = tmp_path / name
    _ = path.write_bytes(physical_save)
    return Civ5SaveDecoder(path)


def test_iterates_multiplayer_plots_with_absolute_payload_offsets() -> None:
    decoder = Civ5SaveDecoder(_MULTIPLAYER_PATH)
    plots = tuple(decoder.iter_cv_plots())

    assert len(plots) == 2_016
    assert (plots[0].x, plots[0].y) == (0, 0)
    assert plots[0].byte_offset == 0x7EFF
    assert (plots[-1].x, plots[-1].y) == (47, 41)
    assert plots[-1].byte_offset + plots[-1].byte_length == 0x31DB17

    repeated_first = next(decoder.iter_cv_plots())
    assert repeated_first == plots[0]
    assert repeated_first is not plots[0]


def test_iterates_single_player_map_size() -> None:
    plots = tuple(Civ5SaveDecoder(_SINGLE_PLAYER_PATH).iter_cv_plots())

    assert len(plots) == 3_016
    assert plots[0].byte_offset == 0x36B1
    assert (plots[-1].x, plots[-1].y) == (57, 51)
    assert plots[-1].byte_offset + plots[-1].byte_length == 0x489AB1


def test_rejects_missing_or_invalid_sqlite_framing(tmp_path: Path) -> None:
    payload = Civ5SaveDecoder(_MULTIPLAYER_PATH).decompress_payload()
    sqlite_offset = payload.index(_SQLITE_SIGNATURE)

    missing_signature = bytearray(payload)
    missing_signature[sqlite_offset : sqlite_offset + len(_SQLITE_SIGNATURE)] = (
        b"Not a SQLite DB!"
    )
    missing_decoder = _decoder_with_payload(
        tmp_path, bytes(missing_signature), "missing-sqlite.Civ5Save"
    )
    with pytest.raises(Civ5SavePayloadDecodeError, match="was not found"):
        _ = missing_decoder.iter_cv_plots()

    duplicate_signature = bytearray(payload)
    duplicate_signature[: len(_SQLITE_SIGNATURE)] = _SQLITE_SIGNATURE
    duplicate_decoder = _decoder_with_payload(
        tmp_path, bytes(duplicate_signature), "duplicate-sqlite.Civ5Save"
    )
    with pytest.raises(Civ5SavePayloadDecodeError, match="multiple"):
        _ = duplicate_decoder.iter_cv_plots()

    invalid_length = bytearray(payload)
    invalid_length[sqlite_offset - 4 : sqlite_offset] = (1).to_bytes(
        4, byteorder="little"
    )
    length_decoder = _decoder_with_payload(
        tmp_path, bytes(invalid_length), "bad-sqlite-length.Civ5Save"
    )
    with pytest.raises(Civ5SavePayloadDecodeError, match="SQLite length"):
        _ = length_decoder.iter_cv_plots()


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
    payload = Civ5SaveDecoder(_MULTIPLAYER_PATH).decompress_payload()
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
        _ = decoder.iter_cv_plots()


def test_plot_errors_report_absolute_payload_offsets(tmp_path: Path) -> None:
    payload = bytearray(Civ5SaveDecoder(_MULTIPLAYER_PATH).decompress_payload())
    first_plot_offset = 0x7EFF
    payload[first_plot_offset : first_plot_offset + 4] = (6).to_bytes(
        4, byteorder="little"
    )
    decoder = _decoder_with_payload(
        tmp_path, bytes(payload), "bad-first-plot.Civ5Save"
    )
    plots = decoder.iter_cv_plots()

    with pytest.raises(CvPlotDecodeError) as raised:
        _ = next(plots)

    assert raised.value.offset == first_plot_offset
