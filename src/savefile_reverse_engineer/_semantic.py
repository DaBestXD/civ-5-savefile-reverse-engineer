"""Convert exact serialization records into the semantic public models."""

from ._cv_policy_hashes import POLICY_BRANCH_BY_POLICY_HASH
from .civ5_header_types import Civ5SaveHeader as RawCiv5SaveHeader
from .cv_city_types import (
    CityBuildingState as RawCityBuildingState,
)
from .cv_city_types import (
    CvCity as RawCvCity,
)
from .cv_city_types import (
    ProductionOrder as RawProductionOrder,
)
from .cv_player_types import CvPlayer as RawCvPlayer
from .cv_plot_types import (
    CvPlot as RawCvPlot,
)
from .cv_plot_types import (
    HashedType as RawHashedType,
)
from .cv_plot_types import (
    ObjectReference as RawObjectReference,
)
from .cv_team_types import CvTeam as RawCvTeam
from .cv_unit_types import CvUnit as RawCvUnit
from .models import (
    CityBuildingState,
    CityBuildingStats,
    CvCity,
    CvPlayer,
    CvPlot,
    CvTeam,
    CvUnit,
    EnabledContent,
    GameMode,
    GameOption,
    GameSettings,
    GameType,
    ObjectReference,
    PlayerPolicyBranch,
    PlayerPolicyInformation,
    PlayerSlot,
    PlayerType,
    PlotFlags,
    PlotType,
    PlotYields,
    ProductionOrder,
    ProductionOrderType,
    RouteType,
    SaveSummary,
    SlotClaim,
    SlotStatus,
    TerrainType,
    WorldSettings,
)


def make_summary(header: RawCiv5SaveHeader) -> SaveSummary:
    """Create public summary data from the exact quick header."""
    quick = header.quick
    return SaveSummary(
        game_version=quick.game_version,
        build=quick.build,
        turn=quick.turn,
        game_mode=GameMode(quick.game_mode.value),
        active_civilization_key=quick.active_civilization,
        difficulty_key=quick.difficulty,
        starting_era_key=quick.starting_era,
        current_era_key=quick.current_era,
        game_speed_key=quick.game_speed,
        world_size_key=quick.world_size,
        map_script=quick.map_script,
        enabled_dlc=tuple(
            EnabledContent(guid=item.guid, value=item.value, name=item.name)
            for item in quick.enabled_dlc
        ),
        enabled_mods=tuple(
            EnabledContent(guid=item.guid, value=item.value, name=item.name)
            for item in quick.enabled_mods
        ),
        player_color_key=quick.player_color,
    )


def make_settings(header: RawCiv5SaveHeader) -> GameSettings:
    """Create the curated, non-sensitive settings view."""
    pregame = header.pregame
    world = pregame.world_info
    return GameSettings(
        game_name=pregame.game_name,
        active_player_index=pregame.active_player,
        game_started=pregame.game_started,
        private_game=pregame.private_game,
        internet_game=pregame.is_internet_game,
        earth_map=pregame.is_earth_map,
        maximum_turns=pregame.max_turns,
        target_score=pregame.target_score,
        minor_civilization_count=pregame.num_minor_civs,
        quick_combat=pregame.quick_combat,
        quick_start=pregame.quickstart,
        random_world_size=pregame.random_world_size,
        random_map_script=pregame.random_map_script,
        map_random_seed=pregame.map_random_seed,
        map_script=pregame.map_script_name,
        climate_key=pregame.climate_info.type,
        sea_level_key=pregame.sea_level_info.type,
        turn_timer_key=pregame.turn_timer.type,
        world=WorldSettings(
            world_size_key=world.type,
            grid_width=world.grid_width,
            grid_height=world.grid_height,
            default_player_count=world.default_players,
            default_minor_civilization_count=world.default_minor_civs,
            natural_wonder_count=world.num_natural_wonders,
            maximum_active_religions=world.max_active_religions,
            research_percent=world.research_percent,
            city_unhappiness_percent=world.num_cities_unhappiness_percent,
            city_policy_cost_modifier=world.num_cities_policy_cost_modifier,
            city_technology_cost_modifier=world.num_cities_tech_cost_modifier,
        ),
        game_options=tuple(
            GameOption(key=option.name, value=option.value)
            for option in pregame.game_options
        ),
        map_options=tuple(
            GameOption(key=option.name, value=option.value)
            for option in pregame.map_options
        ),
    )


