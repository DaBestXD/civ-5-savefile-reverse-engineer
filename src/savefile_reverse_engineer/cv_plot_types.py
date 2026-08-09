"""Public result and enum types for the CvPlot decoder."""

from dataclasses import dataclass
from enum import IntEnum
from typing import override


class PlotType(IntEnum):
    """Serialized CvPlot plot types."""

    NONE = -1
    MOUNTAIN = 0
    HILLS = 1
    LAND = 2
    OCEAN = 3


class TerrainType(IntEnum):
    """Serialized CvPlot terrain types."""

    NONE = -1
    GRASSLAND = 0
    PLAINS = 1
    DESERT = 2
    TUNDRA = 3
    SNOW = 4
    COAST = 5
    OCEAN = 6
    MOUNTAIN = 7
    HILL = 8


class RouteType(IntEnum):
    """Serialized CvPlot route types."""

    NONE = -1
    ROAD = 0
    RAILROAD = 1


class FlowDirection(IntEnum):
    """Serialized CvPlot river-flow directions."""

    NONE = -1
    NORTH = 0
    NORTHEAST = 1
    SOUTHEAST = 2
    SOUTH = 3
    SOUTHWEST = 4
    NORTHWEST = 5


@dataclass(slots=True)
class HashedType:
    """A serialized database hash and its known Lekmod v34.11 type name."""

    hash_value: int
    name: str | None

    @override
    def __str__(self) -> str:
        return self.name if self.name else "Unknown"


@dataclass(slots=True)
class ObjectReference:
    """An owner and object-ID pair serialized as Civ V IDInfo."""

    owner: int
    object_id: int


@dataclass(slots=True)
class PlotFlags:
    """The fourteen one-byte flags serialized by Lekmod v34.11."""

    starting_plot: bool
    hills: bool
    northeast_of_river: bool
    west_of_river: bool
    northwest_of_river: bool
    potential_city_work: bool
    improvement_pillaged: bool
    route_pillaged: bool
    route_was_previously_pillaged: bool
    barbarian_camp_not_converting: bool
    rough_feature: bool
    resource_linked_city_active: bool
    improved_by_major_civilization_gift: bool
    forced_fresh_water: bool


@dataclass(slots=True)
class PlotYields:
    """The seven yields serialized by Lekmod v34.11."""

    food: int
    production: int
    gold: int
    science: int
    culture: int
    faith: int
    golden_age_points: int


@dataclass(slots=True)
class BuildProgress:
    """One interleaved build-progress entry."""

    build: HashedType
    progress: int | None


@dataclass(slots=True)
class ArchaeologyData:
    """The final CvArchaeologyData record in a plot."""

    version: int
    artifact_type: int
    era: int
    player_1: int
    player_2: int
    work: int | None


@dataclass(slots=True)
class CvPlot:
    """All confirmed fields in a Lekmod v34.11 CvPlot version 7 record."""

    byte_offset: int
    byte_length: int
    version: int
    x: int
    y: int
    area: int
    feature_variety: int
    ownership_duration: int
    improvement_duration: int
    upgrade_progress: int
    culture: int
    major_civilizations_revealed: int
    city_radius_count: int
    recon_count: int
    river_crossing_count: int
    resource_quantity: int
    builder_scratch_player: int
    builder_scratch_turn: int
    builder_scratch_value: int
    builder_scratch_route: RouteType
    landmass: int
    trade_route_bit_flags: int
    flags: PlotFlags
    owner: int
    plot_type: PlotType
    terrain: TerrainType
    feature: HashedType
    resource: HashedType
    improvement: HashedType
    under_construction_improvement: HashedType
    player_that_built_improvement: int
    player_responsible_for_improvement: int
    player_responsible_for_route: int
    player_that_cleared_camp: int
    route: RouteType
    world_anchor: int
    world_anchor_data: int
    east_river_flow: FlowDirection
    southeast_river_flow: FlowDirection
    southwest_river_flow: FlowDirection
    plot_city: ObjectReference
    working_city: ObjectReference
    working_city_override: ObjectReference
    resource_linked_city: ObjectReference
    purchase_city: ObjectReference
    yields: PlotYields
    found_values: tuple[int, ...]
    player_city_radius_counts: tuple[int, ...]
    visibility_counts: tuple[int, ...]
    revealed_owners: tuple[int, ...]
    river_crossing: int
    revealed_bits: tuple[int, ...]
    resource_force_reveals: tuple[bool, ...]
    revealed_improvements: tuple[HashedType, ...]
    revealed_routes: tuple[RouteType, ...]
    no_settling: tuple[bool, ...]
    has_script_data: bool
    outer_build_count: int
    inner_build_count: int | None
    build_progress: tuple[BuildProgress, ...]
    invisible_visibility: tuple[int, ...]
    unit_references: tuple[ObjectReference, ...]
    continent: int
    archaeology: ArchaeologyData


__all__: tuple[str, ...] = ()
