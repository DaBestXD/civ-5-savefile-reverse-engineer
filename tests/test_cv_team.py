"""Tests for the bytes-only CvTeam array decoder."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from savefile_reverse_engineer import CvTeam, CvTeamDecodeError, RouteType
from savefile_reverse_engineer.cv_team import decode_cv_team_array_bytes

_FIXTURE_PATH = Path(__file__).parent / "test_data/cv_team/turn_76_team_array.bin"
_FIXTURE_BYTES = _FIXTURE_PATH.read_bytes()
_TEAM_LENGTH = 0x3424
_TEAM_COUNT = 64


def _replace_unsigned(data: bytes, offset: int, size: int, value: int) -> bytes:
    replacement = value.to_bytes(size, byteorder="little", signed=False)
    return data[:offset] + replacement + data[offset + size :]


def _consume(data: bytes) -> tuple[CvTeam, ...]:
    return tuple(decode_cv_team_array_bytes(data))


def test_turn_76_fixture_decodes_completely() -> None:
    teams = _consume(_FIXTURE_BYTES)

    assert len(teams) == _TEAM_COUNT
    assert [team.team_id for team in teams] == list(range(_TEAM_COUNT))
    assert teams[0].byte_offset == 0
    assert teams[-1].byte_offset + teams[-1].byte_length == len(_FIXTURE_BYTES)
    assert {team.byte_length for team in teams} == {_TEAM_LENGTH}


def test_decodes_fixed_fields_relationships_and_technologies() -> None:
    teams = _consume(_FIXTURE_BYTES)
    team = teams[0]

    assert team.member_count == 1
    assert team.alive_member_count == 1
    assert team.city_count == 4
    assert team.total_population == 44
    assert team.total_land == 56
    assert team.current_era == 2
    assert team.best_possible_route is RouteType.ROAD
    assert len(team.technology_sharing_counts) == 64
    assert len(team.turns_at_war) == 64
    assert len(team.has_met) == 64
    assert len(team.extra_domain_movement) == 5
    assert len(team.turns_teams_met) == 63
    assert len(team.technologies) == 81
    assert team.last_technology_index == 21
    assert team.last_technology is not None
    assert team.last_technology.name == "TECH_THEOLOGY"
    assert team.technologies[21].has_technology
    assert teams[21].member_count == 18
    assert teams[21].alive_member_count == 0
    assert teams[21].last_technology is None


def test_decodes_hashed_arrays_project_art_and_yields() -> None:
    team = next(decode_cv_team_array_bytes(_FIXTURE_BYTES))

    assert len(team.vote_source_eligibility_counts) == 2
    assert [entry.type.name for entry in team.vote_source_eligibility_counts] == [
        "DIPLOVOTE_UN",
        "DIPLOVOTE_POPE",
    ]
    assert len(team.can_launch_victories) == 6
    assert len(team.build_time_changes) == 70
    assert len(team.project_counts) == 6
    assert len(team.unit_class_counts) == 113
    assert len(team.building_class_counts) == 177
    assert len(team.obsolete_building_counts) == 268
    assert len(team.terrain_trade_counts) == 9
    assert len(team.improvement_yield_changes) == 46
    assert len(team.no_fresh_water_improvement_yield_changes) == 46
    assert len(team.fresh_water_improvement_yield_changes) == 46
    assert team.unit_class_counts[0].type.name == "UNITCLASS_SETTLER"
    assert team.project_art_types[0].project.name == "PROJECT_MANHATTAN_PROJECT"
    assert team.project_art_types[0].art_types == ()
    missing_improvement = team.improvement_yield_changes[27]
    assert missing_improvement.type.hash_value == 0
    assert missing_improvement.value is None
    first_changes = team.improvement_yield_changes[0].value
    assert first_changes is not None
    assert first_changes.food == 0
    assert team.revealed_resources == ()


def test_preserves_unknown_hash_and_decodes_variable_revealed_resources() -> None:
    unknown_hash = 0x12345678
    unknown_victory = _replace_unsigned(_FIXTURE_BYTES, 0x840, 4, unknown_hash)
    team = next(decode_cv_team_array_bytes(unknown_victory))
    assert team.can_launch_victories[0].type.hash_value == unknown_hash
    assert team.can_launch_victories[0].type.name is None

    resource_hash = 0x2E1008E0
    first = _replace_unsigned(_FIXTURE_BYTES[:_TEAM_LENGTH], 0x3420, 4, 1)
    first += resource_hash.to_bytes(4, byteorder="little")
    variable_array = first + _FIXTURE_BYTES[_TEAM_LENGTH:]
    teams = _consume(variable_array)
    assert teams[0].byte_length == _TEAM_LENGTH + 4
    assert teams[0].revealed_resources[0].name == "RESOURCE_WHEAT"
    assert teams[1].byte_offset == _TEAM_LENGTH + 4


def test_decodes_variable_project_art() -> None:
    first = _replace_unsigned(_FIXTURE_BYTES[:_TEAM_LENGTH], 0xACC, 4, 1)
    first = first[:0xB34] + (7).to_bytes(4, byteorder="little", signed=True) + first[0xB34:]
    teams = _consume(first + _FIXTURE_BYTES[_TEAM_LENGTH:])

    assert teams[0].byte_length == _TEAM_LENGTH + 4
    assert teams[0].project_art_types[0].art_types == (7,)


def test_iterator_is_lazy_after_first_record() -> None:
    data = _FIXTURE_BYTES[:_TEAM_LENGTH] + b"\0\0\0\0"
    iterator: Iterator[CvTeam] = decode_cv_team_array_bytes(data)

    assert next(iterator).team_id == 0
    with pytest.raises(CvTeamDecodeError):
        _ = next(iterator)


def test_rejects_empty_truncated_and_trailing_input() -> None:
    with pytest.raises(CvTeamDecodeError, match="empty"):
        _ = decode_cv_team_array_bytes(b"")
    with pytest.raises(CvTeamDecodeError, match="truncated"):
        _ = _consume(_FIXTURE_BYTES[:100])
    with pytest.raises(CvTeamDecodeError, match="trailing bytes"):
        _ = _consume(_FIXTURE_BYTES + b"\0\0\0\0")


def test_rejects_invalid_version_boolean_team_id_and_count() -> None:
    invalid_version = _replace_unsigned(_FIXTURE_BYTES, 0, 4, 2)
    invalid_boolean = _replace_unsigned(_FIXTURE_BYTES, 0x7C, 1, 2)
    invalid_team_id = _replace_unsigned(_FIXTURE_BYTES, 0x84, 4, 9)
    invalid_count = _replace_unsigned(_FIXTURE_BYTES, 0x83C, 4, 7)

    with pytest.raises(CvTeamDecodeError, match="CvTeam version"):
        _ = next(decode_cv_team_array_bytes(invalid_version))
    with pytest.raises(CvTeamDecodeError, match="Boolean"):
        _ = next(decode_cv_team_array_bytes(invalid_boolean))
    with pytest.raises(CvTeamDecodeError, match="team ID"):
        _ = next(decode_cv_team_array_bytes(invalid_team_id))
    with pytest.raises(CvTeamDecodeError, match="expected 6"):
        _ = next(decode_cv_team_array_bytes(invalid_count))


def test_rejects_unsafe_variable_counts() -> None:
    revealed_count = _replace_unsigned(
        _FIXTURE_BYTES, 0x3420, 4, 0xFFFFFFFF
    )
    project_art_count = _replace_unsigned(_FIXTURE_BYTES, 0xB2C, 4, 7)
    negative_project_count = _replace_unsigned(
        _FIXTURE_BYTES, 0xACC, 4, 0xFFFFFFFF
    )

    with pytest.raises(CvTeamDecodeError, match="revealed_resources.count"):
        _ = next(decode_cv_team_array_bytes(revealed_count))
    with pytest.raises(CvTeamDecodeError, match="project_art_types.count"):
        _ = next(decode_cv_team_array_bytes(project_art_count))
    with pytest.raises(CvTeamDecodeError, match="nonnegative"):
        _ = next(decode_cv_team_array_bytes(negative_project_count))
