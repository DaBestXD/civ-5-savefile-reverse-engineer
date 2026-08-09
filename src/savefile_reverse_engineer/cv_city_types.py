"""Public result types for nested Lekmod v34.11 CvCity records."""

from dataclasses import dataclass

from .cv_plot_types import HashedType


@dataclass(slots=True)
class CityBuildingState:
    """Serialized state for one building type in a city."""

    building: HashedType
    production_times_100: int | None
    production_turns: int | None
    original_owner: int | None
    original_year: int | None
    real_count: int | None
    free_count: int | None


@dataclass(slots=True)
class CvCityBuildings:
    """Confirmed header and inventory arrays from one CvCityBuildings object."""

    byte_offset: int
    inventory_byte_length: int
    version: int
    num_buildings: int
    production_modifier: int
    defense: int
    garrison_strength_bonus: int
    defense_per_citizen: int
    defense_modifier: int
    missionary_extra_spreads: int
    landmarks_tourism_percent: int
    great_works_tourism_modifier: int
    sold_building_this_turn: bool
    entries: tuple[CityBuildingState, ...]


@dataclass(slots=True)
class CvCity:
    """Confirmed fields from one CvCityAI free-list entry."""

    record_index: int
    slot_index: int
    byte_offset: int
    byte_length: int
    version: int
    city_id: int
    x: int
    y: int
    rally_x: int
    rally_y: int
    game_turn_founded: int
    game_turn_acquired: int
    population: int
    highest_population: int
    great_people_created: int
    base_great_people_rate: int
    great_people_rate_modifier: int
    culture_stored_times_100: int
    culture_level: int
    buildings: CvCityBuildings


__all__: tuple[str, ...] = ()
