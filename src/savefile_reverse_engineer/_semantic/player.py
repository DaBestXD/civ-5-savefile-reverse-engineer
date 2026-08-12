"""Convert private raw player, city, and unit data to public models."""

from .._raw._catalogue.policies import POLICY_BRANCH_BY_POLICY_HASH
from .._raw.player.city_models import CityBuildingState as RawCityBuildingState
from .._raw.player.city_models import CityYieldValues as RawCityYieldValues
from .._raw.player.city_models import CityYieldVectors as RawCityYieldVectors
from .._raw.player.city_models import CvCity as RawCvCity
from .._raw.player.city_models import ProductionOrder as RawProductionOrder
from .._raw.player.models import CvPlayer as RawCvPlayer
from .._raw.player.unit_models import CvUnit as RawCvUnit
from ..models import (
    CityBuildingState,
    CityBuildingStats,
    CityYieldValues,
    CityYieldVectors,
    CvCity,
    CvPlayer,
    CvUnit,
    GameType,
    PlayerPolicyBranch,
    PlayerPolicyInformation,
    PlayerSlot,
    PlayerType,
    ProductionOrder,
    ProductionOrderType,
    SlotStatus,
)
from ._shared import game_type

_MINOR_CIVILIZATION_KEY = "CIVILIZATION_MINOR"
_BARBARIAN_CIVILIZATION_KEY = "CIVILIZATION_BARBARIAN"


def _player_display_name(player: RawCvPlayer, slot: PlayerSlot) -> str | None:
    if slot.display_name is not None:
        return slot.display_name
    if slot.status is not SlotStatus.COMPUTER:
        return None
    if slot.civilization_key != _MINOR_CIVILIZATION_KEY:
        return slot.leader_key
    if not player.cities.entries:
        return None
    return player.cities.entries[0].name_key


def _player_type(slot: PlayerSlot) -> PlayerType:
    if slot.civilization_key == _MINOR_CIVILIZATION_KEY:
        return PlayerType.CITY_STATE
    if slot.civilization_key == _BARBARIAN_CIVILIZATION_KEY:
        return PlayerType.BARBARIAN
    if slot.status is SlotStatus.TAKEN:
        return PlayerType.PLAYER
    return PlayerType.COMPUTER


def _required(value: int | None, field: str) -> int:
    if value is None:
        raise ValueError(f"non-placeholder building has no {field}")
    return value


def _building_state(
    state: RawCityBuildingState,
) -> CityBuildingState | None:
    if state.building.hash_value == 0:
        return None
    real_count = _required(state.real_count, "real count")
    free_count = _required(state.free_count, "free count")
    if real_count <= 0 and free_count <= 0:
        return None
    return CityBuildingState(
        building_type=game_type(state.building),
        production_x100=_required(state.production_times_100, "production"),
        production_turns=_required(state.production_turns, "production turns"),
        original_owner_player_index=_required(state.original_owner, "original owner"),
        original_year=_required(state.original_year, "original year"),
        real_count=real_count,
        free_count=free_count,
    )


def _city_yield_values(values: RawCityYieldValues) -> CityYieldValues:
    return CityYieldValues(
        food=values.food,
        production=values.production,
        gold=values.gold,
        science=values.science,
        culture=values.culture,
        faith=values.faith,
        golden_age_points=values.golden_age_points,
    )


def _city_yield_vectors(vectors: RawCityYieldVectors) -> CityYieldVectors:
    return CityYieldVectors(
        sea_plot_yield=_city_yield_values(vectors.sea_plot_yield),
        river_plot_yield=_city_yield_values(vectors.river_plot_yield),
        lake_plot_yield=_city_yield_values(vectors.lake_plot_yield),
        sea_resource_yield=_city_yield_values(vectors.sea_resource_yield),
        base_yield_rate_from_terrain=_city_yield_values(
            vectors.base_yield_rate_from_terrain
        ),
        base_yield_rate_from_buildings=_city_yield_values(
            vectors.base_yield_rate_from_buildings
        ),
        base_yield_rate_from_specialists=_city_yield_values(
            vectors.base_yield_rate_from_specialists
        ),
        base_yield_rate_from_misc=_city_yield_values(vectors.base_yield_rate_from_misc),
        base_yield_rate_from_religion=_city_yield_values(
            vectors.base_yield_rate_from_religion
        ),
        base_yield_rate_from_policies=_city_yield_values(
            vectors.base_yield_rate_from_policies
        ),
        garrison_yield_bonus=_city_yield_values(vectors.garrison_yield_bonus),
        yield_per_population_x100=_city_yield_values(vectors.yield_per_population_x100),
        yield_per_religion_x100=_city_yield_values(vectors.yield_per_religion_x100),
        yield_rate_modifier=_city_yield_values(vectors.yield_rate_modifier),
        power_yield_rate_modifier=_city_yield_values(vectors.power_yield_rate_modifier),
        resource_yield_rate_modifier=_city_yield_values(
            vectors.resource_yield_rate_modifier
        ),
        extra_specialist_yield=_city_yield_values(vectors.extra_specialist_yield),
        production_to_yield_modifier=_city_yield_values(
            vectors.production_to_yield_modifier
        ),
    )


