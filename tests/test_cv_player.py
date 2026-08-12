"""Tests for CvPlayer decoding with nested city and unit free lists."""

from pathlib import Path

import pytest

from savefile_reverse_engineer import (
    Civ5SaveDecoder,
    ProductionOrderType,
)
from savefile_reverse_engineer._raw._shared.firaxis_hash import firaxis_hash
from savefile_reverse_engineer._raw.header.decoder import (
    decode_header_bytes_impl,
    decompress_payload_bytes_impl,
)
from savefile_reverse_engineer._raw.map.payload_locator import (
    locate_cv_plots,
    locate_cv_teams,
)
from savefile_reverse_engineer._raw.player.cities import (
    read_city_buildings,
    read_city_yield_values,
)
from savefile_reverse_engineer._raw.player.city_models import (
    CvCityBuildings,
)
from savefile_reverse_engineer._raw.player.city_models import (
    ProductionOrderType as RawProductionOrderType,
)
from savefile_reverse_engineer._raw.player.decoder import (
    decode_player_array_bytes_impl as decode_player_array_bytes,
)
from savefile_reverse_engineer._raw.player.decoder import (
    iterate_players_from_payload_impl,
)
from savefile_reverse_engineer._raw.player.infrastructure import (
    CvPlayerDecodeError,
    PlayerReader,
)
from savefile_reverse_engineer._raw.team.decoder import iterate_teams_from_payload_impl

_PROJECT_ROOT = Path(__file__).parent.parent
_SAVE_PATH = (
    _PROJECT_ROOT / "test-save-file/multi-player/AutoSave_Post_0076 AD-0040.Civ5Save"
)
_EARLY_SAVE_PATH = (
    _PROJECT_ROOT / "test-save-file/multi-player/AutoSave_Post_0027 BC-2380.Civ5Save"
)
_UNKNOWN_BUILDING_HASH = 0x12345678
_BUILDING_TYPE_COUNT = 268
_UNIT_TYPE_COUNT = 265
_IMPROVEMENT_TYPE_COUNT = 46
_UNIT_COMBAT_TYPE_COUNT = 18
_PROMOTION_TYPE_COUNT = 340
_POLICY_SLOT_COUNT = 138
_POLICY_BRANCH_COUNT = 12

_requires_save = pytest.mark.skipif(
    not _SAVE_PATH.is_file(), reason="the local Lekmod v34.11 save is unavailable"
)
_requires_early_save = pytest.mark.skipif(
    not _EARLY_SAVE_PATH.is_file(),
    reason="the early local Lekmod v34.11 save is unavailable",
)


def _payload(path: Path) -> bytes:
    save_bytes = path.read_bytes()
    return decompress_payload_bytes_impl(
        save_bytes, decode_header_bytes_impl(save_bytes)
    )


def _player_array_inputs(
    path: Path,
) -> tuple[bytes, int, tuple[tuple[int, int], ...]]:
    payload = _payload(path)
    plot_location = locate_cv_plots(payload)
    team_location = locate_cv_teams(payload, plot_location)
    teams = tuple(
        iterate_teams_from_payload_impl(payload, byte_offset=team_location.byte_offset)
    )
    return (
        payload,
        teams[-1].byte_offset + teams[-1].byte_length,
        tuple((team.total_population, team.total_land) for team in teams),
    )


@_requires_save
def test_decodes_participant_players_and_nested_objects() -> None:
    players = Civ5SaveDecoder(_SAVE_PATH).players

    assert [player.player_index for player in players] == [
        0,
        1,
        2,
        22,
        23,
        24,
        25,
        63,
    ]
    assert players[0].total_population == 44
    assert players[0].total_land == 56
    assert players[0].culture_x100 == 23_000
    assert players[0].faith == 62
    assert [player.display_name for player in players[:3]] == [
        "Brad, From Algebra",
        "PostiveMentalAttitude",
        "Wyldmaenn",
    ]
    assert [player.display_name for player in players[3:]] == [
        "TXT_KEY_CITYSTATE_MEXICO",
        "TXT_KEY_CITYSTATE_LA_VENTA",
        "TXT_KEY_CITYSTATE_PRAGUE",
        "TXT_KEY_CITYSTATE_HONG_KONG",
        "LEADER_BARBARIAN",
    ]
    assert len(players[0].cities) == 4
    assert len(players[0].units) == 16
    assert players[-1].cities == ()
    assert players[-1].units == ()


