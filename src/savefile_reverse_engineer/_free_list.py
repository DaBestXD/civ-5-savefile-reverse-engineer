"""Shared validation for serialized FFreeListTrashArray headers."""

from dataclasses import dataclass

from ._binary_reader import LittleEndianReader

FREE_LIST_MAX_SLOTS = 1 << 13
FREE_LIST_INDEX_MASK = FREE_LIST_MAX_SLOTS - 1


@dataclass(slots=True)
class FreeListHeader:
    """Validated free-list header and its occupied/free slot partition."""

    byte_offset: int
    byte_length: int
    slot_count: int
    last_index: int
    free_list_head: int
    free_count: int
    current_id: int
    next_free_indices: tuple[int, ...]
    live_count: int
    live_slots: tuple[int, ...]


def read_free_list_header(
    reader: LittleEndianReader, field: str
) -> FreeListHeader:
    """Read and validate one FFreeListTrashArray header."""
    start = reader.offset
    slot_count = reader.i32(f"{field}.slot_count")
    if slot_count < 0 or slot_count > FREE_LIST_MAX_SLOTS:
        reader.fail(
            f"slot count is {slot_count}, expected 0..{FREE_LIST_MAX_SLOTS}",
            offset=start,
            field=f"{field}.slot_count",
        )
    last_index = reader.i32(f"{field}.last_index")
    if last_index < -1 or last_index >= slot_count:
        reader.fail(
            f"last index is {last_index}, outside the slot array",
            field=f"{field}.last_index",
        )
    free_list_head = reader.i32(f"{field}.free_list_head")
    free_count = reader.i32(f"{field}.free_count")
    if free_count < 0 or free_count > last_index + 1:
        reader.fail(
            f"free count is {free_count}, expected 0..{last_index + 1}",
            field=f"{field}.free_count",
        )
    current_id = reader.i32(f"{field}.current_id")
    if current_id < 0 or current_id & FREE_LIST_INDEX_MASK:
        reader.fail(
            "current ID must be a nonnegative multiple of 8192",
            field=f"{field}.current_id",
        )
    reader.ensure_count_fits(
        slot_count,
        item_size=4,
        reserved_bytes=4,
        field=f"{field}.slot_count",
    )
    next_free_indices = tuple(
        reader.i32(f"{field}.next_free_indices[{index}]")
        for index in range(slot_count)
    )
    live_count = reader.i32(f"{field}.live_count")
    occupied_count = last_index + 1
    if live_count < 0 or live_count > occupied_count:
        reader.fail(
            f"live count is {live_count}, expected 0..{occupied_count}",
            field=f"{field}.live_count",
        )
    if live_count + free_count != occupied_count:
        reader.fail(
            "live and free counts do not cover the occupied slots",
            field=f"{field}.live_count",
        )

    free_slots: set[int] = set()
    next_slot = free_list_head
    while next_slot != -1:
        if next_slot < 0 or next_slot > last_index:
            reader.fail(
                f"free-list index {next_slot} is outside 0..{last_index}",
                field=f"{field}.free_list_head",
            )
        if next_slot in free_slots:
            reader.fail(
                f"free-list chain contains a cycle at slot {next_slot}",
                field=f"{field}.free_list_head",
            )
        free_slots.add(next_slot)
        next_slot = next_free_indices[next_slot]
    if len(free_slots) != free_count:
        reader.fail(
            f"free-list chain contains {len(free_slots)} slots, expected {free_count}",
            field=f"{field}.free_count",
        )
    if free_count == 0 and free_list_head != -1:
        reader.fail(
            "free-list head must be -1 when the free count is zero",
            field=f"{field}.free_list_head",
        )
    live_slots = tuple(
        index for index in range(occupied_count) if index not in free_slots
    )
    return FreeListHeader(
        byte_offset=start,
        byte_length=reader.offset - start,
        slot_count=slot_count,
        last_index=last_index,
        free_list_head=free_list_head,
        free_count=free_count,
        current_id=current_id,
        next_free_indices=next_free_indices,
        live_count=live_count,
        live_slots=live_slots,
    )
