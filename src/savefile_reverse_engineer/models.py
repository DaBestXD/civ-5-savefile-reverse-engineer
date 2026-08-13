"""Semantic, immutable result types for the public save API."""

from dataclasses import dataclass
from enum import IntEnum
from typing import override


class GameMode(IntEnum):
    """Game mode reported by the save summary."""

    SINGLE_PLAYER = 0
    MULTIPLAYER = 1
    HOTSEAT = 2


class SlotClaim(IntEnum):
    """Reservation state for a player slot."""

    UNASSIGNED = 0
    RESERVED = 1
    ASSIGNED = 2


class SlotStatus(IntEnum):
    """Occupancy state for a player slot."""

    OPEN = 0
    COMPUTER = 1
    CLOSED = 2
    TAKEN = 3
    OBSERVER = 4


class PlayerType(IntEnum):
    """Broad category of a participating player."""

    PLAYER = 0
    COMPUTER = 1
    CITY_STATE = 2
    BARBARIAN = 3


class ProductionOrderType(IntEnum):
    """Kind of item in a city's production queue."""

    TRAIN_UNIT = 0
    CONSTRUCT_BUILDING = 1
    CREATE_PROJECT = 2
    PREPARE_SPECIALIST = 3
    MAINTAIN_PROCESS = 4


class PlotType(IntEnum):
    """A plot's broad map type."""

    NONE = -1
    MOUNTAIN = 0
    HILLS = 1
    LAND = 2
    OCEAN = 3


class TerrainType(IntEnum):
    """A plot's terrain type."""

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
    """A route built on a plot or available to a team."""

    NONE = -1
    ROAD = 0
    RAILROAD = 1


class FlowDirection(IntEnum):
    """A river-flow direction."""

    NONE = -1
    NORTH = 0
    NORTHEAST = 1
    SOUTHEAST = 2
    SOUTH = 3
    SOUTHWEST = 4
    NORTHWEST = 5


@dataclass(frozen=True, slots=True)
class EnabledContent:
    """One enabled DLC or mod entry."""

    guid: str
    value: int
    name: str


@dataclass(frozen=True, slots=True)
class SaveSummary:
    """Common metadata available without decoding the game payload."""

    game_version: str
    build: str
    turn: int
    game_mode: GameMode
    active_civilization_key: str
    difficulty_key: str
    starting_era_key: str
    current_era_key: str
    game_speed_key: str
    world_size_key: str
    map_script: str
    enabled_dlc: tuple[EnabledContent, ...]
    enabled_mods: tuple[EnabledContent, ...]
    player_color_key: str


@dataclass(frozen=True, slots=True)
class GameOption:
    """One named game or map option."""

    key: str
    value: int


@dataclass(frozen=True, slots=True)
class WorldSettings:
    """Common settings for the selected world size."""

    world_size_key: str
    grid_width: int
    grid_height: int
    default_player_count: int
    default_minor_civilization_count: int
    natural_wonder_count: int
    maximum_active_religions: int
    research_percent: int
    city_unhappiness_percent: int
    city_policy_cost_modifier: int
    city_technology_cost_modifier: int


@dataclass(frozen=True, slots=True)
class GameSettings:
    """Common, non-sensitive settings for the saved game."""

    game_name: str
    active_player_index: int
    game_started: bool
    private_game: bool
    internet_game: bool
    earth_map: bool
    maximum_turns: int
    target_score: int
    minor_civilization_count: int
    quick_combat: bool
    quick_start: bool
    random_world_size: bool
    random_map_script: bool
    map_random_seed: int
    map_script: str
    climate_key: str
    sea_level_key: str
    turn_timer_key: str
    world: WorldSettings
    game_options: tuple[GameOption, ...]
    map_options: tuple[GameOption, ...]


@dataclass(frozen=True, slots=True)
class PlayerSlot:
    """Semantic setup information for one saved player slot."""

    player_index: int
    display_name: str | None
    steam_id: str | None
    status: SlotStatus
    claim: SlotClaim
    team_index: int
    handicap_index: int
    civilization_key: str
    leader_key: str


@dataclass(frozen=True, slots=True)
class GameType:
    """A saved database hash and its known type key."""

    hash_value: int
    key: str | None

    @override
    def __str__(self) -> str:
        if self.hash_value == 0:
            return "No resource"
        return "Unknown" if self.key is None else self.key


@dataclass(frozen=True, slots=True)
class ObjectReference:
    """A player index and object ID saved as a Civ V IDInfo value."""

    owner_player_index: int
    object_id: int


