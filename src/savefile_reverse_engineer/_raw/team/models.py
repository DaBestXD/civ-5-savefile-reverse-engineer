"""Private raw records for the Lekmod v34.11 CvTeam decoder."""

from dataclasses import dataclass

from .._shared.types import HashedType, RouteType


@dataclass(slots=True)
class HashedValue[ValueT]:
    """One saved database hash and its optional associated value."""

    type: HashedType
    value: ValueT | None


@dataclass(slots=True)
class TeamFlags:
    """The eight one-byte flags serialized in a CvTeam record."""

    map_centering: bool
    has_broken_peace_treaty: bool
    home_of_united_nations: bool
    has_technology_for_world_congress: bool
    broken_military_promise: bool
    broken_expansion_promise: bool
    broken_border_promise: bool
    broken_city_state_promise: bool


@dataclass(slots=True)
class TeamTechnology:
    """One technology slot in a serialized CvTeamTechs record."""

    technology: HashedType
    has_technology: bool
    obtained_by_human: bool
    obtained_for_league: bool
    cannot_trade: bool
    research_progress: int
    acquisition_count: int


@dataclass(slots=True)
class TeamYieldChanges:
    """The seven signed yield changes saved for one improvement."""

    food: int
    production: int
    gold: int
    science: int
    culture: int
    faith: int
    golden_age_points: int


@dataclass(slots=True)
class ProjectArt:
    """Saved project art choices for one project type."""

    project: HashedType
    art_types: tuple[int, ...]


@dataclass(slots=True)
class CvTeam:
    """All confirmed fields in a Lekmod v34.11 CvTeam version 1 record."""

    team_index: int
    byte_offset: int
    byte_length: int
    version: int
    member_count: int
    alive_member_count: int
    ever_alive_member_count: int
    city_count: int
    total_population: int
    total_land: int
    nuclear_interception_modifier: int
    extra_water_visibility_count: int
    map_trading_count: int
    technology_trading_count: int
    gold_trading_count: int
    embassy_trading_count: int
    open_border_trading_count: int
    defensive_pact_trading_count: int
    research_agreement_trading_count: int
    trade_agreement_trading_count: int
    permanent_alliance_trading_count: int
    bridge_building_count: int
    water_working_count: int
    river_trading_count: int
    border_obstacle_count: int
    victory_points: int
    extra_embarked_movement: int
    extra_embarked_sight: int
    can_embark_count: int
    defensive_embark_count: int
    all_water_passage_count: int
    natural_wonders_discovered: int
    best_possible_route: RouteType
    minor_civilizations_attacked: int
    flags: TeamFlags
    team_id: int
    current_era: int
    liberated_by_team: int
    killed_by_team: int
    technology_sharing_counts: tuple[int, ...]
    turns_at_war: tuple[int, ...]
    turns_locked_into_war: tuple[int, ...]
    extra_domain_movement: tuple[int, ...]
    vote_source_eligibility_counts: tuple[HashedValue[int], ...]
    turns_peace_made: tuple[int, ...]
    ignore_warning_counts: tuple[int, ...]
    has_met: tuple[bool, ...]
    has_found_territory: tuple[bool, ...]
    at_war: tuple[bool, ...]
    permanent_war_or_peace: tuple[bool, ...]
    has_embassy: tuple[bool, ...]
    has_open_borders: tuple[bool, ...]
    has_defensive_pact: tuple[bool, ...]
    has_research_agreement: tuple[bool, ...]
    has_trade_agreement: tuple[bool, ...]
    force_peace: tuple[bool, ...]
    can_launch_victories: tuple[HashedValue[bool], ...]
    victories_achieved: tuple[HashedValue[bool], ...]
    small_awards_achieved: tuple[HashedValue[bool], ...]
    route_changes: tuple[HashedValue[int], ...]
    build_time_changes: tuple[HashedValue[int], ...]
    project_counts: tuple[HashedValue[int], ...]
    project_default_art_types: tuple[HashedValue[int], ...]
    project_art_types: tuple[ProjectArt, ...]
    projects_being_constructed: tuple[HashedValue[int], ...]
    unit_class_counts: tuple[HashedValue[int], ...]
    building_class_counts: tuple[HashedValue[int], ...]
    obsolete_building_counts: tuple[HashedValue[int], ...]
    terrain_trade_counts: tuple[HashedValue[int], ...]
    victory_countdowns: tuple[HashedValue[int], ...]
    turns_teams_met: tuple[int, ...]
    technology_version: int
    last_technology_index: int
    last_technology: HashedType | None
    technologies: tuple[TeamTechnology, ...]
    improvement_yield_changes: tuple[HashedValue[TeamYieldChanges], ...]
    no_fresh_water_improvement_yield_changes: tuple[HashedValue[TeamYieldChanges], ...]
    fresh_water_improvement_yield_changes: tuple[HashedValue[TeamYieldChanges], ...]
    revealed_resources: tuple[HashedType, ...]


__all__: tuple[str, ...] = ()
