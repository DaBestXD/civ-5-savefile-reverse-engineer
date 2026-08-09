"""Decode a complete Lekmod v34.11 CvPlot array from bytes."""

from collections.abc import Callable, Iterator, Mapping
from enum import IntEnum
from typing import NoReturn, override

from ._binary_reader import LittleEndianReader
from ._cv_plot_hashes import (
    BUILD_HASH_NAMES,
    FEATURE_HASH_NAMES,
    IMPROVEMENT_HASH_NAMES,
    RESOURCE_HASH_NAMES,
)
from .cv_plot_types import (
    ArchaeologyData,
    BuildProgress,
    CvPlot,
    FlowDirection,
    HashedType,
    ObjectReference,
    PlotFlags,
    PlotType,
    PlotYields,
    RouteType,
    TerrainType,
)

_PLOT_VERSION = 7
_PLAYER_TEAM_COUNT = 80
_MAJOR_CIVILIZATION_COUNT = 22
_REVEALED_WORD_COUNT = 4
_LEKMOD_BUILD_SLOT_COUNT = 70
_MINIMUM_ARCHAEOLOGY_LENGTH = 20


class CvPlotDecodeError(ValueError):
    """A malformed or unsupported value in a serialized CvPlot array."""

    offset: int
    plot_index: int

    def __init__(self, message: str, *, offset: int, plot_index: int) -> None:
        self.offset = offset
        self.plot_index = plot_index
        super().__init__(f"plot {plot_index} at byte offset 0x{offset:X}: {message}")


class _Reader(LittleEndianReader):
    __slots__: tuple[str, ...] = ("plot_index",)
    _bounds_error_suffix: str = "plot-array bytes"

    plot_index: int

    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.plot_index = 0

    @override
    def fail(
        self,
        message: str,
        *,
        offset: int | None = None,
        field: str | None = None,
    ) -> NoReturn:
        del field
        raise CvPlotDecodeError(
            message,
            offset=self.offset if offset is None else offset,
            plot_index=self.plot_index,
        )


def _read_enum[EnumType: IntEnum](
    reader: _Reader,
    enum_type: type[EnumType],
    raw_value: int,
    *,
    field: str,
    offset: int,
) -> EnumType:
    try:
        return enum_type(raw_value)
    except ValueError:
        reader.fail(f"unsupported {field} value {raw_value}", offset=offset)


def _read_sized_enum[EnumType: IntEnum](
    reader: _Reader,
    enum_type: type[EnumType],
    read_raw: Callable[[str], int],
    *,
    field: str,
) -> EnumType:
    offset = reader.offset
    return _read_enum(reader, enum_type, read_raw(field), field=field, offset=offset)


def _read_i8_enum[EnumType: IntEnum](
    reader: _Reader, enum_type: type[EnumType], *, field: str
) -> EnumType:
    return _read_sized_enum(reader, enum_type, reader.i8, field=field)


def _read_i16_enum[EnumType: IntEnum](
    reader: _Reader, enum_type: type[EnumType], *, field: str
) -> EnumType:
    return _read_sized_enum(reader, enum_type, reader.i16, field=field)


def _read_i32_enum[EnumType: IntEnum](
    reader: _Reader, enum_type: type[EnumType], *, field: str
) -> EnumType:
    return _read_sized_enum(reader, enum_type, reader.i32, field=field)


def _resolve_hash(hash_value: int, names: Mapping[int, str]) -> HashedType:
    return HashedType(hash_value=hash_value, name=names.get(hash_value))


def _read_hash(reader: _Reader, names: Mapping[int, str], *, field: str) -> HashedType:
    return _resolve_hash(reader.u32(field), names)


def _read_reference(reader: _Reader, *, field: str) -> ObjectReference:
    return ObjectReference(
        owner=reader.i32(f"{field}.owner"),
        object_id=reader.i32(f"{field}.object_id"),
    )


def _read_flags(reader: _Reader) -> PlotFlags:
    return PlotFlags(
        starting_plot=reader.read_bool("flags.starting_plot"),
        hills=reader.read_bool("flags.hills"),
        northeast_of_river=reader.read_bool("flags.northeast_of_river"),
        west_of_river=reader.read_bool("flags.west_of_river"),
        northwest_of_river=reader.read_bool("flags.northwest_of_river"),
        potential_city_work=reader.read_bool("flags.potential_city_work"),
        improvement_pillaged=reader.read_bool("flags.improvement_pillaged"),
        route_pillaged=reader.read_bool("flags.route_pillaged"),
        route_was_previously_pillaged=reader.read_bool(
            "flags.route_was_previously_pillaged"
        ),
        barbarian_camp_not_converting=reader.read_bool(
            "flags.barbarian_camp_not_converting"
        ),
        rough_feature=reader.read_bool("flags.rough_feature"),
        resource_linked_city_active=reader.read_bool(
            "flags.resource_linked_city_active"
        ),
        improved_by_major_civilization_gift=reader.read_bool(
            "flags.improved_by_major_civilization_gift"
        ),
        forced_fresh_water=reader.read_bool("flags.forced_fresh_water"),
    )