@dataclass(frozen=True, slots=True)
class PlotFlags:
    """Confirmed Boolean state stored for a plot."""

    starting_plot: bool
    hills: bool
    northeast_of_river: bool
    west_of_river: bool
    northwest_of_river: bool
    potential_city_work: bool
    improvement_pillaged: bool
    route_pillaged: bool
    forced_fresh_water: bool


@dataclass(frozen=True, slots=True)
class PlotYields:
    """The seven saved plot yields."""

    food: int
    production: int
    gold: int
    science: int
    culture: int
    faith: int
    golden_age_points: int


@dataclass(frozen=True, slots=True)
class CityBuildingState:
    """Semantic state for one non-placeholder building type."""

    building_type: GameType
    production_x100: int
    production_turns: int
    original_owner_player_index: int
    original_year: int
    real_count: int
    free_count: int

    @override
    def __str__(self) -> str:
        return f"{self.building_type!s}({self.production_turns=}, {self.original_owner_player_index=}, {self.original_year=})"


@dataclass(frozen=True, slots=True)
class CityYieldValues:
    """One seven-value city yield vector."""

    food: int
    production: int
    gold: int
    science: int
    culture: int
    faith: int
    golden_age_points: int


@dataclass(frozen=True, slots=True)
class CityYieldVectors:
    """Named city yield vectors saved by Lekmod v34.11."""

    sea_plot_yield: CityYieldValues
    river_plot_yield: CityYieldValues
    lake_plot_yield: CityYieldValues
    sea_resource_yield: CityYieldValues
    base_yield_rate_from_terrain: CityYieldValues
    base_yield_rate_from_buildings: CityYieldValues
    base_yield_rate_from_specialists: CityYieldValues
    base_yield_rate_from_misc: CityYieldValues
    base_yield_rate_from_religion: CityYieldValues
    base_yield_rate_from_policies: CityYieldValues
    garrison_yield_bonus: CityYieldValues
    yield_per_population_x100: CityYieldValues
    yield_per_religion_x100: CityYieldValues
    yield_rate_modifier: CityYieldValues
    power_yield_rate_modifier: CityYieldValues
    resource_yield_rate_modifier: CityYieldValues
    extra_specialist_yield: CityYieldValues
    production_to_yield_modifier: CityYieldValues


@dataclass(frozen=True, slots=True)
class CitySpecialistState:
    """One specialist type's current state in a city."""

    specialist_type: GameType
    assigned_count: int
    great_person_progress_x100: int
    building_great_people_rate_change: int


@dataclass(frozen=True, slots=True)
class CityBuildingSpecialistState:
    """Current specialist assignments in one city building."""

    building_type: GameType
    assigned_count: int
    forced_count: int


@dataclass(frozen=True, slots=True)
class CityCitizenState:
    """Authoritative citizen and specialist state for one city."""

    automated: bool
    no_auto_assign_specialists: bool
    unassigned_citizens: int
    citizens_working_plots: int
    forced_working_plots: int
    focus_type_index: int
    avoid_growth: bool
    working_plot_flags: tuple[bool, ...]
    forced_working_plot_flags: tuple[bool, ...]
    default_specialists: int
    forced_default_specialists: int
    specialists: tuple[CitySpecialistState, ...]
    building_specialists: tuple[CityBuildingSpecialistState, ...]


@dataclass(frozen=True, slots=True)
class ProductionOrder:
    """One item in a city's production queue, in queue order."""

    order_type: ProductionOrderType
    item_type: GameType
    production_x100: int | None
    production_inactive_turns: int | None
    secondary_data: int
    save: bool
    rush: bool

    @override
    def __str__(self) -> str:
        return f"{self.order_type.name}({self.item_type!s}, {self.production_x100=}, {self.production_inactive_turns=}, {self.secondary_data=}, {self.save=}, {self.rush=})"


@dataclass(frozen=True, slots=True)
class CityBuildingStats:
    """City-wide values stored with the building inventory."""

    production_modifier: int
    defense: int
    garrison_strength_bonus: int
    defense_per_citizen: int
    defense_modifier: int
    missionary_extra_spreads: int
    landmarks_tourism_percent: int
    great_works_tourism_modifier: int
    sold_building_this_turn: bool


