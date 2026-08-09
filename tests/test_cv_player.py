"""Tests for CvPlayer decoding with nested city and unit free lists."""

from pathlib import Path

import pytest

from savefile_reverse_engineer import (
    Civ5SaveDecoder,
    CvPlayerDecodeError,
)
from savefile_reverse_engineer._firaxis_hash import firaxis_hash
from savefile_reverse_engineer.cv_player import (
    _read_city_buildings,  # pyright: ignore[reportPrivateUsage]
    iterate_players_from_payload_impl,
)
from savefile_reverse_engineer.raw import (
    CvCityBuildings,
    decode_player_array_bytes,
)

_PROJECT_ROOT = Path(__file__).parent.parent
_SAVE_PATH = (
    _PROJECT_ROOT / "test-save-file/multi-player/AutoSave_Post_0076 AD-0040.Civ5Save"
)
_EARLY_SAVE_PATH = (
    _PROJECT_ROOT / "test-save-file/multi-player/AutoSave_Post_0027 BC-2380.Civ5Save"
)
_UNKNOWN_BUILDING_HASH = 0x12345678
_BUILDING_TYPE_COUNT = 268

_requires_save = pytest.mark.skipif(
    not _SAVE_PATH.is_file(), reason="the local Lekmod v34.11 save is unavailable"
)
_requires_early_save = pytest.mark.skipif(
    not _EARLY_SAVE_PATH.is_file(),
    reason="the early local Lekmod v34.11 save is unavailable",
)


@_requires_save
def test_decodes_participant_players_and_nested_objects() -> None:
    players = tuple(Civ5SaveDecoder(_SAVE_PATH).iter_players())

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
def test_decodes_semantic_city_fields_and_ownership() -> None:
    player = next(Civ5SaveDecoder(_SAVE_PATH).iter_players())
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
def test_decodes_city_building_inventory_and_production() -> None:
    cities = next(Civ5SaveDecoder(_SAVE_PATH).iter_players()).cities

    second_city_by_name = {
        entry.building_type.key: entry for entry in cities[1].buildings
    }
    capital_by_name = {entry.building_type.key: entry for entry in cities[0].buildings}

    assert len(cities[1].buildings) == _BUILDING_TYPE_COUNT - 4
    assert all(state.building_type.hash_value != 0 for state in cities[1].buildings)
    assert second_city_by_name["BUILDING_LIBRARY"].real_count == 1
    assert second_city_by_name["BUILDING_LIBRARY"].free_count == 0
    assert second_city_by_name["BUILDING_GRANARY"].real_count == 1
    assert capital_by_name["BUILDING_GREAT_LIGHTHOUSE"].production_x100 == 7081


@_requires_early_save
def test_writer_guided_city_probe_rejects_false_prefix_markers() -> None:
    cities = next(Civ5SaveDecoder(_EARLY_SAVE_PATH).iter_players()).cities

    assert [city.city_id for city in cities] == [8192, 16385]
    assert [(city.x, city.y) for city in cities] == [(11, 16), (16, 14)]
    assert all(len(city.buildings) == _BUILDING_TYPE_COUNT - 4 for city in cities)


@_requires_save
def test_decodes_unit_ids_coordinates_and_deleted_slots() -> None:
    player = next(Civ5SaveDecoder(_SAVE_PATH).iter_players())
    units = player.units

    assert units[0].unit_id == 57344
    assert units[0].unit_type_index == 1
    assert (units[0].x, units[0].y) == (12, 15)
    assert len(units) == 16
    assert {unit.owner_player_index for unit in units} == {0}


@_requires_save
def test_returns_fresh_nested_results() -> None:
    decoder = Civ5SaveDecoder(_SAVE_PATH)
    first = next(decoder.iter_players())
    repeated = next(decoder.iter_players())

    assert repeated == first
    assert repeated is not first
    assert repeated.cities[0] is not first.cities[0]


@_requires_save
def test_nested_errors_keep_absolute_player_context() -> None:
    source = Civ5SaveDecoder(_SAVE_PATH)
    payload = bytearray(source.payload_bytes)
    payload[0x44F557:0x44F55B] = (7).to_bytes(4, "little")

    teams = tuple(
        source._iter_raw_teams()  # pyright: ignore[reportPrivateUsage]
    )
    expected_totals = tuple((team.total_population, team.total_land) for team in teams)
    players = iterate_players_from_payload_impl(
        bytes(payload), byte_offset=0x42513D, expected_totals=expected_totals
    )
    with pytest.raises(CvPlayerDecodeError) as raised:
        _ = next(players)

    assert raised.value.player_index == 0
    assert raised.value.offset == 0x44F557
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


def _synthetic_city_prefix_to_buildings() -> bytes:
    city_prefix = _i32_values((6, 8192, 2, 3, -1, -1, 10, 10, 7, 7, 0, 0, 0, 250, 1))
    return b"".join(
        (
            city_prefix,
            _i32_values(tuple(0 for _ in range(44))),
            bytes(10),
            _i32_values((0, 0, 0, 0)),
            *(_int_vector(tuple(0 for _ in range(7))) for _ in range(18)),
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


def _synthetic_player_record(*, has_objects: bool) -> bytes:
    values = (16, 0, 0, *(0 for _ in range(14)))
    record = bytearray(
        b"".join(value.to_bytes(4, "little", signed=True) for value in values)
    )
    record.extend(_free_list_header(live=has_objects))
    if has_objects:
        record.extend(_synthetic_city_prefix_to_buildings())
        record.extend(_synthetic_city_buildings())
    record.extend(_free_list_header(live=has_objects))
    if has_objects:
        unit_values = (9, 0, 0, 1, 3, 4, 8192)
        record.extend(
            b"".join(value.to_bytes(4, "little", signed=True) for value in unit_values)
        )
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
    buildings = players[0].cities.entries[0].buildings
    entries_by_hash = {entry.building.hash_value: entry for entry in buildings.entries}

    assert len(players) == 64
    assert players[0].cities.entries[0].population == 7
    assert len(buildings.entries) == _BUILDING_TYPE_COUNT
    assert entries_by_hash[firaxis_hash("BUILDING_GRANARY")].real_count == 1
    assert entries_by_hash[firaxis_hash("BUILDING_LIBRARY")].free_count == 1
    assert entries_by_hash[_UNKNOWN_BUILDING_HASH].building.name is None
    assert entries_by_hash[_UNKNOWN_BUILDING_HASH].production_times_100 == 1234
    zero_entry = entries_by_hash[0]
    assert zero_entry.production_times_100 is None
    assert zero_entry.real_count is None
    assert players[0].units.entries[0].unit_id == 8192
    assert players[1].cities.entries == ()


def test_bytes_only_decoder_rejects_trailing_data(
    synthetic_player_array: bytes,
) -> None:
    with pytest.raises(CvPlayerDecodeError, match="no complete 64-player path"):
        _ = tuple(decode_player_array_bytes(synthetic_player_array + b"extra"))


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
    return _read_city_buildings(
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