@_requires_save
def test_decodes_raw_player_policy_information() -> None:
    payload, player_offset, expected_totals = _player_array_inputs(_SAVE_PATH)
    raw_player = next(
        iterate_players_from_payload_impl(
            payload,
            byte_offset=player_offset,
            expected_totals=expected_totals,
        )
    )
    information = raw_player.policy_information
    owned_by_name = {
        policy.policy_type.name: policy.owned
        for policy in information.policy_slots
        if policy.policy_type.name is not None
    }

    assert information.byte_offset == 0x428708
    assert information.version == 2
    assert len(information.policy_slots) == _POLICY_SLOT_COUNT
    assert (
        sum(policy.policy_type.hash_value == 0 for policy in information.policy_slots)
        == 14
    )
    assert all(
        policy.policy_type.hash_value == 0 or policy.policy_type.name is not None
        for policy in information.policy_slots
    )
    assert len(information.branches) == _POLICY_BRANCH_COUNT
    assert [branch.branch_type.name for branch in information.branches] == [
        "POLICY_BRANCH_TRADITION",
        "POLICY_BRANCH_LIBERTY",
        "POLICY_BRANCH_HONOR",
        "POLICY_BRANCH_PIETY",
        "POLICY_BRANCH_PATRONAGE",
        "POLICY_BRANCH_AESTHETICS",
        "POLICY_BRANCH_COMMERCE",
        "POLICY_BRANCH_EXPLORATION",
        "POLICY_BRANCH_RATIONALISM",
        "POLICY_BRANCH_FREEDOM",
        "POLICY_BRANCH_ORDER",
        "POLICY_BRANCH_AUTOCRACY",
    ]
    assert owned_by_name["POLICY_TRADITION"] is True
    assert owned_by_name["POLICY_TRADITION_FINISHER"] is True
    assert owned_by_name["POLICY_LIBERTY"] is False


@_requires_save
def test_decodes_semantic_player_policy_information() -> None:
    player = Civ5SaveDecoder(_SAVE_PATH).players[0]
    information = player.policy_information
    branches = {branch.branch_type.key: branch for branch in information.branches}

    assert [policy.key for policy in information.owned_policies] == [
        "POLICY_TRADITION",
        "POLICY_ARISTOCRACY",
        "POLICY_OLIGARCHY",
        "POLICY_LEGALISM",
        "POLICY_LANDED_ELITE",
        "POLICY_MONARCHY",
        "POLICY_TRADITION_FINISHER",
        "POLICY_EXPLORATION",
        "POLICY_MARITIME_INFRASTRUCTURE",
    ]
    assert branches["POLICY_BRANCH_TRADITION"].unlocked is True
    assert branches["POLICY_BRANCH_EXPLORATION"].unlocked is True
    assert branches["POLICY_BRANCH_LIBERTY"].unlocked is False
    assert [
        policy.key for policy in branches["POLICY_BRANCH_TRADITION"].owned_policies
    ] == [
        "POLICY_TRADITION",
        "POLICY_ARISTOCRACY",
        "POLICY_OLIGARCHY",
        "POLICY_LEGALISM",
        "POLICY_LANDED_ELITE",
        "POLICY_MONARCHY",
        "POLICY_TRADITION_FINISHER",
    ]


@_requires_early_save
def test_preserves_multiple_partial_branch_policies() -> None:
    player = Civ5SaveDecoder(_EARLY_SAVE_PATH).players[0]
    tradition = next(
        branch
        for branch in player.policy_information.branches
        if branch.branch_type.key == "POLICY_BRANCH_TRADITION"
    )

    assert tradition.unlocked is True
    assert [policy.key for policy in tradition.owned_policies] == [
        "POLICY_TRADITION",
        "POLICY_LEGALISM",
        "POLICY_MONARCHY",
    ]


@_requires_save
def test_decodes_semantic_city_fields_and_ownership() -> None:
    player = Civ5SaveDecoder(_SAVE_PATH).players[0]
    cities = player.cities

    assert [city.city_id for city in cities] == [8192, 16385, 24578, 32771]
    assert [city.name_key for city in cities] == [
        "TXT_KEY_CITY_NAME_VENEZ",
        "TXT_KEY_CITY_NAME_RAGUZ",
        "TXT_KEY_CITY_NAME_CANDIA",
        "TXT_KEY_CITY_NAME_ZARA",
    ]
    assert {city.owner_player_index for city in cities} == {0}
    assert [(city.x, city.y) for city in cities] == [
        (11, 16),
        (16, 14),
        (7, 20),
        (6, 26),
    ]
    assert [city.population for city in cities] == [16, 9, 10, 9]
    assert sum(city.population for city in cities) == player.total_population


