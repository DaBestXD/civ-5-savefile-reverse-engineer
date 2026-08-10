"""Decode Lekmod v34.11 CvPlayer records and their object free lists."""

from bisect import bisect_left, bisect_right
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from functools import cache
from typing import NoReturn, override

from ._binary_reader import LittleEndianReader
from ._cv_building_hashes import BUILDING_HASH_NAMES
from ._cv_policy_hashes import POLICY_BRANCH_HASH_NAMES, POLICY_HASH_NAMES
from ._cv_production_hashes import PROJECT_HASH_NAMES
from ._cv_unit_hashes import UNIT_HASH_NAMES
from ._free_list import (
    FREE_LIST_INDEX_MASK,
    read_free_list_header,
)
from .cv_city_types import (
    CityBuildingState,
    CvCity,
    CvCityBuildings,
    ProductionOrder,
    ProductionOrderType,
)
from .cv_player_types import (
    CvPlayer,
    CvPlayerPolicy,
    CvPlayerPolicyBranch,
    CvPlayerPolicyInformation,
    SerializedFreeList,
)
from .cv_plot_types import HashedType
from .cv_unit_types import CvUnit

_PLAYER_COUNT = 64
_PLAYER_VERSION = 16
_PLAYER_POLICIES_VERSION = 2
_POLICY_SLOT_COUNT = 138
_POLICY_BRANCH_COUNT = 12
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
_CITY_UNIT_TYPE_COUNT = 265
_CITY_IMPROVEMENT_COUNT = 46
_CITY_SCALARS_AFTER_PREFIX = 44
_CITY_FLAGS_AFTER_SCALARS = 10
_CITY_OWNER_FIELDS = 4
_CITY_YIELD_VECTORS = 18
_CITY_DOMAIN_VECTORS = 2
_MINIMUM_PLAYER_LENGTH = 0x20000
_INVALID_PLOT_COORD = -0x7FFFFFFF
_FREE_LIST_SLOT_COUNTS = (8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192)
_UNIT_ARCHIVE_WORDS_AFTER_PREFIX = 8
_UNIT_ARCHIVE_WORDS_AFTER_IMMOBILE = 10
_UNIT_ARCHIVE_WORDS_BEFORE_FLAGS = 93
_UNIT_ARCHIVE_FLAG_COUNT = 7
_UNIT_ARCHIVE_ENUM_WORDS = 6
_UNIT_ARCHIVE_FINAL_WORDS = 6
_UNIT_SELECTED_PROMOTION_COUNT = 340
_UNIT_YIELD_COUNT = 7
_UNIT_ERA_COUNT = 8
_UNIT_TERRAIN_COUNT = 9
_UNIT_FEATURE_COUNT = 25
_UNIT_COMBAT_COUNT = 18
_UNIT_CLASS_COUNT = 113
_CITY_PRODUCTION_QUEUE_CAPACITY = 25


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
    name_key: str


@dataclass(slots=True)
class _CityProbe:
    buildings_offset: int
    name_key: str


@dataclass(slots=True)
class _HashedIntEntry:
    hash_value: int
    value: int | None
    hash_offset: int


@dataclass(slots=True)
class _HashedBoolEntry:
    hash_value: int
    value: bool | None


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


def _read_exact_hashed_bool_array(
    reader: _Reader, *, count: int, field: str
) -> tuple[_HashedBoolEntry, ...]:
    count_offset = reader.offset
    saved_count = reader.u32(f"{field}.count")
    if saved_count != count:
        reader.fail(
            f"saved count is {saved_count}, expected {count}",
            offset=count_offset,
            field=f"{field}.count",
        )
    entries: list[_HashedBoolEntry] = []
    for index in range(count):
        item_field = f"{field}[{index}]"
        hash_value = reader.u32(f"{item_field}.type")
        value = None if hash_value == 0 else reader.read_bool(f"{item_field}.value")
        entries.append(_HashedBoolEntry(hash_value=hash_value, value=value))
    return tuple(entries)