def _read_yields(reader: _Reader) -> PlotYields:
    return PlotYields(
        food=reader.i16("yields.food"),
        production=reader.i16("yields.production"),
        gold=reader.i16("yields.gold"),
        science=reader.i16("yields.science"),
        culture=reader.i16("yields.culture"),
        faith=reader.i16("yields.faith"),
        golden_age_points=reader.i16("yields.golden_age_points"),
    )


def _read_build_progress(
    reader: _Reader, outer_count: int
) -> tuple[int | None, tuple[BuildProgress, ...]]:
    if outer_count == 0:
        return None, ()
    if outer_count != _LEKMOD_BUILD_SLOT_COUNT:
        reader.fail(
            f"outer_build_count is {outer_count}, expected 0 or {_LEKMOD_BUILD_SLOT_COUNT}"
        )

    inner_count = reader.i32("inner_build_count")
    if inner_count != _LEKMOD_BUILD_SLOT_COUNT:
        reader.fail(
            f"inner_build_count is {inner_count}, expected {_LEKMOD_BUILD_SLOT_COUNT}"
        )

    minimum_tail = (_PLAYER_TEAM_COUNT * 2) + 4 + 1 + _MINIMUM_ARCHAEOLOGY_LENGTH
    reader.ensure_count_fits(
        inner_count,
        item_size=4,
        reserved_bytes=minimum_tail,
        field="inner_build_count",
    )
    entries: list[BuildProgress] = []
    for build_index in range(inner_count):
        hash_value = reader.u32(f"build_progress[{build_index}].build")
        progress = (
            None
            if hash_value == 0
            else reader.i16(f"build_progress[{build_index}].progress")
        )
        entries.append(
            BuildProgress(
                build=_resolve_hash(hash_value, BUILD_HASH_NAMES),
                progress=progress,
            )
        )
    return inner_count, tuple(entries)


def _read_archaeology(reader: _Reader) -> ArchaeologyData:
    version_offset = reader.offset
    version = reader.u32("archaeology.version")
    if version not in (1, 2):
        reader.fail(f"unsupported archaeology version {version}", offset=version_offset)
    artifact_type = reader.i32("archaeology.artifact_type")
    era = reader.i32("archaeology.era")
    player_1 = reader.i32("archaeology.player_1")
    player_2 = reader.i32("archaeology.player_2")
    work = reader.i32("archaeology.work") if version == 2 else None
    return ArchaeologyData(
        version=version,
        artifact_type=artifact_type,
        era=era,
        player_1=player_1,
        player_2=player_2,
        work=work,
    )