@_requires_save
def test_decodes_semantic_city_yield_vectors() -> None:
    capital = Civ5SaveDecoder(_SAVE_PATH).cities[0]
    vectors = capital.yield_vectors

    assert vectors.base_yield_rate_from_terrain.science == 0
    assert vectors.base_yield_rate_from_buildings.science == 6
    assert vectors.base_yield_rate_from_specialists.science == 0
    assert vectors.base_yield_rate_from_misc.science == 16
    assert vectors.base_yield_rate_from_religion.science == 0
    assert vectors.base_yield_rate_from_policies.science == 0
    assert vectors.yield_per_population_x100.science == 50
    assert vectors.yield_rate_modifier.science == 0
    assert vectors.production_to_yield_modifier.science == 0


@_requires_save
def test_decodes_only_present_city_buildings() -> None:
    cities = Civ5SaveDecoder(_SAVE_PATH).players[0].cities

    second_city_by_name = {
        entry.building_type.key: entry for entry in cities[1].buildings
    }
    capital_by_name = {entry.building_type.key: entry for entry in cities[0].buildings}

    assert [len(city.buildings) for city in cities] == [17, 9, 8, 6]
    assert all(
        state.real_count > 0 or state.free_count > 0
        for city in cities
        for state in city.buildings
    )
    assert second_city_by_name["BUILDING_LIBRARY"].real_count == 1
    assert second_city_by_name["BUILDING_LIBRARY"].free_count == 0
    assert second_city_by_name["BUILDING_GRANARY"].real_count == 1
    assert "BUILDING_GREAT_LIGHTHOUSE" not in capital_by_name


@_requires_save
def test_decodes_city_production_queue_and_current_building() -> None:
    cities = Civ5SaveDecoder(_SAVE_PATH).players[0].cities

    assert [len(city.production_queue) for city in cities] == [1, 1, 1, 1]
    assert all(city.current_production == city.production_queue[0] for city in cities)
    assert [
        city.current_production.item_type.key
        for city in cities
        if city.current_production is not None
    ] == [
        "BUILDING_GREAT_LIGHTHOUSE",
        "BUILDING_CIRCUS",
        "BUILDING_CHICHEN_ITZA",
        "BUILDING_LIGHTHOUSE",
    ]
    assert all(
        city.current_production is not None
        and city.current_production.order_type is ProductionOrderType.CONSTRUCT_BUILDING
        for city in cities
    )
    capital_production = cities[0].current_production
    assert capital_production is not None
    assert capital_production.item_type.key == "BUILDING_GREAT_LIGHTHOUSE"
    assert capital_production.production_x100 == 7081
    assert capital_production.production_inactive_turns == 0


@_requires_early_save
def test_unit_current_production_has_no_decoded_progress() -> None:
    cities = Civ5SaveDecoder(_EARLY_SAVE_PATH).players[0].cities

    assert [
        city.current_production.item_type.key
        for city in cities
        if city.current_production is not None
    ] == ["UNIT_SETTLER", "UNIT_WORKER"]
    assert all(
        city.current_production is not None
        and city.current_production.order_type is ProductionOrderType.TRAIN_UNIT
        for city in cities
    )
    assert all(
        city.current_production is not None
        and city.current_production.production_x100 is None
        and city.current_production.production_inactive_turns is None
        for city in cities
    )


@_requires_early_save
def test_writer_guided_city_probe_rejects_false_prefix_markers() -> None:
    cities = Civ5SaveDecoder(_EARLY_SAVE_PATH).players[0].cities

    assert [city.city_id for city in cities] == [8192, 16385]
    assert [(city.x, city.y) for city in cities] == [(11, 16), (16, 14)]
    assert [len(city.buildings) for city in cities] == [3, 1]


@_requires_save
def test_decodes_unit_ids_coordinates_and_deleted_slots() -> None:
    player = Civ5SaveDecoder(_SAVE_PATH).players[0]
    units = player.units

    assert units[0].unit_id == 57344
    assert units[0].unit_hash == firaxis_hash("UNIT_WORKER")
    assert units[0].unit_name == "UNIT_WORKER"
    assert (units[0].x, units[0].y) == (12, 15)
    assert len(units) == 16
    assert {unit.owner_player_index for unit in units} == {0}


@_requires_save
def test_returns_cached_nested_results() -> None:
    decoder = Civ5SaveDecoder(_SAVE_PATH)
    first = decoder.players[0]
    repeated = decoder.players[0]

    assert repeated == first
    assert repeated is first
    assert repeated.cities[0] is first.cities[0]


