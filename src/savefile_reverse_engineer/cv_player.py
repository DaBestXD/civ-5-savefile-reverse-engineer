"""Decode Lekmod v34.11 CvPlayer records and their object free lists."""

from bisect import bisect_left, bisect_right
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from functools import cache
from typing import NoReturn, override

from ._binary_reader import LittleEndianReader
from ._cv_building_hashes import BUILDING_HASH_NAMES
from ._free_list import (
    FREE_LIST_INDEX_MASK,
    read_free_list_header,
)
from .cv_city_types import CityBuildingState, CvCity, CvCityBuildings
from .cv_player_types import CvPlayer, SerializedFreeList
from .cv_plot_types import HashedType
from .cv_unit_types import CvUnit

_PLAYER_COUNT = 64
_PLAYER_VERSION = 16
_CITY_VERSION = 6
_CITY_BUILDINGS_VERSION = 1
_UNIT_VERSION = 9
_CITY_BUILDING_TYPE_COUNT = 268
_CITY_YIELD_COUNT = 7
_CITY_DOMAIN_COUNT = 5
_CITY_PLAYER_COUNT = 80
_CITY_RESOURCE_COUNT = 57
_CITY_SPECIALIST_COUNT = 7
_CITY_PROJECT_COUNT = 6
_CITY_SCALARS_AFTER_PREFIX = 44
_CITY_FLAGS_AFTER_SCALARS = 10
_CITY_OWNER_FIELDS = 4
_CITY_YIELD_VECTORS = 18
_CITY_DOMAIN_VECTORS = 2
_MINIMUM_PLAYER_LENGTH = 0x20000
_INVALID_PLOT_COORD = -0x7FFFFFFF
_FREE_LIST_SLOT_COUNTS = (8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192)


class CvPlayerDecodeError(ValueError):
    """Malformed or unsupported value in a serialized CvPlayer array."""

    offset: int
    player_index: int
    field: str

    def __init__(
        self, message: str, *, offset: int, player_index: int, field: str
    ) -> None:
        self.offset = offset
        self.player_index = player_index
        self.field = field
        super().__init__(
            f"player {player_index} {field} at byte offset 0x{offset:X}: {message}"
        )


class _Reader(LittleEndianReader):
    __slots__: tuple[str, ...] = ("player_index",)
    _bounds_error_suffix: str = "player-array bytes"
    player_index: int
    offset: int

    def __init__(self, data: bytes, offset: int, player_index: int) -> None:
        super().__init__(data)
        self.offset = offset
        self.player_index = player_index

    @override
    def fail(
        self,
        message: str,
        *,
        offset: int | None = None,
        field: str | None = None,
    ) -> NoReturn:
        raise CvPlayerDecodeError(
            message,
            offset=self.offset if offset is None else offset,
            player_index=self.player_index,
            field="player" if field is None else field,
        )


@dataclass(slots=True)
class _HeaderCandidate:
    offset: int
    byte_length: int


@dataclass(slots=True)
class _CityCandidate:
    offset: int
    buildings_offset: int


@dataclass(slots=True)
class _HashedIntEntry:
    hash_value: int
    value: int | None
    hash_offset: int


