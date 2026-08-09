"""Public result types for the Lekmod v34.11 CvPlayer decoder."""

from dataclasses import dataclass

from .cv_city_types import CvCity
from .cv_unit_types import CvUnit


@dataclass(slots=True)
class SerializedFreeList[EntryT]:
    """Serialized metadata and live entries from an FFreeListTrashArray."""

    byte_offset: int
    byte_length: int
    slot_count: int
    last_index: int
    free_list_head: int
    free_count: int
    current_id: int
    next_free_indices: tuple[int, ...]
    entries: tuple[EntryT, ...]


@dataclass(slots=True)
class CvPlayer:
    """Confirmed fields in one Lekmod v34.11 CvPlayer version 16 record."""

    player_index: int
    byte_offset: int
    byte_length: int
    version: int
    starting_x: int
    starting_y: int
    total_population: int
    total_land: int
    total_land_scored: int
    culture_per_turn_for_free: int
    culture_per_turn_from_minor_civs: int
    culture_city_modifier: int
    culture_times_100: int
    culture_ever_generated_times_100: int
    culture_per_wonder: int
    culture_wonder_multiplier: int
    culture_per_technology_researched: int
    faith: int
    faith_ever_generated: int
    happiness: int
    cities: SerializedFreeList[CvCity]
    units: SerializedFreeList[CvUnit]


__all__: tuple[str, ...] = ()