@_requires_save
def test_nested_errors_keep_absolute_player_context() -> None:
    valid_payload, player_offset, expected_totals = _player_array_inputs(_SAVE_PATH)
    first_player = next(
        iterate_players_from_payload_impl(
            valid_payload,
            byte_offset=player_offset,
            expected_totals=expected_totals,
        )
    )
    invalid_version_offset = first_player.cities.entries[0].byte_offset
    payload = bytearray(valid_payload)
    payload[invalid_version_offset : invalid_version_offset + 4] = (7).to_bytes(
        4, "little"
    )

    players = iterate_players_from_payload_impl(
        bytes(payload), byte_offset=player_offset, expected_totals=expected_totals
    )
    with pytest.raises(CvPlayerDecodeError) as raised:
        _ = next(players)

    assert raised.value.player_index == 0
    assert raised.value.offset == invalid_version_offset
    assert raised.value.field == "cities.entries[0].version"


def _free_list_header(*, live: bool) -> bytes:
    occupied_last_index = 0 if live else -1
    values = (
        8,
        occupied_last_index,
        -1,
        0,
        8192,
        -1,
        -1,
        -1,
        -1,
        -1,
        -1,
        -1,
        -1,
        int(live),
    )
    return b"".join(value.to_bytes(4, "little", signed=True) for value in values)


def _i32_values(values: tuple[int, ...]) -> bytes:
    return b"".join(value.to_bytes(4, "little", signed=True) for value in values)


def _int_vector(values: tuple[int, ...]) -> bytes:
    return len(values).to_bytes(4, "little") + _i32_values(values)


def _bool_vector(values: tuple[bool, ...]) -> bytes:
    return len(values).to_bytes(4, "little") + bytes(values)


def _utf8(value: str) -> bytes:
    encoded = value.encode()
    return len(encoded).to_bytes(4, "little") + encoded


def _hashed_int_array(hashes: tuple[int, ...], values: tuple[int | None, ...]) -> bytes:
    encoded = bytearray(len(hashes).to_bytes(4, "little", signed=True))
    for hash_value, value in zip(hashes, values, strict=True):
        encoded.extend(hash_value.to_bytes(4, "little"))
        if hash_value != 0:
            if value is None:
                raise ValueError("a nonzero hash requires an integer value")
            encoded.extend(value.to_bytes(4, "little", signed=True))
        elif value is not None:
            raise ValueError("a zero hash cannot have an integer value")
    return bytes(encoded)


def _hashed_bool_array(
    hashes: tuple[int, ...], values: tuple[bool | None, ...]
) -> bytes:
    encoded = bytearray(len(hashes).to_bytes(4, "little"))
    for hash_value, value in zip(hashes, values, strict=True):
        encoded.extend(hash_value.to_bytes(4, "little"))
        if hash_value != 0:
            if value is None:
                raise ValueError("a nonzero hash requires a Boolean value")
            encoded.append(value)
        elif value is not None:
            raise ValueError("a zero hash cannot have a Boolean value")
    return bytes(encoded)


def _synthetic_policy_information() -> bytes:
    policy_hashes = (
        firaxis_hash("POLICY_LIBERTY"),
        _UNKNOWN_BUILDING_HASH,
        *(firaxis_hash(f"POLICY_SYNTHETIC_{index}") for index in range(2, 124)),
        *(0 for _ in range(14)),
    )
    policy_values = (
        True,
        False,
        *(False for _ in range(122)),
        *(None for _ in range(14)),
    )
    branch_names = (
        "TRADITION",
        "LIBERTY",
        "HONOR",
        "PIETY",
        "PATRONAGE",
        "AESTHETICS",
        "COMMERCE",
        "EXPLORATION",
        "RATIONALISM",
        "FREEDOM",
        "ORDER",
        "AUTOCRACY",
    )
    branch_hashes = tuple(
        firaxis_hash(f"POLICY_BRANCH_{name}") for name in branch_names
    )
    branch_values = (True, *(False for _ in range(_POLICY_BRANCH_COUNT - 1)))
    return b"".join(
        (
            (2).to_bytes(4, "little"),
            *(_hashed_bool_array(policy_hashes, policy_values) for _ in range(3)),
            *(_hashed_bool_array(branch_hashes, branch_values) for _ in range(2)),
        )
    )


def _synthetic_building_hashes() -> tuple[int, ...]:
    return (
        firaxis_hash("BUILDING_GRANARY"),
        firaxis_hash("BUILDING_LIBRARY"),
        _UNKNOWN_BUILDING_HASH,
        0,
        *(
            firaxis_hash(f"BUILDING_SYNTHETIC_{index}")
            for index in range(4, _BUILDING_TYPE_COUNT)
        ),
    )


def _values_with(
    default: int | None, replacements: dict[int, int | None]
) -> tuple[int | None, ...]:
    return tuple(
        replacements.get(index, default) for index in range(_BUILDING_TYPE_COUNT)
    )


