"""Decode a complete Lekmod v34.11 CvTeam array from bytes."""

from collections.abc import Callable, Iterator
from functools import partial
from typing import NoReturn, override

from .._catalogue.teams import TEAM_HASH_NAMES
from .._shared.binary_reader import LittleEndianReader, enum_value, read_u32_count
from .._shared.types import HashedType, RouteType, resolve_hashed_type
from .models import (
    CvTeam,
    HashedValue,
    ProjectArt,
    TeamFlags,
    TeamTechnology,
    TeamYieldChanges,
)

_TEAM_VERSION = 1
_TEAM_COUNT = 64
_CIV_TEAM_COUNT = 63
_DOMAIN_COUNT = 5
_VOTE_SOURCE_COUNT = 2
_VICTORY_COUNT = 6
_SMALL_AWARD_COUNT = 0
_ROUTE_COUNT = 2
_BUILD_COUNT = 70
_PROJECT_COUNT = 6
_UNIT_CLASS_COUNT = 113
_BUILDING_CLASS_COUNT = 177
_BUILDING_COUNT = 268
_TERRAIN_COUNT = 9
_TECHNOLOGY_COUNT = 81
_IMPROVEMENT_COUNT = 46
_YIELD_COUNT = 7
_RESOURCE_COUNT = 57


class CvTeamDecodeError(ValueError):
    """A malformed or unsupported value in a serialized CvTeam array."""

    message: str
    offset: int
    team_index: int

    def __init__(self, message: str, *, offset: int, team_index: int) -> None:
        self.message = message
        self.offset = offset
        self.team_index = team_index
        super().__init__(f"team {team_index} at byte offset 0x{offset:X}: {message}")


class _Reader(LittleEndianReader):
    __slots__: tuple[str, ...] = ("team_index",)
    _bounds_error_suffix: str = "team-array bytes"

    team_index: int
    offset: int

    def __init__(self, data: bytes, byte_offset: int = 0) -> None:
        super().__init__(data)
        self.offset = byte_offset
        self.team_index = 0

    @override
    def fail(
        self,
        message: str,
        *,
        offset: int | None = None,
        field: str | None = None,
    ) -> NoReturn:
        del field
        raise CvTeamDecodeError(
            message,
            offset=self.offset if offset is None else offset,
            team_index=self.team_index,
        )


def _resolve_hash(hash_value: int) -> HashedType:
    return resolve_hashed_type(hash_value, TEAM_HASH_NAMES)


def _read_ints(reader: _Reader, count: int, field: str) -> tuple[int, ...]:
    return tuple(reader.i32(f"{field}[{index}]") for index in range(count))


def _read_bools(reader: _Reader, count: int, field: str) -> tuple[bool, ...]:
    return tuple(reader.read_bool(f"{field}[{index}]") for index in range(count))


def _read_hashed_values[ValueT](
    reader: _Reader,
    *,
    expected_count: int,
    read_value: Callable[[str], ValueT],
    field: str,
) -> tuple[HashedValue[ValueT], ...]:
    count = read_u32_count(reader, field, expected=expected_count)
    entries: list[HashedValue[ValueT]] = []
    for index in range(count):
        item_field = f"{field}[{index}]"
        hash_value = reader.u32(f"{item_field}.type")
        value = None if hash_value == 0 else read_value(f"{item_field}.value")
        entries.append(HashedValue(type=_resolve_hash(hash_value), value=value))
    return tuple(entries)


def _read_hashed_ints(
    reader: _Reader, *, expected_count: int, field: str
) -> tuple[HashedValue[int], ...]:
    return _read_hashed_values(
        reader,
        expected_count=expected_count,
        read_value=reader.i32,
        field=field,
    )


def _read_hashed_bools(
    reader: _Reader, *, expected_count: int, field: str
) -> tuple[HashedValue[bool], ...]:
    return _read_hashed_values(
        reader,
        expected_count=expected_count,
        read_value=reader.read_bool,
        field=field,
    )


