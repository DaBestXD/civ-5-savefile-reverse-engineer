"""Tests for the bytes-only CvPlot array decoder."""

from collections.abc import Iterator
from dataclasses import fields
from pathlib import Path

import pytest

from savefile_reverse_engineer.raw import (
    CvPlot,
    CvPlotDecodeError,
    FlowDirection,
    PlotType,
    RouteType,
    TerrainType,
    decode_plot_array_bytes,
)

_FIXTURE_PATH = Path(__file__).parent / "test_data/cv_plot/turn_76_plot_array.bin"
_FIXTURE_BYTES = _FIXTURE_PATH.read_bytes()
_BASE_PLOT_LENGTH = 0x625
_BUILD_PLOT_OFFSET = 640_211
_BUILD_PLOT_LENGTH = 2_001
_LAST_PLOT_OFFSET = 3_240_003


def _replace_unsigned(data: bytes, offset: int, size: int, value: int) -> bytes:
    replacement = value.to_bytes(size, byteorder="little", signed=False)
    return data[:offset] + replacement + data[offset + size :]


def _consume(data: bytes) -> tuple[CvPlot, ...]:
    return tuple(decode_plot_array_bytes(data))


def test_turn_76_fixture_decodes_completely() -> None:
    plots = _consume(_FIXTURE_BYTES)

    assert len(plots) == 2_016
    assert (plots[0].x, plots[0].y) == (0, 0)
    assert (plots[-1].x, plots[-1].y) == (47, 41)
    assert plots[-1].byte_offset == _LAST_PLOT_OFFSET
    assert plots[-1].byte_offset + plots[-1].byte_length == len(_FIXTURE_BYTES)


def test_decodes_fixed_fields_and_embedded_arrays() -> None:
    plot = next(decode_plot_array_bytes(_FIXTURE_BYTES))

    assert plot.byte_length == _BASE_PLOT_LENGTH
    assert isinstance(plot.plot_type, PlotType)
    assert isinstance(plot.terrain, TerrainType)
    assert isinstance(plot.route, RouteType)
    assert isinstance(plot.east_river_flow, FlowDirection)
    assert len(plot.found_values) == 80
    assert len(plot.player_city_radius_counts) == 80
    assert len(plot.visibility_counts) == 80
    assert len(plot.revealed_owners) == 80
    assert len(plot.resource_force_reveals) == 80
    assert len(plot.revealed_improvements) == 80
    assert len(plot.revealed_routes) == 80
    assert len(plot.no_settling) == 22
    assert len(plot.invisible_visibility) == 80
    assert {field.name for field in fields(plot.yields)} == {
        "food",
        "production",
        "gold",
        "science",
        "culture",
        "faith",
        "golden_age_points",
    }


def test_resolves_known_hashes_and_preserves_zero() -> None:
    target: CvPlot | None = None
    for index, plot in enumerate(decode_plot_array_bytes(_FIXTURE_BYTES)):
        if index == 408:
            target = plot
            break

    assert target is not None, "plot 408 was not decoded"
    assert target.resource.name == "RESOURCE_WHEAT"
    assert target.resource.hash_value == 0x2E1008E0
    assert target.improvement.name == "IMPROVEMENT_FARM"
    assert target.feature.hash_value == 0
    assert target.feature.name is None


def test_decodes_build_progress_and_unit_references() -> None:
    build_blob = _FIXTURE_BYTES[
        _BUILD_PLOT_OFFSET : _BUILD_PLOT_OFFSET + _BUILD_PLOT_LENGTH
    ]
    # A standalone array must start at (0, 0), so retain its bytes but
    # replace only the two serialized coordinate fields for this test.
    build_blob = _replace_unsigned(build_blob, 4, 2, 0)
    build_blob = _replace_unsigned(build_blob, 6, 2, 0)
    plot = next(decode_plot_array_bytes(build_blob))

    assert plot.outer_build_count == 70
    assert plot.inner_build_count == 70
    assert len(plot.build_progress) == 70
    assert plot.build_progress[2].build.name == "BUILD_FARM"
    assert plot.build_progress[45].progress is None
    assert plot.build_progress[46].build.name is None
    assert len(plot.unit_references) == 1