def _synthetic_city_buildings() -> bytes:
    hashes = _synthetic_building_hashes()
    header = _i32_values((1, 2, 5, 400, 0, 0, 0, 0, 0, 0)) + bytes((0,))
    arrays = (
        _values_with(0, {2: 1234, 3: None}),
        _values_with(0, {2: 3, 3: None}),
        _values_with(-1, {0: 0, 1: 0, 3: None}),
        _values_with(-(1 << 31), {0: -40, 1: -40, 3: None}),
        _values_with(0, {0: 1, 3: None}),
        _values_with(0, {1: 1, 3: None}),
    )
    return header + b"".join(_hashed_int_array(hashes, values) for values in arrays)


def _production_order(
    order_type: RawProductionOrderType,
    item_hash: int,
    secondary_data: int,
    *,
    save: bool = False,
    rush: bool = False,
) -> bytes:
    return b"".join(
        (
            _i32_values((order_type.value,)),
            item_hash.to_bytes(4, "little"),
            _i32_values((secondary_data,)),
            bytes((save, rush)),
        )
    )


def _synthetic_city_after_buildings() -> bytes:
    zero_unit_array = _hashed_int_array(
        tuple(0 for _ in range(_UNIT_TYPE_COUNT)),
        tuple(None for _ in range(_UNIT_TYPE_COUNT)),
    )
    zero_promotion_array = _hashed_int_array(
        tuple(0 for _ in range(_PROMOTION_TYPE_COUNT)),
        tuple(None for _ in range(_PROMOTION_TYPE_COUNT)),
    )
    orders = (
        _production_order(
            RawProductionOrderType.CONSTRUCT_BUILDING,
            firaxis_hash("BUILDING_GRANARY"),
            -1,
        ),
        _production_order(
            RawProductionOrderType.TRAIN_UNIT,
            firaxis_hash("UNIT_SETTLER"),
            2,
            save=True,
        ),
    )
    return b"".join(
        (
            _i32_values((0, 0)),
            zero_unit_array,
            zero_unit_array,
            *(_int_vector(tuple(0 for _ in range(7))) for _ in range(4)),
            _int_vector(tuple(0 for _ in range(_IMPROVEMENT_TYPE_COUNT))),
            *(
                _int_vector(tuple(0 for _ in range(_UNIT_COMBAT_TYPE_COUNT)))
                for _ in range(2)
            ),
            zero_promotion_array,
            len(orders).to_bytes(4, "little"),
            *orders,
        )
    )


def _synthetic_city_prefix_to_buildings() -> bytes:
    city_prefix = _i32_values((6, 8192, 2, 3, -1, -1, 10, 10, 7, 7, 0, 0, 0, 250, 1))
    yield_vectors = tuple(
        tuple(vector_index * 10 + yield_index for yield_index in range(7))
        for vector_index in range(18)
    )
    return b"".join(
        (
            city_prefix,
            _i32_values(tuple(0 for _ in range(44))),
            bytes(10),
            _i32_values((0, 0, 0, 0)),
            *(_int_vector(values) for values in yield_vectors),
            *(_int_vector(tuple(0 for _ in range(5))) for _ in range(2)),
            _bool_vector(tuple(False for _ in range(80))),
            _bool_vector(tuple(False for _ in range(80))),
            bytes((0,)),
            _i32_values((-1,)),
            _utf8("Synthetic City"),
            _utf8(""),
            *(
                _hashed_int_array(
                    tuple(0 for _ in range(57)),
                    tuple(None for _ in range(57)),
                )
                for _ in range(3)
            ),
            _int_vector(tuple(0 for _ in range(7))),
            _int_vector(tuple(0 for _ in range(6))),
        )
    )


def _synthetic_unit() -> bytes:
    prefix = _i32_values((9, 0, 0, 1, 3, 4, 8192))
    archive_tail = b"".join(
        (
            _i32_values(tuple(0 for _ in range(8))),
            bytes((0,)),
            _i32_values(tuple(0 for _ in range(10))),
            bytes((0,)),
            _i32_values(tuple(0 for _ in range(93))),
            bytes(7),
            _i32_values((0,)),
            _bool_vector(tuple(False for _ in range(340))),
            bytes(2),
            _i32_values(tuple(0 for _ in range(6))),
            _utf8(""),
            _utf8(""),
            _int_vector(tuple(0 for _ in range(7))),
            _int_vector(tuple(0 for _ in range(7))),
            _bool_vector(tuple(False for _ in range(8))),
            *(
                _int_vector(tuple(0 for _ in range(count)))
                for count in (9, 25, 9, 25, 9, 9, 25, 25, 18, 113)
            ),
            _i32_values(tuple(0 for _ in range(6))),
        )
    )
    unit_hash = firaxis_hash("UNIT_WORKER").to_bytes(4, "little")
    return prefix + archive_tail + unit_hash


