"""Convert raw header data to public game and slot models."""

from .._raw.header.models import Civ5SaveHeader as RawCiv5SaveHeader
from ..models import (
    EnabledContent,
    GameMode,
    GameOption,
    GameSettings,
    PlayerSlot,
    SaveSummary,
    SlotClaim,
    SlotStatus,
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


def make_player_slots(header: RawCiv5SaveHeader) -> tuple[PlayerSlot, ...]:
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

__all__ = ("make_player_slots", "make_settings", "make_summary")