def _try_read_policy_information(
    data: bytes,
    *,
    offset: int,
    limit: int,
    player_index: int,
) -> CvPlayerPolicyInformation | None:
    reader = _Reader(data, offset, player_index)
    try:
        version = reader.u32("policy_information.version")
        if version != _PLAYER_POLICIES_VERSION:
            return None
        policy_arrays = tuple(
            _read_exact_hashed_bool_array(
                reader,
                count=_POLICY_SLOT_COUNT,
                field=f"policy_information.policy_arrays[{array_index}]",
            )
            for array_index in range(3)
        )
        policy_hashes = tuple(entry.hash_value for entry in policy_arrays[0])
        if any(
            tuple(entry.hash_value for entry in entries) != policy_hashes
            for entries in policy_arrays[1:]
        ):
            return None

        branch_arrays = tuple(
            _read_exact_hashed_bool_array(
                reader,
                count=_POLICY_BRANCH_COUNT,
                field=f"policy_information.branch_arrays[{array_index}]",
            )
            for array_index in range(2)
        )
        branch_hashes = tuple(entry.hash_value for entry in branch_arrays[0])
        if (
            any(hash_value == 0 for hash_value in branch_hashes)
            or tuple(entry.hash_value for entry in branch_arrays[1])
            != branch_hashes
            or reader.offset > limit
        ):
            return None
    except CvPlayerDecodeError:
        return None

    policy_slots = tuple(
        CvPlayerPolicy(
            policy_type=HashedType(
                hash_value=entry.hash_value,
                name=POLICY_HASH_NAMES.get(entry.hash_value),
            ),
            owned=entry.value,
        )
        for entry in policy_arrays[0]
    )
    branches: list[CvPlayerPolicyBranch] = []
    for entry in branch_arrays[0]:
        if entry.value is None:
            return None
        branches.append(
            CvPlayerPolicyBranch(
                branch_type=HashedType(
                    hash_value=entry.hash_value,
                    name=POLICY_BRANCH_HASH_NAMES.get(entry.hash_value),
                ),
                unlocked=entry.value,
            )
        )
    return CvPlayerPolicyInformation(
        byte_offset=offset,
        version=version,
        policy_slots=policy_slots,
        branches=tuple(branches),
    )


def _locate_policy_information(
    data: bytes,
    *,
    start: int,
    end: int,
    player_index: int,
) -> CvPlayerPolicyInformation:
    marker = b"".join(
        (
            _PLAYER_POLICIES_VERSION.to_bytes(4, "little"),
            _POLICY_SLOT_COUNT.to_bytes(4, "little"),
        )
    )
    candidates: list[CvPlayerPolicyInformation] = []
    search_offset = start
    while True:
        candidate_offset = data.find(marker, search_offset, end)
        if candidate_offset < 0:
            break
        candidate = _try_read_policy_information(
            data,
            offset=candidate_offset,
            limit=end,
            player_index=player_index,
        )
        if candidate is not None:
            candidates.append(candidate)
        search_offset = candidate_offset + 1
    if len(candidates) != 1:
        reader = _Reader(data, start, player_index)
        reader.fail(
            f"found {len(candidates)} structurally valid policy blocks, expected 1",
            offset=start,
            field="policy_information",
        )
    return candidates[0]


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


def _skip_struct_vector(reader: _Reader, *, item_size: int, field: str) -> None:
    count = reader.u32(f"{field}.count")
    _ = reader.read_bytes(count * item_size, f"{field}.entries")


