"""Locate and validate the 64 variable-length CvPlayer records."""

from bisect import bisect_left, bisect_right
from collections.abc import Sequence
from dataclasses import dataclass, field

from .._shared.free_list import FREE_LIST_INDEX_MASK
from .constants import (
    FREE_LIST_SLOT_COUNTS,
    INVALID_PLOT_COORD,
    MINIMUM_PLAYER_LENGTH,
    PLAYER_COUNT,
    PLAYER_VERSION,
)
from .infrastructure import CvPlayerDecodeError


@dataclass(slots=True)
class HeaderCandidate:
    offset: int
    byte_length: int


@dataclass(slots=True)
class _PlayerPathSearch:
    data: bytes
    headers: tuple[HeaderCandidate, ...]
    require_exact_end: bool
    header_offsets: tuple[int, ...]
    candidate_offsets: tuple[int, ...]
    memo: dict[tuple[int, int, int], tuple[int, ...] | None] = field(
        default_factory=dict
    )

    def header_count(self, start: int, end: int) -> int:
        return bisect_left(self.header_offsets, end) - bisect_right(
            self.header_offsets, start
        )

    def find_path(
        self, previous: int, current: int, players_remaining: int
    ) -> tuple[int, ...] | None:
        key = (previous, current, players_remaining)
        if key in self.memo:
            return self.memo[key]
        path = self._find_uncached_path(previous, current, players_remaining)
        self.memo[key] = path
        return path

    def _find_uncached_path(
        self, previous: int, current: int, players_remaining: int
    ) -> tuple[int, ...] | None:
        if players_remaining == 1:
            final_header_index = bisect_right(self.header_offsets, current)
            if final_header_index + 2 >= len(self.headers):
                return None
            previous_header_index = bisect_right(self.header_offsets, previous)
            if previous_header_index + 2 >= len(self.headers):
                return None
            previous_third = self.headers[previous_header_index + 2]
            final_third = self.headers[final_header_index + 2]
            previous_tail_length = current - (
                previous_third.offset + previous_third.byte_length
            )
            final_end = (
                final_third.offset + final_third.byte_length + previous_tail_length
            )
            if final_end > len(self.data) or (
                self.require_exact_end and final_end != len(self.data)
            ):
                return None
            return (current,)

        minimum_next = current + MINIMUM_PLAYER_LENGTH
        first_candidate = bisect_left(self.candidate_offsets, minimum_next)
        for next_start in self.candidate_offsets[first_candidate:]:
            free_list_count = self.header_count(current, next_start)
            if free_list_count < 3:
                continue
            if free_list_count > 3:
                break
            suffix = self.find_path(current, next_start, players_remaining - 1)
            if suffix is not None:
                return (current, *suffix)
        return None


def read_i32(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little", signed=True)


def _try_free_list_header(
    data: bytes, offset: int, limit: int
) -> HeaderCandidate | None:
    if offset + 24 > limit:
        return None
    slot_count = read_i32(data, offset)
    if slot_count not in FREE_LIST_SLOT_COUNTS:
        return None
    last_index = read_i32(data, offset + 4)
    free_list_head = read_i32(data, offset + 8)
    free_count = read_i32(data, offset + 12)
    current_id = read_i32(data, offset + 16)
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
    live_count = read_i32(data, end - 4)
    if live_count < 0 or live_count + free_count != last_index + 1:
        return None
    next_free_indices = tuple(
        read_i32(data, offset + 20 + index * 4) for index in range(slot_count)
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
    return HeaderCandidate(
        offset=offset,
        byte_length=24 + slot_count * 4,
    )


def _find_free_list_headers(
    data: bytes, start: int, limit: int
) -> tuple[HeaderCandidate, ...]:
    candidates: dict[int, HeaderCandidate] = {}
    for slot_count in FREE_LIST_SLOT_COUNTS:
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
    if offset + 68 > limit or read_i32(data, offset) != PLAYER_VERSION:
        return False
    starting_x = read_i32(data, offset + 4)
    starting_y = read_i32(data, offset + 8)
    coordinates_are_valid = (
        starting_x == INVALID_PLOT_COORD and starting_y == INVALID_PLOT_COORD
    ) or (0 <= starting_x < 512 and 0 <= starting_y < 512)
    population = read_i32(data, offset + 12)
    land = read_i32(data, offset + 16)
    return (
        coordinates_are_valid and 0 <= population < 1_000_000 and 0 <= land < 1_000_000
    )


def locate_player_records(
    data: bytes,
    byte_offset: int,
    expected_totals: Sequence[tuple[int, int]] | None = None,
    *,
    require_exact_end: bool = False,
) -> tuple[tuple[int, int, tuple[HeaderCandidate, ...]], ...]:
    if expected_totals is not None and len(expected_totals) != PLAYER_COUNT:
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
        version_marker = PLAYER_VERSION.to_bytes(4, "little")
        for player_index in range(1, PLAYER_COUNT):
            search_offset = starts[-1] + MINIMUM_PLAYER_LENGTH
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
                        read_i32(data, candidate + 12),
                        read_i32(data, candidate + 16),
                    )
                    == expected_totals[player_index]
                ):
                    starts.append(candidate)
                    break
                search_offset = candidate + 1

    records: list[tuple[int, int, tuple[HeaderCandidate, ...]]] = []
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
            player_index=PLAYER_COUNT - 1,
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
            player_index=PLAYER_COUNT - 1,
            field="byte_length",
        )
    if previous_end - previous_start < MINIMUM_PLAYER_LENGTH:
        raise CvPlayerDecodeError(
            "the preceding player record is too short to bound the final player",
            offset=previous_start,
            player_index=PLAYER_COUNT - 2,
            field="byte_length",
        )
    records.append((last_start, last_end, last_three))
    return tuple(records)


def _find_player_starts_by_structure(
    data: bytes,
    *,
    byte_offset: int,
    headers: tuple[HeaderCandidate, ...],
    require_exact_end: bool,
) -> tuple[int, ...]:
    """Find the one 64-record path whose records each contain three free lists."""
    header_offsets = tuple(header.offset for header in headers)
    candidates = [byte_offset]
    marker = PLAYER_VERSION.to_bytes(4, "little")
    search_offset = byte_offset + MINIMUM_PLAYER_LENGTH
    while True:
        candidate = data.find(marker, search_offset)
        if candidate < 0:
            break
        if _has_plausible_player_prefix(data, candidate, len(data)):
            candidates.append(candidate)
        search_offset = candidate + 1
    candidate_offsets = tuple(candidates)

    search = _PlayerPathSearch(
        data=data,
        headers=headers,
        require_exact_end=require_exact_end,
        header_offsets=header_offsets,
        candidate_offsets=candidate_offsets,
    )
    path = search.find_path(byte_offset, byte_offset, PLAYER_COUNT)
    if path is None:
        raise CvPlayerDecodeError(
            "no complete 64-player path with three object free lists per record was found",
            offset=byte_offset,
            player_index=0,
            field="player_array",
        )
    return path


__all__: tuple[str, ...] = ()