@dataclass(frozen=True, slots=True)
class CvCity:
    """Confirmed semantic fields, including buildings present in one city."""

    owner_player_index: int
    city_id: int
    name_key: str
    x: int
    y: int
    rally_x: int
    rally_y: int
    founded_turn: int
    acquired_turn: int
    population: int
    highest_population: int
    great_people_created: int
    base_great_people_rate: int
    great_people_rate_modifier: int
    culture_stored_x100: int
    culture_level: int
    yield_vectors: CityYieldVectors
    citizens: CityCitizenState
    building_stats: CityBuildingStats
    buildings: tuple[CityBuildingState, ...]
    current_production: ProductionOrder | None
    production_queue: tuple[ProductionOrder, ...]


@dataclass(frozen=True, slots=True)
class CvUnit:
    """Confirmed semantic fields for one unit."""

    owner_player_index: int
    unit_id: int
    unit_hash: int
    unit_name: str | None
    x: int
    y: int


@dataclass(frozen=True, slots=True)
class PlayerPolicyBranch:
    """One policy branch and the saved policies owned within it."""

    branch_type: GameType
    unlocked: bool
    owned_policies: tuple[GameType, ...]


@dataclass(frozen=True, slots=True)
class PlayerPolicyInformation:
    """Confirmed policy information for one participating player."""

    owned_policies: tuple[GameType, ...]
    branches: tuple[PlayerPolicyBranch, ...]


@dataclass(frozen=True, slots=True)
class CvPlayer:
    """Confirmed semantic fields for one participating player."""

    player_index: int
    player_type: PlayerType
    display_name: str | None
    starting_x: int
    starting_y: int
    total_population: int
    total_land: int
    total_land_scored: int
    culture_per_turn_for_free: int
    culture_per_turn_from_minor_civilizations: int
    culture_city_modifier: int
    culture_x100: int
    culture_ever_generated_x100: int
    culture_per_wonder: int
    culture_wonder_multiplier: int
    culture_per_technology_researched: int
    faith: int
    faith_ever_generated: int
    happiness: int
    policy_information: PlayerPolicyInformation
    cities: tuple[CvCity, ...]
    units: tuple[CvUnit, ...]


@dataclass(frozen=True, slots=True)
class CvPlot:
    """Common confirmed game state for one map plot."""

    x: int
    y: int
    area_index: int
    owner_player_index: int
    ownership_duration: int
    plot_type: PlotType
    terrain: TerrainType
    feature: GameType
    resource: GameType
    resource_quantity: int
    improvement: GameType
    improvement_pillaged: bool
    route: RouteType
    route_pillaged: bool
    flags: PlotFlags
    plot_city: ObjectReference
    working_city: ObjectReference
    purchase_city: ObjectReference
    yields: PlotYields
    unit_references: tuple[ObjectReference, ...]
    continent_index: int


@dataclass(frozen=True, slots=True)
class TeamTechnology:
    """State for one technology known to a participating team."""

    technology: GameType
    unlocked: bool
    obtained_by_human: bool
    obtained_for_league: bool
    cannot_trade: bool
    research_progress: int
    acquisition_count: int

    @override
    def __str__(self) -> str:
        return f"{self.technology!s}({self.unlocked=}, {self.research_progress=})"


@dataclass(frozen=True, slots=True)
class CvTeam:
    """Common confirmed game state for one participating team."""

    team_index: int
    member_count: int
    alive_member_count: int
    ever_alive_member_count: int
    city_count: int
    total_population: int
    total_land: int
    victory_points: int
    natural_wonders_discovered: int
    best_possible_route: RouteType
    current_era_index: int
    has_met: tuple[bool, ...]
    at_war: tuple[bool, ...]
    has_embassy: tuple[bool, ...]
    has_open_borders: tuple[bool, ...]
    technologies: tuple[TeamTechnology, ...]


__all__ = (
    "CityBuildingSpecialistState",
    "CityBuildingState",
    "CityBuildingStats",
    "CityCitizenState",
    "CitySpecialistState",
    "CityYieldValues",
    "CityYieldVectors",
    "CvCity",
    "CvPlayer",
    "CvPlot",
    "CvTeam",
    "CvUnit",
    "EnabledContent",
    "FlowDirection",
    "GameMode",
    "GameOption",
    "GameSettings",
    "GameType",
    "ObjectReference",
    "PlayerSlot",
    "PlotFlags",
    "PlotType",
    "PlotYields",
    "RouteType",
    "SaveSummary",
    "SlotClaim",
    "SlotStatus",
    "TeamTechnology",
    "TerrainType",
    "WorldSettings",
)