def _try_locate_city_buildings(
    data: bytes,
    *,
    start: int,
    end: int,
    player_index: int,
) -> _CityProbe | None:
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
        name_key = reader.read_utf8("cities.probe.name")
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
    return _CityProbe(buildings_offset=reader.offset, name_key=name_key)


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
                probe = _try_locate_city_buildings(
                    data,
                    start=candidate_offset,
                    end=end,
                    player_index=player_index,
                )
                if probe is not None:
                    candidates_by_slot[slot_index].append(
                        _CityCandidate(
                            offset=candidate_offset,
                            buildings_offset=probe.buildings_offset,
                            name_key=probe.name_key,
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
            has_valid_hash = False
            if has_expected_slot and has_valid_prefix:
                try:
                    probe = _Reader(data, candidate, player_index)
                    _ = probe.u32(f"units.entries[{record_index}].version")
                    for prefix_index in range(6):
                        _ = probe.i32(
                            f"units.entries[{record_index}].archive_prefix[{prefix_index}]"
                        )
                    unit_hash = _read_unit_hash(
                        probe,
                        end=end,
                        field=f"units.entries[{record_index}]",
                    )
                    has_valid_hash = unit_hash != 0
                except CvPlayerDecodeError:
                    has_valid_hash = False
            if has_expected_slot and has_valid_prefix and has_valid_hash:
                starts.append(candidate)
                cursor = candidate + 8
                break
            cursor = candidate + 1
    return tuple(starts)


def _ensure_unit_bytes_fit(reader: _Reader, *, end: int, size: int, field: str) -> None:
    if size > end - reader.offset:
        reader.fail(
            f"{field} extends beyond the CvUnit record",
            field=field,
        )


def _consume_unit_fixed_bytes(
    reader: _Reader, *, end: int, size: int, field: str
) -> None:
    _ensure_unit_bytes_fit(reader, end=end, size=size, field=field)
    _ = reader.read_bytes(size, field)


def _read_unit_bool(reader: _Reader, *, end: int, field: str) -> bool:
    if reader.offset >= end:
        reader.fail(
            f"{field} extends beyond the CvUnit record",
            field=field,
        )
    return reader.read_bool(field)


def _consume_unit_string(reader: _Reader, *, end: int, field: str) -> None:
    _ensure_unit_bytes_fit(reader, end=end, size=4, field=f"{field}.length")
    length = reader.u32(f"{field}.length")
    _consume_unit_fixed_bytes(reader, end=end, size=length, field=field)


def _consume_unit_vector(
    reader: _Reader,
    *,
    end: int,
    expected_count: int,
    item_size: int,
    field: str,
) -> None:
    count_offset = reader.offset
    _ensure_unit_bytes_fit(reader, end=end, size=4, field=f"{field}.count")
    count = reader.u32(f"{field}.count")
    if count != expected_count:
        reader.fail(
            f"saved count is {count}, expected {expected_count}",
            offset=count_offset,
            field=f"{field}.count",
        )
    _consume_unit_fixed_bytes(
        reader,
        end=end,
        size=count * item_size,
        field=field,
    )
    raw_values = reader.data[reader.offset - count * item_size : reader.offset]
    if item_size == 1:
        invalid_value = next(
            (value for value in raw_values if value not in (0, 1)), None
        )
        if invalid_value is not None:
            reader.fail(
                f"{field} contains Boolean byte {invalid_value}, expected zero or one",
                offset=count_offset + 4,
                field=field,
            )


def _read_unit_hash(reader: _Reader, *, end: int, field: str) -> int:
    """Read the unit hash after the exact Lekmod v34.11 sync archive."""
    _consume_unit_fixed_bytes(
        reader,
        end=end,
        size=_UNIT_ARCHIVE_WORDS_AFTER_PREFIX * 4,
        field=f"{field}.archive.scalars_after_prefix",
    )
    _ = _read_unit_bool(reader, end=end, field=f"{field}.archive.immobile")
    _consume_unit_fixed_bytes(
        reader,
        end=end,
        size=_UNIT_ARCHIVE_WORDS_AFTER_IMMOBILE * 4,
        field=f"{field}.archive.scalars_after_immobile",
    )
    _ = _read_unit_bool(
        reader,
        end=end,
        field=f"{field}.archive.fortified_this_turn",
    )
    _consume_unit_fixed_bytes(
        reader,
        end=end,
        size=_UNIT_ARCHIVE_WORDS_BEFORE_FLAGS * 4,
        field=f"{field}.archive.scalars_before_flags",
    )
    for index in range(_UNIT_ARCHIVE_FLAG_COUNT):
        _ = _read_unit_bool(
            reader,
            end=end,
            field=f"{field}.archive.flags[{index}]",
        )
    _ensure_unit_bytes_fit(
        reader, end=end, size=4, field=f"{field}.archive.num_selected_promotions"
    )
    _ = reader.i32(f"{field}.archive.num_selected_promotions")
    _consume_unit_vector(
        reader,
        end=end,
        expected_count=_UNIT_SELECTED_PROMOTION_COUNT,
        item_size=1,
        field=f"{field}.archive.selected_promotions",
    )
    _ = _read_unit_bool(reader, end=end, field=f"{field}.archive.embarked")
    _ = _read_unit_bool(
        reader,
        end=end,
        field=f"{field}.archive.ai_turn_processed",
    )
    _consume_unit_fixed_bytes(
        reader,
        end=end,
        size=_UNIT_ARCHIVE_ENUM_WORDS * 4,
        field=f"{field}.archive.enums",
    )
    _consume_unit_string(reader, end=end, field=f"{field}.archive.legacy_name")
    _consume_unit_string(reader, end=end, field=f"{field}.archive.script_data")
    for name in ("yield_from_kills", "kill_yield_cap"):
        _consume_unit_vector(
            reader,
            end=end,
            expected_count=_UNIT_YIELD_COUNT,
            item_size=4,
            field=f"{field}.archive.{name}",
        )
    _consume_unit_vector(
        reader,
        end=end,
        expected_count=_UNIT_ERA_COUNT,
        item_size=1,
        field=f"{field}.archive.kill_yield_era_valid",
    )
    for name, count in (
        ("terrain_double_move", _UNIT_TERRAIN_COUNT),
        ("feature_double_move", _UNIT_FEATURE_COUNT),
        ("terrain_impassable", _UNIT_TERRAIN_COUNT),
        ("feature_impassable", _UNIT_FEATURE_COUNT),
        ("extra_terrain_attack", _UNIT_TERRAIN_COUNT),
        ("extra_terrain_defense", _UNIT_TERRAIN_COUNT),
        ("extra_feature_attack", _UNIT_FEATURE_COUNT),
        ("extra_feature_defense", _UNIT_FEATURE_COUNT),
        ("extra_unit_combat_modifier", _UNIT_COMBAT_COUNT),
        ("unit_class_modifier", _UNIT_CLASS_COUNT),
    ):
        _consume_unit_vector(
            reader,
            end=end,
            expected_count=count,
            item_size=4,
            field=f"{field}.archive.{name}",
        )
    _consume_unit_fixed_bytes(
        reader,
        end=end,
        size=_UNIT_ARCHIVE_FINAL_WORDS * 4,
        field=f"{field}.archive.final_fields",
    )
    if 4 > end - reader.offset:
        reader.fail(
            "serialized unit hash extends beyond the CvUnit record",
            field=f"{field}.unit_hash",
        )
    return reader.u32(f"{field}.unit_hash")


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


def _production_item_name(
    order_type: ProductionOrderType, hash_value: int
) -> str | None:
    if order_type is ProductionOrderType.TRAIN_UNIT:
        return UNIT_HASH_NAMES.get(hash_value)
    if order_type is ProductionOrderType.CONSTRUCT_BUILDING:
        return BUILDING_HASH_NAMES.get(hash_value)
    if order_type is ProductionOrderType.CREATE_PROJECT:
        return PROJECT_HASH_NAMES.get(hash_value)
    return None


def _read_city_production_queue(
    data: bytes,
    *,
    start: int,
    end: int,
    record_index: int,
    player_index: int,
) -> tuple[ProductionOrder, ...]:
    reader = _Reader(data, start, player_index)
    field = f"cities.entries[{record_index}]"

    _skip_struct_vector(
        reader,
        item_size=3 * 4,
        field=f"{field}.buildings.yield_changes",
    )
    _skip_struct_vector(
        reader,
        item_size=3 * 4,
        field=f"{field}.buildings.great_works",
    )
    for array_name in ("unit_production", "unit_production_time"):
        _skip_exact_hashed_int_array(
            reader,
            count=_CITY_UNIT_TYPE_COUNT,
            field=f"{field}.{array_name}",
        )
    for vector_name, count in (
        ("specialist_count", _CITY_SPECIALIST_COUNT),
        ("maximum_specialist_count", _CITY_SPECIALIST_COUNT),
        ("forced_specialist_count", _CITY_SPECIALIST_COUNT),
        ("free_specialist_count", _CITY_SPECIALIST_COUNT),
        ("improvement_free_specialists", _CITY_IMPROVEMENT_COUNT),
        ("unit_combat_free_experience", _UNIT_COMBAT_COUNT),
        ("unit_combat_production_modifier", _UNIT_COMBAT_COUNT),
    ):
        _skip_exact_int_vector(
            reader,
            count=count,
            field=f"{field}.{vector_name}",
        )
    _skip_exact_hashed_int_array(
        reader,
        count=_UNIT_SELECTED_PROMOTION_COUNT,
        field=f"{field}.free_promotion_count",
    )

    count_offset = reader.offset
    count = reader.u32(f"{field}.production_queue.count")
    if count > _CITY_PRODUCTION_QUEUE_CAPACITY:
        reader.fail(
            (f"saved count is {count}, maximum is {_CITY_PRODUCTION_QUEUE_CAPACITY}"),
            offset=count_offset,
            field=f"{field}.production_queue.count",
        )
    orders: list[ProductionOrder] = []
    for queue_index in range(count):
        order_start = reader.offset
        order_field = f"{field}.production_queue[{queue_index}]"
        order_value = reader.i32(f"{order_field}.order_type")
        try:
            order_type = ProductionOrderType(order_value)
        except ValueError:
            reader.fail(
                f"unsupported production order type {order_value}",
                offset=order_start,
                field=f"{order_field}.order_type",
            )
        hash_value = reader.u32(f"{order_field}.item")
        secondary_data = reader.i32(f"{order_field}.secondary_data")
        save = reader.read_bool(f"{order_field}.save")
        rush = reader.read_bool(f"{order_field}.rush")
        orders.append(
            ProductionOrder(
                queue_index=queue_index,
                byte_offset=order_start,
                byte_length=reader.offset - order_start,
                order_type=order_type,
                item=HashedType(
                    hash_value=hash_value,
                    name=_production_item_name(order_type, hash_value),
                ),
                secondary_data=secondary_data,
                save=save,
                rush=rush,
            )
        )
    if reader.offset > end:
        reader.fail(
            "production queue extends beyond the city record",
            offset=end,
            field=f"{field}.production_queue",
        )
    return tuple(orders)


def _read_city(
    data: bytes,
    *,
    start: int,
    buildings_offset: int,
    end: int,
    record_index: int,
    slot_index: int,
    player_index: int,
    name_key: str,
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
    production_queue = _read_city_production_queue(
        data,
        start=buildings.byte_offset + buildings.inventory_byte_length,
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
        name_key=name_key,
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
        production_queue=production_queue,
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
    _ = reader.i32(f"{field}.archive_prefix_3")
    x = reader.i32(f"{field}.x")
    y = reader.i32(f"{field}.y")
    unit_id = reader.i32(f"{field}.unit_id")
    if unit_id & FREE_LIST_INDEX_MASK != slot_index:
        reader.fail(
            f"unit ID {unit_id} does not name free-list slot {slot_index}",
            field=f"{field}.unit_id",
        )
    unit_hash = _read_unit_hash(reader, end=end, field=field)
    return CvUnit(
        record_index=record_index,
        slot_index=slot_index,
        byte_offset=start,
        byte_length=end - start,
        version=version,
        unit_id=unit_id,
        unit_hash=unit_hash,
        unit_name=UNIT_HASH_NAMES.get(unit_hash),
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
    policy_information = _locate_policy_information(
        data,
        start=reader.offset,
        end=headers[0].offset,
        player_index=player_index,
    )

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
            name_key=city_candidate.name_key,
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
        policy_information=policy_information,
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