def _synthetic_player_record(
    *,
    has_objects: bool,
    false_unit_prefix: bool = False,
    duplicate_policy_information: bool = False,
) -> bytes:
    values = (16, 0, 0, *(0 for _ in range(14)))
    record = bytearray(
        b"".join(value.to_bytes(4, "little", signed=True) for value in values)
    )
    policy_information = _synthetic_policy_information()
    record.extend(policy_information)
    if duplicate_policy_information:
        record.extend(policy_information)
    record.extend(_free_list_header(live=has_objects))
    if has_objects:
        record.extend(_synthetic_city_prefix_to_buildings())
        record.extend(_synthetic_city_buildings())
        record.extend(_synthetic_city_after_buildings())
    record.extend(_free_list_header(live=has_objects))
    if has_objects:
        if false_unit_prefix:
            record.extend(_i32_values((9, 0, 0, 49, 8, 8, 8192)))
        record.extend(_synthetic_unit())
    record.extend(_free_list_header(live=False))
    record.extend(bytes(0x20000 - len(record)))
    return bytes(record)


@pytest.fixture(scope="module")
def synthetic_player_array() -> bytes:
    return _synthetic_player_record(has_objects=True) + (
        _synthetic_player_record(has_objects=False) * 63
    )


def test_bytes_only_decoder_uses_exact_structural_path(
    synthetic_player_array: bytes,
) -> None:
    players = tuple(decode_player_array_bytes(synthetic_player_array))
    policy_information = players[0].policy_information
    buildings = players[0].cities.entries[0].buildings
    entries_by_hash = {entry.building.hash_value: entry for entry in buildings.entries}

    assert len(players) == 64
    assert len(policy_information.policy_slots) == _POLICY_SLOT_COUNT
    assert policy_information.policy_slots[0].policy_type.name == "POLICY_LIBERTY"
    assert policy_information.policy_slots[0].owned is True
    assert policy_information.policy_slots[1].policy_type.hash_value == (
        _UNKNOWN_BUILDING_HASH
    )
    assert policy_information.policy_slots[1].policy_type.name is None
    assert policy_information.policy_slots[-1].owned is None
    assert policy_information.branches[0].branch_type.name == (
        "POLICY_BRANCH_TRADITION"
    )
    assert policy_information.branches[0].unlocked is True
    assert players[0].cities.entries[0].population == 7
    yield_vectors = players[0].cities.entries[0].yield_vectors
    assert yield_vectors.sea_plot_yield.food == 0
    assert yield_vectors.base_yield_rate_from_terrain.science == 43
    assert yield_vectors.base_yield_rate_from_buildings.science == 53
    assert yield_vectors.base_yield_rate_from_specialists.science == 63
    assert yield_vectors.base_yield_rate_from_misc.science == 73
    assert yield_vectors.base_yield_rate_from_religion.science == 83
    assert yield_vectors.base_yield_rate_from_policies.science == 93
    assert yield_vectors.garrison_yield_bonus.science == 103
    assert yield_vectors.yield_per_population_x100.science == 113
    assert yield_vectors.yield_per_religion_x100.science == 123
    assert yield_vectors.yield_rate_modifier.science == 133
    assert yield_vectors.power_yield_rate_modifier.science == 143
    assert yield_vectors.resource_yield_rate_modifier.science == 153
    assert yield_vectors.extra_specialist_yield.science == 163
    assert yield_vectors.production_to_yield_modifier.science == 173
    assert len(buildings.entries) == _BUILDING_TYPE_COUNT
    assert entries_by_hash[firaxis_hash("BUILDING_GRANARY")].real_count == 1
    assert entries_by_hash[firaxis_hash("BUILDING_LIBRARY")].free_count == 1
    assert entries_by_hash[_UNKNOWN_BUILDING_HASH].building.name is None
    assert entries_by_hash[_UNKNOWN_BUILDING_HASH].production_times_100 == 1234
    zero_entry = entries_by_hash[0]
    assert zero_entry.production_times_100 is None
    assert zero_entry.real_count is None
    production_queue = players[0].cities.entries[0].production_queue
    assert [order.order_type for order in production_queue] == [
        RawProductionOrderType.CONSTRUCT_BUILDING,
        RawProductionOrderType.TRAIN_UNIT,
    ]
    assert production_queue[0].item.name == "BUILDING_GRANARY"
    assert production_queue[1].item.name == "UNIT_SETTLER"
    assert production_queue[1].secondary_data == 2
    assert production_queue[1].save is True
    assert all(order.byte_length == 14 for order in production_queue)
    assert players[0].units.entries[0].unit_id == 8192
    assert players[0].units.entries[0].unit_hash == firaxis_hash("UNIT_WORKER")
    assert players[0].units.entries[0].unit_name == "UNIT_WORKER"
    assert players[1].cities.entries == ()