def _read_plot(reader: _Reader) -> CvPlot:
    start = reader.offset
    version = reader.u32("version")
    if version != _PLOT_VERSION:
        reader.fail(
            f"unsupported CvPlot version {version}; expected {_PLOT_VERSION}",
            offset=start,
        )

    x = reader.i16("x")
    y = reader.i16("y")
    area = reader.i32("area")
    feature_variety = reader.i8("feature_variety")
    ownership_duration = reader.i16("ownership_duration")
    improvement_duration = reader.i16("improvement_duration")
    upgrade_progress = reader.i16("upgrade_progress")
    culture = reader.i16("culture")
    major_civilizations_revealed = reader.i8("major_civilizations_revealed")
    city_radius_count = reader.i8("city_radius_count")
    recon_count = reader.i8("recon_count")
    river_crossing_count = reader.i8("river_crossing_count")
    resource_quantity = reader.i8("resource_quantity")
    builder_scratch_player = reader.i8("builder_scratch_player")
    builder_scratch_turn = reader.i16("builder_scratch_turn")
    builder_scratch_value = reader.i16("builder_scratch_value")
    builder_scratch_route = _read_i32_enum(
        reader, RouteType, field="builder_scratch_route"
    )
    landmass = reader.i32("landmass")
    trade_route_bit_flags = reader.u32("trade_route_bit_flags")
    flags = _read_flags(reader)
    owner = reader.i8("owner")
    plot_type = _read_i8_enum(reader, PlotType, field="plot_type")
    terrain = _read_i8_enum(reader, TerrainType, field="terrain")
    feature = _read_hash(reader, FEATURE_HASH_NAMES, field="feature")
    resource = _read_hash(reader, RESOURCE_HASH_NAMES, field="resource")
    improvement = _read_hash(reader, IMPROVEMENT_HASH_NAMES, field="improvement")
    under_construction_improvement = _read_hash(
        reader,
        IMPROVEMENT_HASH_NAMES,
        field="under_construction_improvement",
    )
    player_that_built_improvement = reader.i8("player_that_built_improvement")
    player_responsible_for_improvement = reader.i8("player_responsible_for_improvement")
    player_responsible_for_route = reader.i8("player_responsible_for_route")
    player_that_cleared_camp = reader.i8("player_that_cleared_camp")
    route = _read_i8_enum(reader, RouteType, field="route")
    world_anchor = reader.i8("world_anchor")
    world_anchor_data = reader.i8("world_anchor_data")
    east_river_flow = _read_i8_enum(reader, FlowDirection, field="east_river_flow")
    southeast_river_flow = _read_i8_enum(
        reader, FlowDirection, field="southeast_river_flow"
    )
    southwest_river_flow = _read_i8_enum(
        reader, FlowDirection, field="southwest_river_flow"
    )

    plot_city = _read_reference(reader, field="plot_city")
    working_city = _read_reference(reader, field="working_city")
    working_city_override = _read_reference(reader, field="working_city_override")
    resource_linked_city = _read_reference(reader, field="resource_linked_city")
    purchase_city = _read_reference(reader, field="purchase_city")
    yields = _read_yields(reader)

    found_values = tuple(
        reader.i32(f"found_values[{index}]") for index in range(_PLAYER_TEAM_COUNT)
    )
    player_city_radius_counts = tuple(
        reader.i8(f"player_city_radius_counts[{index}]")
        for index in range(_PLAYER_TEAM_COUNT)
    )
    visibility_counts = tuple(
        reader.i16(f"visibility_counts[{index}]") for index in range(_PLAYER_TEAM_COUNT)
    )
    revealed_owners = tuple(
        reader.i8(f"revealed_owners[{index}]") for index in range(_PLAYER_TEAM_COUNT)
    )
    river_crossing = reader.i8("river_crossing")
    revealed_bits = tuple(
        reader.u32(f"revealed_bits[{index}]") for index in range(_REVEALED_WORD_COUNT)
    )
    resource_force_reveals = tuple(
        reader.read_bool(f"resource_force_reveals[{index}]")
        for index in range(_PLAYER_TEAM_COUNT)
    )
    revealed_improvements = tuple(
        _read_hash(
            reader,
            IMPROVEMENT_HASH_NAMES,
            field=f"revealed_improvements[{index}]",
        )
        for index in range(_PLAYER_TEAM_COUNT)
    )
    revealed_routes = tuple(
        _read_i16_enum(reader, RouteType, field=f"revealed_routes[{index}]")
        for index in range(_PLAYER_TEAM_COUNT)
    )
    no_settling = tuple(
        reader.read_bool(f"no_settling[{index}]")
        for index in range(_MAJOR_CIVILIZATION_COUNT)
    )
    script_data_offset = reader.offset
    has_script_data = reader.read_bool("has_script_data")
    if has_script_data:
        reader.fail(
            "script data is unsupported because its string framing is unconfirmed",
            offset=script_data_offset,
        )

    outer_build_count = reader.i32("outer_build_count")
    inner_build_count, build_progress = _read_build_progress(reader, outer_build_count)
    invisible_visibility = tuple(
        reader.i16(f"invisible_visibility[{index}]")
        for index in range(_PLAYER_TEAM_COUNT)
    )

    unit_count = reader.u32("unit_reference_count")
    reader.ensure_count_fits(
        unit_count,
        item_size=8,
        reserved_bytes=1 + _MINIMUM_ARCHAEOLOGY_LENGTH,
        field="unit_reference_count",
    )
    unit_references = tuple(
        _read_reference(reader, field=f"unit_references[{index}]")
        for index in range(unit_count)
    )
    continent = reader.i8("continent")
    archaeology = _read_archaeology(reader)

    return CvPlot(
        byte_offset=start,
        byte_length=reader.offset - start,
        version=version,
        x=x,
        y=y,
        area=area,
        feature_variety=feature_variety,
        ownership_duration=ownership_duration,
        improvement_duration=improvement_duration,
        upgrade_progress=upgrade_progress,
        culture=culture,
        major_civilizations_revealed=major_civilizations_revealed,
        city_radius_count=city_radius_count,
        recon_count=recon_count,
        river_crossing_count=river_crossing_count,
        resource_quantity=resource_quantity,
        builder_scratch_player=builder_scratch_player,
        builder_scratch_turn=builder_scratch_turn,
        builder_scratch_value=builder_scratch_value,
        builder_scratch_route=builder_scratch_route,
        landmass=landmass,
        trade_route_bit_flags=trade_route_bit_flags,
        flags=flags,
        owner=owner,
        plot_type=plot_type,
        terrain=terrain,
        feature=feature,
        resource=resource,
        improvement=improvement,
        under_construction_improvement=under_construction_improvement,
        player_that_built_improvement=player_that_built_improvement,
        player_responsible_for_improvement=player_responsible_for_improvement,
        player_responsible_for_route=player_responsible_for_route,
        player_that_cleared_camp=player_that_cleared_camp,
        route=route,
        world_anchor=world_anchor,
        world_anchor_data=world_anchor_data,
        east_river_flow=east_river_flow,
        southeast_river_flow=southeast_river_flow,
        southwest_river_flow=southwest_river_flow,
        plot_city=plot_city,
        working_city=working_city,
        working_city_override=working_city_override,
        resource_linked_city=resource_linked_city,
        purchase_city=purchase_city,
        yields=yields,
        found_values=found_values,
        player_city_radius_counts=player_city_radius_counts,
        visibility_counts=visibility_counts,
        revealed_owners=revealed_owners,
        river_crossing=river_crossing,
        revealed_bits=revealed_bits,
        resource_force_reveals=resource_force_reveals,
        revealed_improvements=revealed_improvements,
        revealed_routes=revealed_routes,
        no_settling=no_settling,
        has_script_data=has_script_data,
        outer_build_count=outer_build_count,
        inner_build_count=inner_build_count,
        build_progress=build_progress,
        invisible_visibility=invisible_visibility,
        unit_references=unit_references,
        continent=continent,
        archaeology=archaeology,
    )