def _i32(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little", signed=True)


def _try_free_list_header(
    data: bytes, offset: int, limit: int
) -> _HeaderCandidate | None:
    if offset + 24 > limit:
        return None
    slot_count = _i32(data, offset)
    if slot_count not in _FREE_LIST_SLOT_COUNTS:
        return None
    last_index = _i32(data, offset + 4)
    free_list_head = _i32(data, offset + 8)
    free_count = _i32(data, offset + 12)
    current_id = _i32(data, offset + 16)
    end = offset + 24 + slot_count * 4
    if end > limit:
        return None
    if last_index < -1 or last_index >= slot_count:
        return None
    if free_list_head < -1 or free_list_head > last_index:
        return None
    if free_count < 0 or free_count > last_index + 1:
        return None
    if current_id < 0 or current_id & FREE_LIST_INDEX_MASK:
        return None
    live_count = _i32(data, end - 4)
    if live_count < 0 or live_count + free_count != last_index + 1:
        return None
    next_free_indices = tuple(
        _i32(data, offset + 20 + index * 4) for index in range(slot_count)
    )
    free_slots: set[int] = set()
    next_slot = free_list_head
    while next_slot != -1:
        if next_slot < 0 or next_slot > last_index or next_slot in free_slots:
            return None
        free_slots.add(next_slot)
        next_slot = next_free_indices[next_slot]
    if len(free_slots) != free_count:
        return None
    return _HeaderCandidate(
        offset=offset,
        byte_length=24 + slot_count * 4,
    )


def _find_free_list_headers(
    data: bytes, start: int, limit: int
) -> tuple[_HeaderCandidate, ...]:
    candidates: dict[int, _HeaderCandidate] = {}
    for slot_count in _FREE_LIST_SLOT_COUNTS:
        marker = slot_count.to_bytes(4, "little", signed=True)
        offset = start
        while True:
            offset = data.find(marker, offset, limit)
            if offset < 0:
                break
            candidate = _try_free_list_header(data, offset, limit)
            if candidate is not None:
                candidates[offset] = candidate
            offset += 1
    return tuple(candidates[offset] for offset in sorted(candidates))


def _has_plausible_player_prefix(data: bytes, offset: int, limit: int) -> bool:
    if offset + 68 > limit or _i32(data, offset) != _PLAYER_VERSION:
        return False
    starting_x = _i32(data, offset + 4)
    starting_y = _i32(data, offset + 8)
    coordinates_are_valid = (
        starting_x == _INVALID_PLOT_COORD and starting_y == _INVALID_PLOT_COORD
    ) or (0 <= starting_x < 512 and 0 <= starting_y < 512)
    population = _i32(data, offset + 12)
    land = _i32(data, offset + 16)
    return (
        coordinates_are_valid and 0 <= population < 1_000_000 and 0 <= land < 1_000_000
    )


def _locate_player_records(
    data: bytes,
    byte_offset: int,
    expected_totals: Sequence[tuple[int, int]] | None = None,
    *,
    require_exact_end: bool = False,
) -> tuple[tuple[int, int, tuple[_HeaderCandidate, ...]], ...]:
    if expected_totals is not None and len(expected_totals) != _PLAYER_COUNT:
        raise ValueError("expected_totals must contain exactly 64 entries")
    headers = _find_free_list_headers(data, byte_offset, len(data))
    if expected_totals is None:
        starts = list(
            _find_player_starts_by_structure(
                data,
                byte_offset=byte_offset,
                headers=headers,
                require_exact_end=require_exact_end,
            )
        )
    else:
        starts = [byte_offset]
        version_marker = _PLAYER_VERSION.to_bytes(4, "little")
        for player_index in range(1, _PLAYER_COUNT):
            search_offset = starts[-1] + _MINIMUM_PLAYER_LENGTH
            while True:
                candidate = data.find(version_marker, search_offset)
                if candidate < 0:
                    raise CvPlayerDecodeError(
                        "the next CvPlayer version-16 prefix was not found",
                        offset=search_offset,
                        player_index=len(starts),
                        field="version",
                    )
                record_headers = tuple(
                    header
                    for header in headers
                    if starts[-1] < header.offset < candidate
                )
                if (
                    len(record_headers) == 3
                    and _has_plausible_player_prefix(data, candidate, len(data))
                    and (
                        _i32(data, candidate + 12),
                        _i32(data, candidate + 16),
                    )
                    == expected_totals[player_index]
                ):
                    starts.append(candidate)
                    break
                search_offset = candidate + 1

    records: list[tuple[int, int, tuple[_HeaderCandidate, ...]]] = []
    for index, start in enumerate(starts[:-1]):
        end = starts[index + 1]
        record_headers = tuple(
            header for header in headers if start < header.offset < end
        )
        if len(record_headers) != 3:
            raise CvPlayerDecodeError(
                f"found {len(record_headers)} object free lists, expected 3",
                offset=start,
                player_index=index,
                field="free_lists",
            )
        records.append((start, end, record_headers))

    previous_start, previous_end, previous_headers = records[-1]
    last_start = starts[-1]
    last_headers = tuple(header for header in headers if header.offset > last_start)
    if len(last_headers) < 3:
        raise CvPlayerDecodeError(
            f"found {len(last_headers)} object free lists, expected at least 3",
            offset=last_start,
            player_index=_PLAYER_COUNT - 1,
            field="free_lists",
        )
    last_three = last_headers[:3]
    previous_tail_length = previous_end - (
        previous_headers[2].offset + previous_headers[2].byte_length
    )
    last_end = last_three[2].offset + last_three[2].byte_length + previous_tail_length
    if last_end > len(data):
        raise CvPlayerDecodeError(
            "the final player tail extends beyond the supplied bytes",
            offset=last_three[2].offset,
            player_index=_PLAYER_COUNT - 1,
            field="byte_length",
        )
    if previous_end - previous_start < _MINIMUM_PLAYER_LENGTH:
        raise CvPlayerDecodeError(
            "the preceding player record is too short to bound the final player",
            offset=previous_start,
            player_index=_PLAYER_COUNT - 2,
            field="byte_length",
        )
    records.append((last_start, last_end, last_three))
    return tuple(records)


def _find_player_starts_by_structure(
    data: bytes,
    *,
    byte_offset: int,
    headers: tuple[_HeaderCandidate, ...],
    require_exact_end: bool,
) -> tuple[int, ...]:
    """Find the one 64-record path whose records each contain three free lists."""
    header_offsets = tuple(header.offset for header in headers)
    candidates = [byte_offset]
    marker = _PLAYER_VERSION.to_bytes(4, "little")
    search_offset = byte_offset + _MINIMUM_PLAYER_LENGTH
    while True:
        candidate = data.find(marker, search_offset)
        if candidate < 0:
            break
        if _has_plausible_player_prefix(data, candidate, len(data)):
            candidates.append(candidate)
        search_offset = candidate + 1
    candidate_offsets = tuple(candidates)

    def header_count(start: int, end: int) -> int:
        return bisect_left(header_offsets, end) - bisect_right(header_offsets, start)

    @cache
    def find_path(
        previous: int, current: int, players_remaining: int
    ) -> tuple[int, ...] | None:
        if players_remaining == 1:
            final_header_index = bisect_right(header_offsets, current)
            if final_header_index + 2 >= len(headers):
                return None
            previous_header_index = bisect_right(header_offsets, previous)
            if previous_header_index + 2 >= len(headers):
                return None
            previous_third = headers[previous_header_index + 2]
            final_third = headers[final_header_index + 2]
            previous_tail_length = current - (
                previous_third.offset + previous_third.byte_length
            )
            final_end = (
                final_third.offset + final_third.byte_length + previous_tail_length
            )
            if final_end > len(data) or (require_exact_end and final_end != len(data)):
                return None
            return (current,)

        minimum_next = current + _MINIMUM_PLAYER_LENGTH
        first_candidate = bisect_left(candidate_offsets, minimum_next)
        for next_start in candidate_offsets[first_candidate:]:
            free_list_count = header_count(current, next_start)
            if free_list_count < 3:
                continue
            if free_list_count > 3:
                break
            suffix = find_path(current, next_start, players_remaining - 1)
            if suffix is not None:
                return (current, *suffix)
        return None

    path = find_path(byte_offset, byte_offset, _PLAYER_COUNT)
    if path is None:
        raise CvPlayerDecodeError(
            "no complete 64-player path with three object free lists per record was found",
            offset=byte_offset,
            player_index=0,
            field="player_array",
        )
    return path


def _skip_exact_int_vector(reader: _Reader, *, count: int, field: str) -> None:
    count_offset = reader.offset
    saved_count = reader.u32(f"{field}.count")
    if saved_count != count:
        reader.fail(
            f"saved count is {saved_count}, expected {count}",
            offset=count_offset,
            field=f"{field}.count",
        )
    _ = reader.read_bytes(count * 4, f"{field}.values")


def _skip_exact_bool_vector(reader: _Reader, *, count: int, field: str) -> None:
    count_offset = reader.offset
    saved_count = reader.u32(f"{field}.count")
    if saved_count != count:
        reader.fail(
            f"saved count is {saved_count}, expected {count}",
            offset=count_offset,
            field=f"{field}.count",
        )
    for index in range(count):
        _ = reader.read_bool(f"{field}[{index}]")


def _skip_exact_hashed_int_array(reader: _Reader, *, count: int, field: str) -> None:
    count_offset = reader.offset
    saved_count = reader.u32(f"{field}.count")
    if saved_count != count:
        reader.fail(
            f"saved count is {saved_count}, expected {count}",
            offset=count_offset,
            field=f"{field}.count",
        )
    for index in range(count):
        hash_value = reader.u32(f"{field}[{index}].type")
        if hash_value != 0:
            _ = reader.i32(f"{field}[{index}].value")


def _try_locate_city_buildings(
    data: bytes,
    *,
    start: int,
    end: int,
    player_index: int,
) -> int | None:
    reader = _Reader(data, start, player_index)
    try:
        _ = reader.read_bytes(15 * 4, "cities.probe.confirmed_prefix")
        _ = reader.read_bytes(
            _CITY_SCALARS_AFTER_PREFIX * 4,
            "cities.probe.trailing_scalars",
        )
        for index in range(_CITY_FLAGS_AFTER_SCALARS):
            _ = reader.read_bool(f"cities.probe.flags[{index}]")
        _ = reader.read_bytes(
            _CITY_OWNER_FIELDS * 4,
            "cities.probe.owner_fields",
        )
        for index in range(_CITY_YIELD_VECTORS):
            _skip_exact_int_vector(
                reader,
                count=_CITY_YIELD_COUNT,
                field=f"cities.probe.yield_vectors[{index}]",
            )
        for index in range(_CITY_DOMAIN_VECTORS):
            _skip_exact_int_vector(
                reader,
                count=_CITY_DOMAIN_COUNT,
                field=f"cities.probe.domain_vectors[{index}]",
            )
        for index in range(2):
            _skip_exact_bool_vector(
                reader,
                count=_CITY_PLAYER_COUNT,
                field=f"cities.probe.player_flags[{index}]",
            )
        _ = reader.read_bool("cities.probe.finished_order_this_turn")
        _ = reader.i32("cities.probe.settler_unit_type")
        _ = reader.read_utf8("cities.probe.name")
        _ = reader.read_utf8("cities.probe.script_data")
        for index in range(3):
            _skip_exact_hashed_int_array(
                reader,
                count=_CITY_RESOURCE_COUNT,
                field=f"cities.probe.resource_arrays[{index}]",
            )
        _skip_exact_int_vector(
            reader,
            count=_CITY_SPECIALIST_COUNT,
            field="cities.probe.specialist_production",
        )
        _skip_exact_int_vector(
            reader,
            count=_CITY_PROJECT_COUNT,
            field="cities.probe.project_production",
        )
    except CvPlayerDecodeError:
        return None
    if reader.offset > end:
        return None
    return reader.offset


def _find_city_candidates(
    data: bytes,
    *,
    start: int,
    end: int,
    live_slots: Sequence[int],
    player_index: int,
) -> tuple[_CityCandidate, ...]:
    if live_slots and (start + 4 > end or _i32(data, start) != _CITY_VERSION):
        raise CvPlayerDecodeError(
            f"unsupported version {_i32(data, start)}; expected {_CITY_VERSION}",
            offset=start,
            player_index=player_index,
            field="cities.entries[0].version",
        )
    live_slot_set = set(live_slots)
    candidates_by_slot: dict[int, list[_CityCandidate]] = {
        slot_index: [] for slot_index in live_slots
    }
    marker = _CITY_VERSION.to_bytes(4, "little")
    candidate_offset = start
    while True:
        candidate_offset = data.find(marker, candidate_offset, end)
        if candidate_offset < 0:
            break
        if candidate_offset + 60 <= end:
            city_id = _i32(data, candidate_offset + 4)
            slot_index = city_id & FREE_LIST_INDEX_MASK
            has_valid_prefix = (
                city_id >= 0
                and slot_index in live_slot_set
                and 0 <= _i32(data, candidate_offset + 8) < 512
                and 0 <= _i32(data, candidate_offset + 12) < 512
                and _i32(data, candidate_offset + 32) >= 0
            )
            if has_valid_prefix:
                buildings_offset = _try_locate_city_buildings(
                    data,
                    start=candidate_offset,
                    end=end,
                    player_index=player_index,
                )
                if buildings_offset is not None:
                    candidates_by_slot[slot_index].append(
                        _CityCandidate(
                            offset=candidate_offset,
                            buildings_offset=buildings_offset,
                        )
                    )
        candidate_offset += 1

    selected: list[_CityCandidate] = []
    for record_index, slot_index in enumerate(live_slots):
        matches = candidates_by_slot[slot_index]
        if len(matches) != 1:
            raise CvPlayerDecodeError(
                f"found {len(matches)} source-shaped records for live slot {slot_index}, expected 1",
                offset=start,
                player_index=player_index,
                field=f"cities.entries[{record_index}]",
            )
        candidate = matches[0]
        if selected and candidate.offset <= selected[-1].offset:
            raise CvPlayerDecodeError(
                "source-shaped city records are not in live-slot order",
                offset=candidate.offset,
                player_index=player_index,
                field=f"cities.entries[{record_index}]",
            )
        selected.append(candidate)
    return tuple(selected)


def _find_unit_starts(
    data: bytes,
    *,
    start: int,
    end: int,
    live_slots: Sequence[int],
    player_index: int,
) -> tuple[int, ...]:
    if live_slots and _i32(data, start) != _UNIT_VERSION:
        raise CvPlayerDecodeError(
            f"unsupported version {_i32(data, start)}; expected {_UNIT_VERSION}",
            offset=start,
            player_index=player_index,
            field="units.entries[0].version",
        )
    starts: list[int] = []
    cursor = start
    marker = _UNIT_VERSION.to_bytes(4, "little")
    for record_index, slot_index in enumerate(live_slots):
        while True:
            candidate = data.find(marker, cursor, end)
            if candidate < 0 or candidate + 28 > end:
                raise CvPlayerDecodeError(
                    f"record {record_index} for live slot {slot_index} was not found",
                    offset=cursor,
                    player_index=player_index,
                    field="units",
                )
            unit_id = _i32(data, candidate + 24)
            has_expected_slot = (
                unit_id >= 0 and unit_id & FREE_LIST_INDEX_MASK == slot_index
            )
            has_valid_prefix = (
                0 <= _i32(data, candidate + 16) < 512
                and 0 <= _i32(data, candidate + 20) < 512
            )
            if has_expected_slot and has_valid_prefix:
                starts.append(candidate)
                cursor = candidate + 8
                break
            cursor = candidate + 1
    return tuple(starts)


def _read_building_array(reader: _Reader, *, field: str) -> tuple[_HashedIntEntry, ...]:
    count_offset = reader.offset
    count = reader.i32(f"{field}.count")
    if count != _CITY_BUILDING_TYPE_COUNT:
        reader.fail(
            f"saved count is {count}, expected {_CITY_BUILDING_TYPE_COUNT}",
            offset=count_offset,
            field=f"{field}.count",
        )
    entries: list[_HashedIntEntry] = []
    for index in range(count):
        hash_offset = reader.offset
        hash_value = reader.u32(f"{field}[{index}].type")
        value = None if hash_value == 0 else reader.i32(f"{field}[{index}].value")
        entries.append(
            _HashedIntEntry(
                hash_value=hash_value,
                value=value,
                hash_offset=hash_offset,
            )
        )
    return tuple(entries)


def _read_city_buildings(
    data: bytes,
    *,
    start: int,
    end: int,
    record_index: int,
    player_index: int,
) -> CvCityBuildings:
    reader = _Reader(data, start, player_index)
    field = f"cities.entries[{record_index}].buildings"
    version = reader.u32(f"{field}.version")
    if version != _CITY_BUILDINGS_VERSION:
        reader.fail(
            f"unsupported CvCityBuildings version {version}; expected {_CITY_BUILDINGS_VERSION}",
            offset=start,
            field=f"{field}.version",
        )
    num_buildings = reader.i32(f"{field}.num_buildings")
    production_modifier = reader.i32(f"{field}.production_modifier")
    defense = reader.i32(f"{field}.defense")
    garrison_strength_bonus = reader.i32(f"{field}.garrison_strength_bonus")
    defense_per_citizen = reader.i32(f"{field}.defense_per_citizen")
    defense_modifier = reader.i32(f"{field}.defense_modifier")
    missionary_extra_spreads = reader.i32(f"{field}.missionary_extra_spreads")
    landmarks_tourism_percent = reader.i32(f"{field}.landmarks_tourism_percent")
    great_works_tourism_modifier = reader.i32(f"{field}.great_works_tourism_modifier")
    sold_building_this_turn = reader.read_bool(f"{field}.sold_building_this_turn")
    arrays = tuple(
        _read_building_array(reader, field=f"{field}.{array_name}")
        for array_name in (
            "production",
            "production_turns",
            "original_owner",
            "original_year",
            "real_count",
            "free_count",
        )
    )
    expected_hashes = tuple(entry.hash_value for entry in arrays[0])
    for array_index, entries in enumerate(arrays[1:], start=1):
        for entry_index, entry in enumerate(entries):
            if entry.hash_value != expected_hashes[entry_index]:
                reader.fail(
                    "building hash does not match the first inventory array",
                    offset=entry.hash_offset,
                    field=(f"{field}.arrays[{array_index}][{entry_index}].type"),
                )
    if reader.offset > end:
        reader.fail(
            "building inventory extends beyond the city record",
            offset=end,
            field=field,
        )
    entries = tuple(
        CityBuildingState(
            building=HashedType(
                hash_value=expected_hashes[index],
                name=BUILDING_HASH_NAMES.get(expected_hashes[index]),
            ),
            production_times_100=arrays[0][index].value,
            production_turns=arrays[1][index].value,
            original_owner=arrays[2][index].value,
            original_year=arrays[3][index].value,
            real_count=arrays[4][index].value,
            free_count=arrays[5][index].value,
        )
        for index in range(_CITY_BUILDING_TYPE_COUNT)
    )
    return CvCityBuildings(
        byte_offset=start,
        inventory_byte_length=reader.offset - start,
        version=version,
        num_buildings=num_buildings,
        production_modifier=production_modifier,
        defense=defense,
        garrison_strength_bonus=garrison_strength_bonus,
        defense_per_citizen=defense_per_citizen,
        defense_modifier=defense_modifier,
        missionary_extra_spreads=missionary_extra_spreads,
        landmarks_tourism_percent=landmarks_tourism_percent,
        great_works_tourism_modifier=great_works_tourism_modifier,
        sold_building_this_turn=sold_building_this_turn,
        entries=entries,
    )


def _read_city(
    data: bytes,
    *,
    start: int,
    buildings_offset: int,
    end: int,
    record_index: int,
    slot_index: int,
    player_index: int,
) -> CvCity:
    reader = _Reader(data, start, player_index)
    field = f"cities.entries[{record_index}]"
    version = reader.u32(f"{field}.version")
    if version != _CITY_VERSION:
        reader.fail(
            f"unsupported CvCity version {version}; expected {_CITY_VERSION}",
            offset=start,
            field=f"{field}.version",
        )
    city_id = reader.i32(f"{field}.city_id")
    if city_id & FREE_LIST_INDEX_MASK != slot_index:
        reader.fail(
            f"city ID {city_id} does not name free-list slot {slot_index}",
            field=f"{field}.city_id",
        )
    buildings = _read_city_buildings(
        data,
        start=buildings_offset,
        end=end,
        record_index=record_index,
        player_index=player_index,
    )
    return CvCity(
        record_index=record_index,
        slot_index=slot_index,
        byte_offset=start,
        byte_length=end - start,
        version=version,
        city_id=city_id,
        x=reader.i32(f"{field}.x"),
        y=reader.i32(f"{field}.y"),
        rally_x=reader.i32(f"{field}.rally_x"),
        rally_y=reader.i32(f"{field}.rally_y"),
        game_turn_founded=reader.i32(f"{field}.game_turn_founded"),
        game_turn_acquired=reader.i32(f"{field}.game_turn_acquired"),
        population=reader.i32(f"{field}.population"),
        highest_population=reader.i32(f"{field}.highest_population"),
        great_people_created=reader.i32(f"{field}.great_people_created"),
        base_great_people_rate=reader.i32(f"{field}.base_great_people_rate"),
        great_people_rate_modifier=reader.i32(f"{field}.great_people_rate_modifier"),
        culture_stored_times_100=reader.i32(f"{field}.culture_stored_times_100"),
        culture_level=reader.i32(f"{field}.culture_level"),
        buildings=buildings,
    )


def _read_unit(
    data: bytes,
    *,
    start: int,
    end: int,
    record_index: int,
    slot_index: int,
    player_index: int,
) -> CvUnit:
    reader = _Reader(data, start, player_index)
    field = f"units.entries[{record_index}]"
    version = reader.u32(f"{field}.version")
    if version != _UNIT_VERSION:
        reader.fail(
            f"unsupported CvUnit version {version}; expected {_UNIT_VERSION}",
            offset=start,
            field=f"{field}.version",
        )
    _ = reader.i32(f"{field}.archive_prefix_1")
    _ = reader.i32(f"{field}.archive_prefix_2")
    unit_type_index = reader.i32(f"{field}.unit_type_index")
    x = reader.i32(f"{field}.x")
    y = reader.i32(f"{field}.y")
    unit_id = reader.i32(f"{field}.unit_id")
    if unit_id & FREE_LIST_INDEX_MASK != slot_index:
        reader.fail(
            f"unit ID {unit_id} does not name free-list slot {slot_index}",
            field=f"{field}.unit_id",
        )
    return CvUnit(
        record_index=record_index,
        slot_index=slot_index,
        byte_offset=start,
        byte_length=end - start,
        version=version,
        unit_id=unit_id,
        unit_type_index=unit_type_index,
        x=x,
        y=y,
    )


def _read_player(
    data: bytes,
    *,
    player_index: int,
    start: int,
    end: int,
    headers: tuple[_HeaderCandidate, ...],
) -> CvPlayer:
    reader = _Reader(data, start, player_index)
    version = reader.u32("version")
    if version != _PLAYER_VERSION:
        reader.fail(
            f"unsupported CvPlayer version {version}; expected {_PLAYER_VERSION}",
            offset=start,
            field="version",
        )
    prefix_values = tuple(reader.i32(f"prefix[{index}]") for index in range(16))

    city_reader = _Reader(data, headers[0].offset, player_index)
    city_header = read_free_list_header(city_reader, "cities")
    unit_reader = _Reader(data, headers[1].offset, player_index)
    unit_header = read_free_list_header(unit_reader, "units")

    city_candidates = _find_city_candidates(
        data,
        start=city_reader.offset,
        end=headers[1].offset,
        live_slots=city_header.live_slots,
        player_index=player_index,
    )
    cities = tuple(
        _read_city(
            data,
            start=city_candidate.offset,
            buildings_offset=city_candidate.buildings_offset,
            end=(
                city_candidates[index + 1].offset
                if index + 1 < len(city_candidates)
                else headers[1].offset
            ),
            record_index=index,
            slot_index=city_header.live_slots[index],
            player_index=player_index,
        )
        for index, city_candidate in enumerate(city_candidates)
    )

    unit_starts = _find_unit_starts(
        data,
        start=unit_reader.offset,
        end=headers[2].offset,
        live_slots=unit_header.live_slots,
        player_index=player_index,
    )
    units = tuple(
        _read_unit(
            data,
            start=unit_start,
            end=(
                unit_starts[index + 1]
                if index + 1 < len(unit_starts)
                else headers[2].offset
            ),
            record_index=index,
            slot_index=unit_header.live_slots[index],
            player_index=player_index,
        )
        for index, unit_start in enumerate(unit_starts)
    )
    return CvPlayer(
        player_index=player_index,
        byte_offset=start,
        byte_length=end - start,
        version=version,
        starting_x=prefix_values[0],
        starting_y=prefix_values[1],
        total_population=prefix_values[2],
        total_land=prefix_values[3],
        total_land_scored=prefix_values[4],
        culture_per_turn_for_free=prefix_values[5],
        culture_per_turn_from_minor_civs=prefix_values[6],
        culture_city_modifier=prefix_values[7],
        culture_times_100=prefix_values[8],
        culture_ever_generated_times_100=prefix_values[9],
        culture_per_wonder=prefix_values[10],
        culture_wonder_multiplier=prefix_values[11],
        culture_per_technology_researched=prefix_values[12],
        faith=prefix_values[13],
        faith_ever_generated=prefix_values[14],
        happiness=prefix_values[15],
        cities=SerializedFreeList(
            byte_offset=city_header.byte_offset,
            byte_length=headers[1].offset - city_header.byte_offset,
            slot_count=city_header.slot_count,
            last_index=city_header.last_index,
            free_list_head=city_header.free_list_head,
            free_count=city_header.free_count,
            current_id=city_header.current_id,
            next_free_indices=city_header.next_free_indices,
            entries=cities,
        ),
        units=SerializedFreeList(
            byte_offset=unit_header.byte_offset,
            byte_length=headers[2].offset - unit_header.byte_offset,
            slot_count=unit_header.slot_count,
            last_index=unit_header.last_index,
            free_list_head=unit_header.free_list_head,
            free_count=unit_header.free_count,
            current_id=unit_header.current_id,
            next_free_indices=unit_header.next_free_indices,
            entries=units,
        ),
    )


def iterate_players_from_payload_impl(
    payload: bytes,
    *,
    byte_offset: int,
    expected_totals: Sequence[tuple[int, int]] | None = None,
) -> Iterator[CvPlayer]:
    """Yield the 64 CvPlayer records at a known payload offset."""
    records = _locate_player_records(payload, byte_offset, expected_totals)
    for player_index, (start, end, headers) in enumerate(records):
        yield _read_player(
            payload,
            player_index=player_index,
            start=start,
            end=end,
            headers=headers,
        )


def decode_player_array_bytes_impl(
    player_array_bytes: bytes,
) -> Iterator[CvPlayer]:
    """Return a lazy iterator over an exact 64-player byte sequence."""
    if not player_array_bytes:
        raise CvPlayerDecodeError(
            "the CvPlayer array is empty",
            offset=0,
            player_index=0,
            field="player_array",
        )
    records = _locate_player_records(player_array_bytes, 0, require_exact_end=True)
    return (
        _read_player(
            player_array_bytes,
            player_index=player_index,
            start=start,
            end=end,
            headers=headers,
        )
        for player_index, (start, end, headers) in enumerate(records)
    )


__all__: tuple[str, ...] = ()
