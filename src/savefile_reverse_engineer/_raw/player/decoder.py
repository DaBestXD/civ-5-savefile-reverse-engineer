"""Assemble raw CvPlayer records and expose player-array entry points."""

from collections.abc import Iterator, Sequence

from .._shared.free_list import read_free_list_header
from .cities import find_city_candidates, read_city
from .constants import PLAYER_VERSION
from .infrastructure import CvPlayerDecodeError, PlayerReader
from .locator import HeaderCandidate, locate_player_records
from .models import CvPlayer, SerializedFreeList
from .policies import locate_policy_information
from .units import find_unit_starts, read_unit


def _read_player(
    data: bytes,
    *,
    player_index: int,
    start: int,
    end: int,
    headers: tuple[HeaderCandidate, ...],
) -> CvPlayer:
    reader = PlayerReader(data, start, player_index)
    version = reader.u32("version")
    if version != PLAYER_VERSION:
        reader.fail(
            f"unsupported CvPlayer version {version}; expected {PLAYER_VERSION}",
            offset=start,
            field="version",
        )
    prefix_values = tuple(reader.i32(f"prefix[{index}]") for index in range(16))
    policy_information = locate_policy_information(
        data,
        start=reader.offset,
        end=headers[0].offset,
        player_index=player_index,
    )

    city_reader = PlayerReader(data, headers[0].offset, player_index)
    city_header = read_free_list_header(city_reader, "cities")
    unit_reader = PlayerReader(data, headers[1].offset, player_index)
    unit_header = read_free_list_header(unit_reader, "units")

    city_candidates = find_city_candidates(
        data,
        start=city_reader.offset,
        end=headers[1].offset,
        live_slots=city_header.live_slots,
        player_index=player_index,
    )
    cities = tuple(
        read_city(
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
            yield_vectors=city_candidate.yield_vectors,
        )
        for index, city_candidate in enumerate(city_candidates)
    )

    unit_starts = find_unit_starts(
        data,
        start=unit_reader.offset,
        end=headers[2].offset,
        live_slots=unit_header.live_slots,
        player_index=player_index,
    )
    units = tuple(
        read_unit(
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
    records = locate_player_records(payload, byte_offset, expected_totals)
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
    records = locate_player_records(player_array_bytes, 0, require_exact_end=True)
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