def make_player_slots(
    header: RawCiv5SaveHeader,
) -> tuple[PlayerSlot, ...]:
    """Create semantic player-slot records."""
    return tuple(
        PlayerSlot(
            player_index=slot.index,
            display_name=slot.display_name,
            steam_id=slot.steam_id,
            status=SlotStatus(slot.status.value),
            claim=SlotClaim(slot.claim.value),
            team_index=slot.team,
            handicap_index=slot.handicap,
            civilization_key=slot.civilization_key,
            leader_key=slot.leader_key,
        )
        for slot in header.slot_hints.players
    )


def _game_type(value: RawHashedType) -> GameType:
    return GameType(hash_value=value.hash_value, key=value.name)


def _object_reference(value: RawObjectReference) -> ObjectReference:
    return ObjectReference(
        owner_player_index=value.owner,
        object_id=value.object_id,
    )


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
        building_type=_game_type(state.building),
        production_x100=_required(state.production_times_100, "production"),
        production_turns=_required(state.production_turns, "production turns"),
        original_owner_player_index=_required(state.original_owner, "original owner"),
        original_year=_required(state.original_year, "original year"),
        real_count=real_count,
        free_count=free_count,
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
        item_type=_game_type(order.item),
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
        policy_type = _game_type(policy.policy_type)
        owned_policies.append(policy_type)
        branch_hash = POLICY_BRANCH_BY_POLICY_HASH.get(policy.policy_type.hash_value)
        if branch_hash is not None:
            owned_by_branch.setdefault(branch_hash, []).append(policy_type)
    return PlayerPolicyInformation(
        owned_policies=tuple(owned_policies),
        branches=tuple(
            PlayerPolicyBranch(
                branch_type=_game_type(branch.branch_type),
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
    display_name: str | None,
    player_type: PlayerType,
) -> CvPlayer:
    """Create a semantic player and its nested cities and units."""
    owner = player.player_index
    return CvPlayer(
        player_index=owner,
        player_type=player_type,
        display_name=display_name,
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


def make_plot(plot: RawCvPlot) -> CvPlot:
    """Create the common semantic view of a plot."""
    flags = plot.flags
    return CvPlot(
        x=plot.x,
        y=plot.y,
        area_index=plot.area,
        owner_player_index=plot.owner,
        ownership_duration=plot.ownership_duration,
        plot_type=PlotType(plot.plot_type.value),
        terrain=TerrainType(plot.terrain.value),
        feature=_game_type(plot.feature),
        resource=_game_type(plot.resource),
        resource_quantity=plot.resource_quantity,
        improvement=_game_type(plot.improvement),
        improvement_pillaged=flags.improvement_pillaged,
        route=RouteType(plot.route.value),
        route_pillaged=flags.route_pillaged,
        flags=PlotFlags(
            starting_plot=flags.starting_plot,
            hills=flags.hills,
            northeast_of_river=flags.northeast_of_river,
            west_of_river=flags.west_of_river,
            northwest_of_river=flags.northwest_of_river,
            potential_city_work=flags.potential_city_work,
            improvement_pillaged=flags.improvement_pillaged,
            route_pillaged=flags.route_pillaged,
            forced_fresh_water=flags.forced_fresh_water,
        ),
        plot_city=_object_reference(plot.plot_city),
        working_city=_object_reference(plot.working_city),
        purchase_city=_object_reference(plot.purchase_city),
        yields=PlotYields(
            food=plot.yields.food,
            production=plot.yields.production,
            gold=plot.yields.gold,
            science=plot.yields.science,
            culture=plot.yields.culture,
            faith=plot.yields.faith,
            golden_age_points=plot.yields.golden_age_points,
        ),
        unit_references=tuple(
            _object_reference(reference) for reference in plot.unit_references
        ),
        continent_index=plot.continent,
    )


def make_team(team: RawCvTeam) -> CvTeam:
    """Create the common semantic view of a team."""
    return CvTeam(
        team_index=team.team_index,
        member_count=team.member_count,
        alive_member_count=team.alive_member_count,
        ever_alive_member_count=team.ever_alive_member_count,
        city_count=team.city_count,
        total_population=team.total_population,
        total_land=team.total_land,
        victory_points=team.victory_points,
        natural_wonders_discovered=team.natural_wonders_discovered,
        best_possible_route=RouteType(team.best_possible_route.value),
        current_era_index=team.current_era,
        has_met=team.has_met,
        at_war=team.at_war,
        has_embassy=team.has_embassy,
        has_open_borders=team.has_open_borders,
    )


__all__: tuple[str, ...] = ()
