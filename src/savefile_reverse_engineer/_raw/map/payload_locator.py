"""Locate major record arrays inside a decompressed Civilization V payload."""

from dataclasses import dataclass
from typing import NoReturn, override

from .._shared.binary_reader import LittleEndianReader, read_u32_count
from .._shared.free_list import read_free_list_header
from .decoder import locate_plot_array_end_impl

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

    message: str
    offset: int
    field: str

    def __init__(self, message: str, *, offset: int, field: str) -> None:
        self.message = message
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
class CvPlotLocation:
    """Location and dimensions of a serialized CvPlot array."""

    byte_offset: int
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class CvTeamLocation:
    """Location of a serialized CvTeam array."""

    byte_offset: int


def _consume_hashed_array(reader: _PayloadReader, field: str) -> None:
    count = read_u32_count(reader, field)
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
    count = read_u32_count(reader, field, expected=expected_count)
    for index in range(count):
        hash_value = reader.u32(f"{field}[{index}].type")
        if hash_value != 0:
            _ = reader.i32(f"{field}[{index}].value")


def _skip_cv_area(reader: _PayloadReader, area_index: int) -> None:
    # TODO(decoding): Decode the complete CvArea structure into a RawCvArea
    # model instead of consuming it only to locate the team array.
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
    # TODO(decoding): Decode area resource counts into RawCvAreaResources.
    _skip_hashed_int_array(
        reader,
        expected_count=_RESOURCE_COUNT,
        field=f"{field}.resource_counts",
    )
    # TODO(decoding): Decode area improvement counts into RawCvAreaImprovements.
    _skip_hashed_int_array(
        reader,
        expected_count=_IMPROVEMENT_COUNT,
        field=f"{field}.improvement_counts",
    )


def _skip_cv_landmass(reader: _PayloadReader, landmass_index: int) -> None:
    # TODO(decoding): Decode the complete CvLandmass structure into a
    # RawCvLandmass model instead of consuming it only to locate the team array.
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


def locate_cv_teams(payload: bytes, plot_location: CvPlotLocation) -> CvTeamLocation:
    """Return the location after plots, areas, and landmasses."""
    plot_end = locate_plot_array_end_impl(
        payload,
        byte_offset=plot_location.byte_offset,
        width=plot_location.width,
        height=plot_location.height,
    )
    reader = _PayloadReader(payload, plot_end)
    area_count = read_free_list_header(reader, "cv_map.areas").live_count
    for area_index in range(area_count):
        _skip_cv_area(reader, area_index)
    landmass_count = read_free_list_header(reader, "cv_map.landmasses").live_count
    for landmass_index in range(landmass_count):
        _skip_cv_landmass(reader, landmass_index)
    # TODO(decoding): Store AI map hints on RawCvMap instead of discarding them.
    _ = reader.i32("cv_map.ai_map_hints")
    return CvTeamLocation(byte_offset=reader.offset)


def locate_cv_plots(payload: bytes) -> CvPlotLocation:
    """Return the location and dimensions of the payload's CvPlot array."""
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

    # TODO(decoding): Store the confirmed map counters, latitudes, wrapping
    # flags, and GUID on RawCvMap instead of discarding this metadata.
    _ = reader.i32("cv_map.land_plot_count")
    _ = reader.i32("cv_map.owned_plot_count")
    _ = reader.i32("cv_map.natural_wonder_count")
    _ = reader.i32("cv_map.top_latitude")
    _ = reader.i32("cv_map.bottom_latitude")
    _ = reader.read_bool("cv_map.wrap_x")
    _ = reader.read_bool("cv_map.wrap_y")
    _ = reader.read_bytes(16, "cv_map.guid")
    # TODO(decoding): Decode total resource counts into RawCvMapResources.
    _consume_hashed_array(reader, "cv_map.total_resources")
    # TODO(decoding): Decode land resource counts into RawCvMapResources.
    _consume_hashed_array(reader, "cv_map.land_resources")

    plot_offset = reader.offset
    plot_count = width * height
    if plot_count > reader.remaining // _MINIMUM_CV_PLOT_LENGTH:
        reader.fail(
            f"{plot_count} plots cannot fit in the remaining payload bytes",
            offset=plot_offset,
            field="cv_map.plots",
        )

    return CvPlotLocation(byte_offset=plot_offset, width=width, height=height)


__all__: tuple[str, ...] = ()