def _building_production(
    city: RawCvCity,
    order: RawProductionOrder,
) -> tuple[int | None, int | None]:
    if order.order_type.value != ProductionOrderType.CONSTRUCT_BUILDING.value:
        return None, None
    current_hash = order.item.hash_value
    for state in city.buildings.entries:
        if state.building.hash_value == current_hash:
            return (
                _required(state.production_times_100, "production"),
                _required(state.production_turns, "production inactive turns"),
            )
    raise ValueError(
        f"queued building hash 0x{current_hash:08X} is absent from the inventory"
    )


def _production_order(city: RawCvCity, order: RawProductionOrder) -> ProductionOrder:
    production_x100, production_inactive_turns = _building_production(city, order)
    return ProductionOrder(
        order_type=ProductionOrderType(order.order_type.value),
        item_type=game_type(order.item),
        production_x100=production_x100,
        production_inactive_turns=production_inactive_turns,
        secondary_data=order.secondary_data,
        save=order.save,
        rush=order.rush,
    )


def _city(city: RawCvCity, owner_player_index: int) -> CvCity:
    inventory = city.buildings
    converted_buildings: list[CityBuildingState] = []
    for state in inventory.entries:
        converted = _building_state(state)
        if converted is not None:
            converted_buildings.append(converted)
    production_queue = tuple(
        _production_order(city, order) for order in city.production_queue
    )
    return CvCity(
        owner_player_index=owner_player_index,
        city_id=city.city_id,
        name_key=city.name_key,
        x=city.x,
        y=city.y,
        rally_x=city.rally_x,
        rally_y=city.rally_y,
        founded_turn=city.game_turn_founded,
        acquired_turn=city.game_turn_acquired,
        population=city.population,
        highest_population=city.highest_population,
        great_people_created=city.great_people_created,
        base_great_people_rate=city.base_great_people_rate,
        great_people_rate_modifier=city.great_people_rate_modifier,
        culture_stored_x100=city.culture_stored_times_100,
        culture_level=city.culture_level,
        yield_vectors=_city_yield_vectors(city.yield_vectors),
        building_stats=CityBuildingStats(
            production_modifier=inventory.production_modifier,
            defense=inventory.defense,
            garrison_strength_bonus=inventory.garrison_strength_bonus,
            defense_per_citizen=inventory.defense_per_citizen,
            defense_modifier=inventory.defense_modifier,
            missionary_extra_spreads=inventory.missionary_extra_spreads,
            landmarks_tourism_percent=inventory.landmarks_tourism_percent,
            great_works_tourism_modifier=inventory.great_works_tourism_modifier,
            sold_building_this_turn=inventory.sold_building_this_turn,
        ),
        buildings=tuple(converted_buildings),
        current_production=(production_queue[0] if production_queue else None),
        production_queue=production_queue,
    )


def _unit(unit: RawCvUnit, owner_player_index: int) -> CvUnit:
    return CvUnit(
        owner_player_index=owner_player_index,
        unit_id=unit.unit_id,
        unit_hash=unit.unit_hash,
        unit_name=unit.unit_name,
        x=unit.x,
        y=unit.y,
    )


def _policy_information(player: RawCvPlayer) -> PlayerPolicyInformation:
    raw_information = player.policy_information
    owned_policies: list[GameType] = []
    owned_by_branch: dict[int, list[GameType]] = {}
    for policy in raw_information.policy_slots:
        if policy.owned is not True:
            continue
        policy_type = game_type(policy.policy_type)
        owned_policies.append(policy_type)
        branch_hash = POLICY_BRANCH_BY_POLICY_HASH.get(policy.policy_type.hash_value)
        if branch_hash is not None:
            owned_by_branch.setdefault(branch_hash, []).append(policy_type)
    return PlayerPolicyInformation(
        owned_policies=tuple(owned_policies),
        branches=tuple(
            PlayerPolicyBranch(
                branch_type=game_type(branch.branch_type),
                unlocked=branch.unlocked,
                owned_policies=tuple(
                    owned_by_branch.get(branch.branch_type.hash_value, ())
                ),
            )
            for branch in raw_information.branches
        ),
    )


def make_player(
    player: RawCvPlayer,
    *,
    slot: PlayerSlot,
) -> CvPlayer:
    """Create a semantic player and its nested cities and units."""
    owner = player.player_index
    return CvPlayer(
        player_index=owner,
        player_type=_player_type(slot),
        display_name=_player_display_name(player, slot),
        starting_x=player.starting_x,
        starting_y=player.starting_y,
        total_population=player.total_population,
        total_land=player.total_land,
        total_land_scored=player.total_land_scored,
        culture_per_turn_for_free=player.culture_per_turn_for_free,
        culture_per_turn_from_minor_civilizations=(
            player.culture_per_turn_from_minor_civs
        ),
        culture_city_modifier=player.culture_city_modifier,
        culture_x100=player.culture_times_100,
        culture_ever_generated_x100=player.culture_ever_generated_times_100,
        culture_per_wonder=player.culture_per_wonder,
        culture_wonder_multiplier=player.culture_wonder_multiplier,
        culture_per_technology_researched=(player.culture_per_technology_researched),
        faith=player.faith,
        faith_ever_generated=player.faith_ever_generated,
        happiness=player.happiness,
        policy_information=_policy_information(player),
        cities=tuple(_city(city, owner) for city in player.cities.entries),
        units=tuple(_unit(unit, owner) for unit in player.units.entries),
    )

__all__ = ("make_player",)