def test_city_yield_vector_rejects_wrong_count() -> None:
    reader = PlayerReader((6).to_bytes(4, "little") + bytes(6 * 4), 0, 3)

    with pytest.raises(CvPlayerDecodeError) as raised:
        _ = read_city_yield_values(reader, field="city.yields")

    assert raised.value.offset == 0
    assert raised.value.player_index == 3
    assert raised.value.field == "city.yields.count"
    assert "expected 7" in raised.value.message


def test_city_yield_vector_reports_truncated_value() -> None:
    data = bytes(10) + (7).to_bytes(4, "little") + bytes(6 * 4)
    reader = PlayerReader(data, 10, 4)

    with pytest.raises(CvPlayerDecodeError) as raised:
        _ = read_city_yield_values(reader, field="city.yields")

    assert raised.value.offset == 38
    assert raised.value.player_index == 4
    assert raised.value.field == "city.yields.golden_age_points"
    assert "truncated" in raised.value.message


def _policy_array_starts(data: bytes | bytearray, start: int) -> tuple[int, ...]:
    starts: list[int] = []
    offset = start + 4
    for _ in range(5):
        starts.append(offset)
        count = int.from_bytes(data[offset : offset + 4], "little")
        offset += 4
        for _ in range(count):
            hash_value = int.from_bytes(data[offset : offset + 4], "little")
            offset += 4 + (1 if hash_value != 0 else 0)
    return tuple(starts)


@pytest.mark.parametrize(
    ("mutation_offset", "replacement"),
    (
        (4, (137).to_bytes(4, "little")),
        (12, bytes((2,))),
    ),
)
def test_rejects_malformed_policy_block(
    synthetic_player_array: bytes,
    mutation_offset: int,
    replacement: bytes,
) -> None:
    first_player = next(decode_player_array_bytes(synthetic_player_array))
    policy_offset = first_player.policy_information.byte_offset
    changed = bytearray(synthetic_player_array)
    start = policy_offset + mutation_offset
    changed[start : start + len(replacement)] = replacement

    with pytest.raises(CvPlayerDecodeError, match="valid policy blocks"):
        _ = tuple(decode_player_array_bytes(bytes(changed)))


def test_rejects_mismatched_policy_hash_order(
    synthetic_player_array: bytes,
) -> None:
    first_player = next(decode_player_array_bytes(synthetic_player_array))
    changed = bytearray(synthetic_player_array)
    arrays = _policy_array_starts(changed, first_player.policy_information.byte_offset)
    second_array_first_hash = arrays[1] + 4
    changed[second_array_first_hash : second_array_first_hash + 4] = (
        _UNKNOWN_BUILDING_HASH.to_bytes(4, "little")
    )

    with pytest.raises(CvPlayerDecodeError, match="valid policy blocks"):
        _ = tuple(decode_player_array_bytes(bytes(changed)))


def test_rejects_missing_policy_block(synthetic_player_array: bytes) -> None:
    first_player = next(decode_player_array_bytes(synthetic_player_array))
    changed = bytearray(synthetic_player_array)
    policy_offset = first_player.policy_information.byte_offset
    changed[policy_offset : policy_offset + 4] = (3).to_bytes(4, "little")

    with pytest.raises(CvPlayerDecodeError, match="found 0 structurally valid"):
        _ = tuple(decode_player_array_bytes(bytes(changed)))


def test_rejects_ambiguous_policy_blocks() -> None:
    player_array = _synthetic_player_record(
        has_objects=True,
        duplicate_policy_information=True,
    ) + (_synthetic_player_record(has_objects=False) * 63)

    with pytest.raises(CvPlayerDecodeError, match="found 2 structurally valid"):
        _ = tuple(decode_player_array_bytes(player_array))


def test_bytes_only_decoder_rejects_trailing_data(
    synthetic_player_array: bytes,
) -> None:
    with pytest.raises(CvPlayerDecodeError, match="no complete 64-player path"):
        _ = tuple(decode_player_array_bytes(synthetic_player_array + b"extra"))


def test_rejects_unknown_city_production_order(
    synthetic_player_array: bytes,
) -> None:
    first_player = next(decode_player_array_bytes(synthetic_player_array))
    order_offset = first_player.cities.entries[0].production_queue[0].byte_offset
    data = bytearray(synthetic_player_array)
    data[order_offset : order_offset + 4] = _i32_values((99,))

    with pytest.raises(
        CvPlayerDecodeError, match="unsupported production order type 99"
    ):
        _ = tuple(decode_player_array_bytes(bytes(data)))