def test_unknown_hash_keeps_integer_and_none_name() -> None:
    unknown_hash = 0x12345678
    data = _replace_unsigned(_FIXTURE_BYTES, 0x3C, 4, unknown_hash)
    plot = next(decode_plot_array_bytes(data))

    assert plot.feature.hash_value == unknown_hash
    assert plot.feature.name is None


def test_supports_archaeology_version_one() -> None:
    base_plot = _FIXTURE_BYTES[:_BASE_PLOT_LENGTH]
    archaeology_offset = _BASE_PLOT_LENGTH - 24
    version_one = _replace_unsigned(base_plot, archaeology_offset, 4, 1)[:-4]
    plot = next(decode_plot_array_bytes(version_one))

    assert plot.archaeology.version == 1
    assert plot.archaeology.work is None
    assert plot.byte_length == _BASE_PLOT_LENGTH - 4


def test_iterator_is_lazy_after_first_record() -> None:
    first_plot_and_garbage = _FIXTURE_BYTES[:_BASE_PLOT_LENGTH] + b"\0\0\0\0"
    iterator: Iterator[CvPlot] = decode_plot_array_bytes(first_plot_and_garbage)

    first = next(iterator)
    assert (first.x, first.y) == (0, 0)
    with pytest.raises(CvPlotDecodeError):
        _ = next(iterator)


def test_rejects_empty_and_truncated_input() -> None:
    with pytest.raises(CvPlotDecodeError, match="empty"):
        _ = decode_plot_array_bytes(b"")
    with pytest.raises(CvPlotDecodeError, match="truncated"):
        _ = _consume(_FIXTURE_BYTES[:100])


def test_rejects_invalid_version_boolean_and_enum() -> None:
    invalid_version = _replace_unsigned(_FIXTURE_BYTES, 0, 4, 6)
    invalid_boolean = _replace_unsigned(_FIXTURE_BYTES, 0x2B, 1, 2)
    invalid_enum = _replace_unsigned(_FIXTURE_BYTES, 0x3A, 1, 9)

    with pytest.raises(CvPlotDecodeError, match="CvPlot version"):
        _ = next(decode_plot_array_bytes(invalid_version))
    with pytest.raises(CvPlotDecodeError, match="Boolean"):
        _ = next(decode_plot_array_bytes(invalid_boolean))
    with pytest.raises(CvPlotDecodeError, match="plot_type"):
        _ = next(decode_plot_array_bytes(invalid_enum))


def test_rejects_script_data_and_unsupported_counts() -> None:
    script_data = _replace_unsigned(_FIXTURE_BYTES, 0x563, 1, 1)
    invalid_build_count = _replace_unsigned(_FIXTURE_BYTES, 0x564, 4, 1)
    invalid_unit_count = _replace_unsigned(_FIXTURE_BYTES, 0x608, 4, 0xFFFFFFFF)

    with pytest.raises(CvPlotDecodeError, match="script data"):
        _ = next(decode_plot_array_bytes(script_data))
    with pytest.raises(CvPlotDecodeError, match="outer_build_count"):
        _ = next(decode_plot_array_bytes(invalid_build_count))
    with pytest.raises(CvPlotDecodeError, match="unit_reference_count"):
        _ = next(decode_plot_array_bytes(invalid_unit_count))


def test_rejects_unsupported_archaeology_and_trailing_bytes() -> None:
    archaeology_offset = _BASE_PLOT_LENGTH - 24
    invalid_archaeology = _replace_unsigned(_FIXTURE_BYTES, archaeology_offset, 4, 3)

    with pytest.raises(CvPlotDecodeError, match="archaeology version"):
        _ = next(decode_plot_array_bytes(invalid_archaeology))
    with pytest.raises(CvPlotDecodeError):
        _ = _consume(_FIXTURE_BYTES + b"\0\0\0\0")


def test_rejects_coordinate_errors_and_incomplete_final_row() -> None:
    invalid_second_x = _replace_unsigned(_FIXTURE_BYTES, _BASE_PLOT_LENGTH + 4, 2, 9)
    missing_final_plot = _FIXTURE_BYTES[:_LAST_PLOT_OFFSET]

    with pytest.raises(CvPlotDecodeError, match="row-major"):
        _ = _consume(invalid_second_x)
    with pytest.raises(CvPlotDecodeError, match="final row is incomplete"):
        _ = _consume(missing_final_plot)