def _validate_coordinates(
    reader: _Reader, plot: CvPlot, plot_index: int, width: int | None
) -> int | None:
    x = plot.x
    y = plot.y
    offset = plot.byte_offset + 4
    if plot_index == 0:
        if (x, y) != (0, 0):
            reader.fail(
                f"first coordinates are ({x}, {y}), expected (0, 0)", offset=offset
            )
        return width

    if width is None:
        if y == 0 and x == plot_index:
            return None
        if y == 1 and x == 0:
            return plot_index
        reader.fail(
            f"coordinates ({x}, {y}) break row-major order before width could be inferred",
            offset=offset,
        )

    expected_x = plot_index % width
    expected_y = plot_index // width
    if (x, y) != (expected_x, expected_y):
        reader.fail(
            f"coordinates are ({x}, {y}), expected ({expected_x}, {expected_y})",
            offset=offset,
        )
    return width


def _iterate_cv_plot_array(plot_array_bytes: bytes) -> Iterator[CvPlot]:
    reader = _Reader(plot_array_bytes)
    width: int | None = None
    plot_count = 0
    while reader.remaining > 0:
        reader.plot_index = plot_count
        plot = _read_plot(reader)
        width = _validate_coordinates(reader, plot, plot_count, width)
        plot_count += 1
        yield plot

    if width is not None and plot_count % width != 0:
        reader.plot_index = plot_count - 1
        reader.fail(
            f"final row is incomplete: decoded {plot_count % width} of {width} plots",
            offset=len(plot_array_bytes),
        )


def decode_cv_plot_array_bytes(plot_array_bytes: bytes) -> Iterator[CvPlot]:
    """Return a lazy iterator over a complete serialized CvPlot array.

    The input must start with plot ``(0, 0)`` and end immediately after the
    final plot's archaeology record. Parsing errors can be raised while the
    returned iterator is consumed.
    """

    if not plot_array_bytes:
        raise CvPlotDecodeError("the CvPlot array is empty", offset=0, plot_index=0)
    return _iterate_cv_plot_array(plot_array_bytes)


def iterate_cv_plots_from_payload(
    payload: bytes, *, byte_offset: int, width: int, height: int
) -> Iterator[CvPlot]:
    """Yield a known-size CvPlot array from a decompressed save payload."""
    reader = _Reader(payload)
    reader.offset = byte_offset
    plot_count = width * height

    for plot_index in range(plot_count):
        reader.plot_index = plot_index
        plot = _read_plot(reader)
        _ = _validate_coordinates(reader, plot, plot_index, width)
        yield plot