def test_rejects_queued_building_absent_from_inventory(
    synthetic_player_array: bytes,
) -> None:
    first_player = next(decode_player_array_bytes(synthetic_player_array))
    order = first_player.cities.entries[0].production_queue[0]
    item_offset = order.byte_offset + 4
    absent_building_hash = 0x87654321
    data = bytearray(synthetic_player_array)
    data[item_offset : item_offset + 4] = absent_building_hash.to_bytes(4, "little")

    with pytest.raises(CvPlayerDecodeError) as raised:
        _ = tuple(decode_player_array_bytes(bytes(data)))

    assert raised.value.offset == item_offset
    assert raised.value.player_index == 0
    assert raised.value.field == "cities.entries[0].production_queue[0].item"
    assert "absent from the inventory" in raised.value.message


def test_rejects_city_production_queue_over_capacity(
    synthetic_player_array: bytes,
) -> None:
    first_player = next(decode_player_array_bytes(synthetic_player_array))
    count_offset = first_player.cities.entries[0].production_queue[0].byte_offset - 4
    data = bytearray(synthetic_player_array)
    data[count_offset : count_offset + 4] = _i32_values((26,))

    with pytest.raises(CvPlayerDecodeError, match="maximum is 25"):
        _ = tuple(decode_player_array_bytes(bytes(data)))


def test_unit_archive_rejects_false_prefix_marker() -> None:
    player_array = _synthetic_player_record(
        has_objects=True, false_unit_prefix=True
    ) + (_synthetic_player_record(has_objects=False) * 63)

    unit = next(decode_player_array_bytes(player_array)).units.entries[0]

    assert (unit.x, unit.y) == (3, 4)
    assert unit.unit_name == "UNIT_WORKER"


def test_unit_preserves_unknown_serialized_hash(
    synthetic_player_array: bytes,
) -> None:
    known_hash = firaxis_hash("UNIT_WORKER").to_bytes(4, "little")
    unknown_hash = _UNKNOWN_BUILDING_HASH.to_bytes(4, "little")
    changed = synthetic_player_array.replace(known_hash, unknown_hash, 1)

    unit = next(decode_player_array_bytes(changed)).units.entries[0]

    assert unit.unit_hash == _UNKNOWN_BUILDING_HASH
    assert unit.unit_name is None


def _building_array_starts(data: bytes | bytearray) -> tuple[int, ...]:
    starts: list[int] = []
    offset = 4 + 9 * 4 + 1
    for _ in range(6):
        starts.append(offset)
        count = int.from_bytes(data[offset : offset + 4], "little", signed=True)
        offset += 4
        for _ in range(count):
            hash_value = int.from_bytes(data[offset : offset + 4], "little")
            offset += 4 + (4 if hash_value != 0 else 0)
    return tuple(starts)


def _decode_buildings(data: bytes) -> CvCityBuildings:
    return read_city_buildings(
        data,
        start=0,
        end=len(data),
        record_index=0,
        player_index=0,
    )


@pytest.mark.parametrize(
    ("offset", "replacement", "field"),
    (
        (0, (2).to_bytes(4, "little"), "buildings.version"),
        (4 + 9 * 4, bytes((2,)), "sold_building_this_turn"),
        (4 + 9 * 4 + 1, (267).to_bytes(4, "little"), "production.count"),
    ),
)
def test_rejects_invalid_city_building_header(
    offset: int, replacement: bytes, field: str
) -> None:
    data = bytearray(_synthetic_city_buildings())
    data[offset : offset + len(replacement)] = replacement

    with pytest.raises(CvPlayerDecodeError) as raised:
        _ = _decode_buildings(bytes(data))

    assert raised.value.player_index == 0
    assert raised.value.offset == offset
    assert field in raised.value.field


def test_rejects_mismatched_city_building_hash_order() -> None:
    data = bytearray(_synthetic_city_buildings())
    second_array = _building_array_starts(data)[1]
    hash_offset = second_array + 4
    data[hash_offset : hash_offset + 4] = (0x87654321).to_bytes(4, "little")

    with pytest.raises(CvPlayerDecodeError) as raised:
        _ = _decode_buildings(bytes(data))

    assert raised.value.offset == hash_offset
    assert raised.value.field.endswith("arrays[1][0].type")


def test_rejects_truncated_city_building_inventory() -> None:
    data = _synthetic_city_buildings()[:-1]

    with pytest.raises(CvPlayerDecodeError, match="truncated") as raised:
        _ = _decode_buildings(data)

    assert raised.value.player_index == 0
    assert raised.value.field.endswith("free_count[267].value")