def _read_flags(reader: _Reader) -> TeamFlags:
    return TeamFlags(
        map_centering=reader.read_bool("flags.map_centering"),
        has_broken_peace_treaty=reader.read_bool("flags.has_broken_peace_treaty"),
        home_of_united_nations=reader.read_bool("flags.home_of_united_nations"),
        has_technology_for_world_congress=reader.read_bool(
            "flags.has_technology_for_world_congress"
        ),
        broken_military_promise=reader.read_bool("flags.broken_military_promise"),
        broken_expansion_promise=reader.read_bool("flags.broken_expansion_promise"),
        broken_border_promise=reader.read_bool("flags.broken_border_promise"),
        broken_city_state_promise=reader.read_bool("flags.broken_city_state_promise"),
    )


def _read_route(reader: _Reader, field: str) -> RouteType:
    offset = reader.offset
    raw_value = reader.i32(field)
    return enum_value(
        reader,
        RouteType,
        raw_value,
        field=field,
        offset=offset,
        value_name=field,
    )


def _read_project_art(
    reader: _Reader, project_counts: tuple[HashedValue[int], ...]
) -> tuple[ProjectArt, ...]:
    count = read_u32_count(reader, "project_art_types", expected=_PROJECT_COUNT)
    counts_by_hash = {
        entry.type.hash_value: entry.value
        for entry in project_counts
        if entry.value is not None
    }
    entries: list[ProjectArt] = []
    for index in range(count):
        hash_offset = reader.offset
        hash_value = reader.u32(f"project_art_types[{index}].project")
        if hash_value == 0 or hash_value not in counts_by_hash:
            reader.fail(
                "project art hash does not match a saved project count",
                offset=hash_offset,
            )
        project_count = counts_by_hash[hash_value]
        if project_count < 0:
            reader.fail(
                f"project count is {project_count}, expected a nonnegative value",
                offset=hash_offset,
            )
        art_types = _read_ints(
            reader, project_count, f"project_art_types[{index}].art_types"
        )
        entries.append(
            ProjectArt(project=_resolve_hash(hash_value), art_types=art_types)
        )
    return tuple(entries)


def _read_technologies(
    reader: _Reader,
) -> tuple[int, int, HashedType | None, tuple[TeamTechnology, ...]]:
    version_offset = reader.offset
    version = reader.u32("technologies.version")
    if version != 1:
        reader.fail(
            f"unsupported CvTeamTechs version {version}; expected 1",
            offset=version_offset,
        )
    last_index = reader.i32("technologies.last_technology_index")
    count = read_u32_count(reader, "technologies", expected=_TECHNOLOGY_COUNT)
    hashes = tuple(
        reader.u32(f"technologies[{index}].technology") for index in range(count)
    )
    has_technology = _read_bools(reader, count, "technologies.has_technology")
    obtained_by_human = _read_bools(reader, count, "technologies.obtained_by_human")
    obtained_for_league = _read_bools(reader, count, "technologies.obtained_for_league")
    cannot_trade = _read_bools(reader, count, "technologies.cannot_trade")
    research_progress = _read_ints(reader, count, "technologies.research_progress")
    acquisition_counts = _read_ints(reader, count, "technologies.acquisition_count")
    technologies = tuple(
        TeamTechnology(
            technology=_resolve_hash(hashes[index]),
            has_technology=has_technology[index],
            obtained_by_human=obtained_by_human[index],
            obtained_for_league=obtained_for_league[index],
            cannot_trade=cannot_trade[index],
            research_progress=research_progress[index],
            acquisition_count=acquisition_counts[index],
        )
        for index in range(count)
    )
    if last_index == -1:
        last_technology = None
    elif 0 <= last_index < count:
        last_technology = technologies[last_index].technology
    else:
        reader.fail(
            f"last technology index {last_index} is outside {-1}..{count - 1}",
            offset=version_offset + 4,
        )
    return version, last_index, last_technology, technologies


def _read_yield_changes(reader: _Reader, field: str) -> TeamYieldChanges:
    values = _read_ints(reader, _YIELD_COUNT, field)
    return TeamYieldChanges(
        food=values[0],
        production=values[1],
        gold=values[2],
        science=values[3],
        culture=values[4],
        faith=values[5],
        golden_age_points=values[6],
    )


