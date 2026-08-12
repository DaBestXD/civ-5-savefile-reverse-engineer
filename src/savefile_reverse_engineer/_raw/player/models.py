"""Private raw records for the Lekmod v34.11 CvPlayer decoder."""

from dataclasses import dataclass

from .._shared.types import HashedType
from .city_models import CvCity
from .unit_models import CvUnit


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
class CvPlayerPolicy:
    """One serialized policy slot and its saved ownership state."""

    policy_type: HashedType
    owned: bool | None


@dataclass(slots=True)
class CvPlayerPolicyBranch:
    """One serialized policy branch and its confirmed unlocked state."""

    branch_type: HashedType
    unlocked: bool


@dataclass(slots=True)
class CvPlayerPolicyInformation:
    """Confirmed fields from one serialized CvPlayerPolicies object."""

    byte_offset: int
    version: int
    policy_slots: tuple[CvPlayerPolicy, ...]
    branches: tuple[CvPlayerPolicyBranch, ...]


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
    policy_information: CvPlayerPolicyInformation
    cities: SerializedFreeList[CvCity]
    units: SerializedFreeList[CvUnit]


__all__: tuple[str, ...] = ()