def _read_improvement_yield_array(
    reader: _Reader, field: str
) -> tuple[HashedValue[TeamYieldChanges], ...]:
    return _read_hashed_values(
        reader,
        expected_count=_IMPROVEMENT_COUNT,
        read_value=partial(_read_yield_changes, reader),
        field=field,
    )


def _read_revealed_resources(reader: _Reader) -> tuple[HashedType, ...]:
    count = read_u32_count(reader, "revealed_resources")
    reader.ensure_count_fits(
        count,
        item_size=4,
        reserved_bytes=0,
        field="revealed_resources.count",
    )
    if count > _RESOURCE_COUNT:
        reader.fail(
            f"revealed_resources.count is {count}, expected at most {_RESOURCE_COUNT}"
        )
    return tuple(
        _resolve_hash(reader.u32(f"revealed_resources[{index}]"))
        for index in range(count)
    )


def _read_team(reader: _Reader, team_index: int) -> CvTeam:
    reader.team_index = team_index
    start = reader.offset
    version = reader.u32("version")
    if version != _TEAM_VERSION:
        reader.fail(
            f"unsupported CvTeam version {version}; expected {_TEAM_VERSION}",
            offset=start,
        )

    member_count = reader.i32("member_count")
    alive_member_count = reader.i32("alive_member_count")
    ever_alive_member_count = reader.i32("ever_alive_member_count")
    city_count = reader.i32("city_count")
    total_population = reader.i32("total_population")
    total_land = reader.i32("total_land")
    nuclear_interception_modifier = reader.i32("nuclear_interception_modifier")
    extra_water_visibility_count = reader.i32("extra_water_visibility_count")
    map_trading_count = reader.i32("map_trading_count")
    technology_trading_count = reader.i32("technology_trading_count")
    gold_trading_count = reader.i32("gold_trading_count")
    embassy_trading_count = reader.i32("embassy_trading_count")
    open_border_trading_count = reader.i32("open_border_trading_count")
    defensive_pact_trading_count = reader.i32("defensive_pact_trading_count")
    research_agreement_trading_count = reader.i32("research_agreement_trading_count")
    trade_agreement_trading_count = reader.i32("trade_agreement_trading_count")
    permanent_alliance_trading_count = reader.i32("permanent_alliance_trading_count")
    bridge_building_count = reader.i32("bridge_building_count")
    water_working_count = reader.i32("water_working_count")
    river_trading_count = reader.i32("river_trading_count")
    border_obstacle_count = reader.i32("border_obstacle_count")
    victory_points = reader.i32("victory_points")
    extra_embarked_movement = reader.i32("extra_embarked_movement")
    extra_embarked_sight = reader.i32("extra_embarked_sight")
    can_embark_count = reader.i32("can_embark_count")
    defensive_embark_count = reader.i32("defensive_embark_count")
    all_water_passage_count = reader.i32("all_water_passage_count")
    natural_wonders_discovered = reader.i32("natural_wonders_discovered")
    best_possible_route = _read_route(reader, "best_possible_route")
    minor_civilizations_attacked = reader.i32("minor_civilizations_attacked")
    flags = _read_flags(reader)
    team_id_offset = reader.offset
    team_id = reader.i32("team_id")
    if team_id != team_index:
        reader.fail(
            f"team ID is {team_id}, expected {team_index}", offset=team_id_offset
        )
    current_era = reader.i32("current_era")
    liberated_by_team = reader.i32("liberated_by_team")
    killed_by_team = reader.i32("killed_by_team")

    technology_sharing_counts = _read_ints(
        reader, _TEAM_COUNT, "technology_sharing_counts"
    )
    turns_at_war = _read_ints(reader, _TEAM_COUNT, "turns_at_war")
    turns_locked_into_war = _read_ints(reader, _TEAM_COUNT, "turns_locked_into_war")
    extra_domain_movement = _read_ints(reader, _DOMAIN_COUNT, "extra_domain_movement")
    vote_source_eligibility_counts = _read_hashed_ints(
        reader,
        expected_count=_VOTE_SOURCE_COUNT,
        field="vote_source_eligibility_counts",
    )
    turns_peace_made = _read_ints(reader, _TEAM_COUNT, "turns_peace_made")
    ignore_warning_counts = _read_ints(reader, _TEAM_COUNT, "ignore_warning_counts")
    has_met = _read_bools(reader, _TEAM_COUNT, "has_met")
    has_found_territory = _read_bools(reader, _TEAM_COUNT, "has_found_territory")
    at_war = _read_bools(reader, _TEAM_COUNT, "at_war")
    permanent_war_or_peace = _read_bools(reader, _TEAM_COUNT, "permanent_war_or_peace")
    has_embassy = _read_bools(reader, _TEAM_COUNT, "has_embassy")
    has_open_borders = _read_bools(reader, _TEAM_COUNT, "has_open_borders")
    has_defensive_pact = _read_bools(reader, _TEAM_COUNT, "has_defensive_pact")
    has_research_agreement = _read_bools(reader, _TEAM_COUNT, "has_research_agreement")
    has_trade_agreement = _read_bools(reader, _TEAM_COUNT, "has_trade_agreement")
    force_peace = _read_bools(reader, _TEAM_COUNT, "force_peace")

    can_launch_victories = _read_hashed_bools(
        reader, expected_count=_VICTORY_COUNT, field="can_launch_victories"
    )
    victories_achieved = _read_hashed_bools(
        reader, expected_count=_VICTORY_COUNT, field="victories_achieved"
    )
    small_awards_achieved = _read_hashed_bools(
        reader,
        expected_count=_SMALL_AWARD_COUNT,
        field="small_awards_achieved",
    )
    route_changes = _read_hashed_ints(
        reader, expected_count=_ROUTE_COUNT, field="route_changes"
    )
    build_time_changes = _read_hashed_ints(
        reader, expected_count=_BUILD_COUNT, field="build_time_changes"
    )
    project_counts = _read_hashed_ints(
        reader, expected_count=_PROJECT_COUNT, field="project_counts"
    )
    project_default_art_types = _read_hashed_ints(
        reader,
        expected_count=_PROJECT_COUNT,
        field="project_default_art_types",
    )
    project_art_types = _read_project_art(reader, project_counts)
    projects_being_constructed = _read_hashed_ints(
        reader,
        expected_count=_PROJECT_COUNT,
        field="projects_being_constructed",
    )
    unit_class_counts = _read_hashed_ints(
        reader, expected_count=_UNIT_CLASS_COUNT, field="unit_class_counts"
    )
    building_class_counts = _read_hashed_ints(
        reader,
        expected_count=_BUILDING_CLASS_COUNT,
        field="building_class_counts",
    )
    obsolete_building_counts = _read_hashed_ints(
        reader,
        expected_count=_BUILDING_COUNT,
        field="obsolete_building_counts",
    )
    terrain_trade_counts = _read_hashed_ints(
        reader, expected_count=_TERRAIN_COUNT, field="terrain_trade_counts"
    )
    victory_countdowns = _read_hashed_ints(
        reader, expected_count=_VICTORY_COUNT, field="victory_countdowns"
    )
    turns_teams_met = _read_ints(reader, _CIV_TEAM_COUNT, "turns_teams_met")
    (
        technology_version,
        last_technology_index,
        last_technology,
        technologies,
    ) = _read_technologies(reader)
    improvement_yield_changes = _read_improvement_yield_array(
        reader, "improvement_yield_changes"
    )
    no_fresh_water_improvement_yield_changes = _read_improvement_yield_array(
        reader, "no_fresh_water_improvement_yield_changes"
    )
    fresh_water_improvement_yield_changes = _read_improvement_yield_array(
        reader, "fresh_water_improvement_yield_changes"
    )
    revealed_resources = _read_revealed_resources(reader)

    return CvTeam(
        team_index=team_index,
        byte_offset=start,
        byte_length=reader.offset - start,
        version=version,
        member_count=member_count,
        alive_member_count=alive_member_count,
        ever_alive_member_count=ever_alive_member_count,
        city_count=city_count,
        total_population=total_population,
        total_land=total_land,
        nuclear_interception_modifier=nuclear_interception_modifier,
        extra_water_visibility_count=extra_water_visibility_count,
        map_trading_count=map_trading_count,
        technology_trading_count=technology_trading_count,
        gold_trading_count=gold_trading_count,
        embassy_trading_count=embassy_trading_count,
        open_border_trading_count=open_border_trading_count,
        defensive_pact_trading_count=defensive_pact_trading_count,
        research_agreement_trading_count=research_agreement_trading_count,
        trade_agreement_trading_count=trade_agreement_trading_count,
        permanent_alliance_trading_count=permanent_alliance_trading_count,
        bridge_building_count=bridge_building_count,
        water_working_count=water_working_count,
        river_trading_count=river_trading_count,
        border_obstacle_count=border_obstacle_count,
        victory_points=victory_points,
        extra_embarked_movement=extra_embarked_movement,
        extra_embarked_sight=extra_embarked_sight,
        can_embark_count=can_embark_count,
        defensive_embark_count=defensive_embark_count,
        all_water_passage_count=all_water_passage_count,
        natural_wonders_discovered=natural_wonders_discovered,
        best_possible_route=best_possible_route,
        minor_civilizations_attacked=minor_civilizations_attacked,
        flags=flags,
        team_id=team_id,
        current_era=current_era,
        liberated_by_team=liberated_by_team,
        killed_by_team=killed_by_team,
        technology_sharing_counts=technology_sharing_counts,
        turns_at_war=turns_at_war,
        turns_locked_into_war=turns_locked_into_war,
        extra_domain_movement=extra_domain_movement,
        vote_source_eligibility_counts=vote_source_eligibility_counts,
        turns_peace_made=turns_peace_made,
        ignore_warning_counts=ignore_warning_counts,
        has_met=has_met,
        has_found_territory=has_found_territory,
        at_war=at_war,
        permanent_war_or_peace=permanent_war_or_peace,
        has_embassy=has_embassy,
        has_open_borders=has_open_borders,
        has_defensive_pact=has_defensive_pact,
        has_research_agreement=has_research_agreement,
        has_trade_agreement=has_trade_agreement,
        force_peace=force_peace,
        can_launch_victories=can_launch_victories,
        victories_achieved=victories_achieved,
        small_awards_achieved=small_awards_achieved,
        route_changes=route_changes,
        build_time_changes=build_time_changes,
        project_counts=project_counts,
        project_default_art_types=project_default_art_types,
        project_art_types=project_art_types,
        projects_being_constructed=projects_being_constructed,
        unit_class_counts=unit_class_counts,
        building_class_counts=building_class_counts,
        obsolete_building_counts=obsolete_building_counts,
        terrain_trade_counts=terrain_trade_counts,
        victory_countdowns=victory_countdowns,
        turns_teams_met=turns_teams_met,
        technology_version=technology_version,
        last_technology_index=last_technology_index,
        last_technology=last_technology,
        technologies=technologies,
        improvement_yield_changes=improvement_yield_changes,
        no_fresh_water_improvement_yield_changes=(
            no_fresh_water_improvement_yield_changes
        ),
        fresh_water_improvement_yield_changes=(fresh_water_improvement_yield_changes),
        revealed_resources=revealed_resources,
    )


def _iterate_cv_team_array(team_array_bytes: bytes) -> Iterator[CvTeam]:
    reader = _Reader(team_array_bytes)
    for team_index in range(_TEAM_COUNT):
        yield _read_team(reader, team_index)
    if reader.remaining != 0:
        reader.team_index = _TEAM_COUNT - 1
        reader.fail(
            f"{reader.remaining} trailing bytes follow the {_TEAM_COUNT}-team array"
        )


def decode_team_array_bytes_impl(team_array_bytes: bytes) -> Iterator[CvTeam]:
    """Return a lazy iterator over a complete serialized 64-team array."""
    if not team_array_bytes:
        raise CvTeamDecodeError("the CvTeam array is empty", offset=0, team_index=0)
    return _iterate_cv_team_array(team_array_bytes)


def iterate_teams_from_payload_impl(
    payload: bytes, *, byte_offset: int
) -> Iterator[CvTeam]:
    """Yield the 64 CvTeam records at a known decompressed-payload offset."""
    reader = _Reader(payload, byte_offset)
    for team_index in range(_TEAM_COUNT):
        yield _read_team(reader, team_index)


__all__: tuple[str, ...] = ()
