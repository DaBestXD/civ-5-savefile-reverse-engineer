"""Locate and decode nested CvUnit records."""

from collections.abc import Sequence

from .._catalogue.units import UNIT_HASH_NAMES
from .._shared.binary_reader import read_u32_count
from .._shared.free_list import FREE_LIST_INDEX_MASK
from .constants import (
    UNIT_ARCHIVE_ENUM_WORDS,
    UNIT_ARCHIVE_FINAL_WORDS,
    UNIT_ARCHIVE_FLAG_COUNT,
    UNIT_ARCHIVE_WORDS_AFTER_IMMOBILE,
    UNIT_ARCHIVE_WORDS_AFTER_PREFIX,
    UNIT_ARCHIVE_WORDS_BEFORE_FLAGS,
    UNIT_CLASS_COUNT,
    UNIT_COMBAT_COUNT,
    UNIT_ERA_COUNT,
    UNIT_FEATURE_COUNT,
    UNIT_SELECTED_PROMOTION_COUNT,
    UNIT_TERRAIN_COUNT,
    UNIT_VERSION,
    UNIT_YIELD_COUNT,
)
from .infrastructure import CvPlayerDecodeError, PlayerReader
from .locator import read_i32
from .unit_models import CvUnit


def find_unit_starts(
    data: bytes,
    *,
    start: int,
    end: int,
    live_slots: Sequence[int],
    player_index: int,
) -> tuple[int, ...]:
    if live_slots and read_i32(data, start) != UNIT_VERSION:
        raise CvPlayerDecodeError(
            f"unsupported version {read_i32(data, start)}; expected {UNIT_VERSION}",
            offset=start,
            player_index=player_index,
            field="units.entries[0].version",
        )
    starts: list[int] = []
    cursor = start
    marker = UNIT_VERSION.to_bytes(4, "little")
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
            unit_id = read_i32(data, candidate + 24)
            has_expected_slot = (
                unit_id >= 0 and unit_id & FREE_LIST_INDEX_MASK == slot_index
            )
            has_valid_prefix = (
                0 <= read_i32(data, candidate + 16) < 512
                and 0 <= read_i32(data, candidate + 20) < 512
            )
            has_valid_hash = False
            if has_expected_slot and has_valid_prefix:
                try:
                    probe = PlayerReader(data, candidate, player_index)
                    _ = probe.u32(f"units.entries[{record_index}].version")
                    for prefix_index in range(6):
                        _ = probe.i32(
                            f"units.entries[{record_index}].archive_prefix[{prefix_index}]"
                        )
                    unit_hash = read_unit_hash(
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


def _ensure_unit_bytes_fit(
    reader: PlayerReader, *, end: int, size: int, field: str
) -> None:
    if size > end - reader.offset:
        reader.fail(
            f"{field} extends beyond the CvUnit record",
            field=field,
        )


def _consume_unit_fixed_bytes(
    reader: PlayerReader, *, end: int, size: int, field: str
) -> None:
    _ensure_unit_bytes_fit(reader, end=end, size=size, field=field)
    _ = reader.read_bytes(size, field)


def read_unit_bool(reader: PlayerReader, *, end: int, field: str) -> bool:
    if reader.offset >= end:
        reader.fail(
            f"{field} extends beyond the CvUnit record",
            field=field,
        )
    return reader.read_bool(field)


def _consume_unit_string(reader: PlayerReader, *, end: int, field: str) -> None:
    _ensure_unit_bytes_fit(reader, end=end, size=4, field=f"{field}.length")
    length = reader.u32(f"{field}.length")
    _consume_unit_fixed_bytes(reader, end=end, size=length, field=field)


def _consume_unit_vector(
    reader: PlayerReader,
    *,
    end: int,
    expected_count: int,
    item_size: int,
    field: str,
) -> None:
    _ensure_unit_bytes_fit(reader, end=end, size=4, field=f"{field}.count")
    count_offset = reader.offset
    count = read_u32_count(reader, field, expected=expected_count)
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


def read_unit_hash(reader: PlayerReader, *, end: int, field: str) -> int:
    """Read the unit hash after the exact Lekmod v34.11 sync archive."""
    # TODO(decoding): Decode the leading unit archive scalars into
    # RawUnitArchive instead of consuming this fixed section only for alignment.
    _consume_unit_fixed_bytes(
        reader,
        end=end,
        size=UNIT_ARCHIVE_WORDS_AFTER_PREFIX * 4,
        field=f"{field}.archive.scalars_after_prefix",
    )
    # TODO(decoding): Store the immobile flag on RawUnitArchive.
    _ = read_unit_bool(reader, end=end, field=f"{field}.archive.immobile")
    # TODO(decoding): Decode the post-immobile scalars into RawUnitArchive.
    _consume_unit_fixed_bytes(
        reader,
        end=end,
        size=UNIT_ARCHIVE_WORDS_AFTER_IMMOBILE * 4,
        field=f"{field}.archive.scalars_after_immobile",
    )
    # TODO(decoding): Store the fortified-this-turn flag on RawUnitArchive.
    _ = read_unit_bool(
        reader,
        end=end,
        field=f"{field}.archive.fortified_this_turn",
    )
    # TODO(decoding): Decode the pre-flag scalars into RawUnitArchive.
    _consume_unit_fixed_bytes(
        reader,
        end=end,
        size=UNIT_ARCHIVE_WORDS_BEFORE_FLAGS * 4,
        field=f"{field}.archive.scalars_before_flags",
    )
    for index in range(UNIT_ARCHIVE_FLAG_COUNT):
        # TODO(decoding): Name and store each confirmed flag on RawUnitArchive.
        _ = read_unit_bool(
            reader,
            end=end,
            field=f"{field}.archive.flags[{index}]",
        )
    _ensure_unit_bytes_fit(
        reader, end=end, size=4, field=f"{field}.archive.num_selected_promotions"
    )
    # TODO(decoding): Store the selected-promotion count on RawUnitArchive.
    _ = reader.i32(f"{field}.archive.num_selected_promotions")
    # TODO(decoding): Decode selected promotions into RawUnitArchive.
    _consume_unit_vector(
        reader,
        end=end,
        expected_count=UNIT_SELECTED_PROMOTION_COUNT,
        item_size=1,
        field=f"{field}.archive.selected_promotions",
    )
    # TODO(decoding): Store embarked and AI-turn-processed on RawUnitArchive.
    _ = read_unit_bool(reader, end=end, field=f"{field}.archive.embarked")
    _ = read_unit_bool(
        reader,
        end=end,
        field=f"{field}.archive.ai_turn_processed",
    )
    # TODO(decoding): Decode the unit archive enums into RawUnitArchive.
    _consume_unit_fixed_bytes(
        reader,
        end=end,
        size=UNIT_ARCHIVE_ENUM_WORDS * 4,
        field=f"{field}.archive.enums",
    )
    # TODO(decoding): Decode the legacy name into RawUnitArchive.
    _consume_unit_string(reader, end=end, field=f"{field}.archive.legacy_name")
    # TODO(decoding): Decode script data into RawUnitArchive.
    _consume_unit_string(reader, end=end, field=f"{field}.archive.script_data")
    for name in ("yield_from_kills", "kill_yield_cap"):
        # TODO(decoding): Decode this unit yield vector into RawUnitArchive.
        _consume_unit_vector(
            reader,
            end=end,
            expected_count=UNIT_YIELD_COUNT,
            item_size=4,
            field=f"{field}.archive.{name}",
        )
    # TODO(decoding): Decode kill-yield era validity into RawUnitArchive.
    _consume_unit_vector(
        reader,
        end=end,
        expected_count=UNIT_ERA_COUNT,
        item_size=1,
        field=f"{field}.archive.kill_yield_era_valid",
    )
    for name, count in (
        ("terrain_double_move", UNIT_TERRAIN_COUNT),
        ("feature_double_move", UNIT_FEATURE_COUNT),
        ("terrain_impassable", UNIT_TERRAIN_COUNT),
        ("feature_impassable", UNIT_FEATURE_COUNT),
        ("extra_terrain_attack", UNIT_TERRAIN_COUNT),
        ("extra_terrain_defense", UNIT_TERRAIN_COUNT),
        ("extra_feature_attack", UNIT_FEATURE_COUNT),
        ("extra_feature_defense", UNIT_FEATURE_COUNT),
        ("extra_unit_combat_modifier", UNIT_COMBAT_COUNT),
        ("unit_class_modifier", UNIT_CLASS_COUNT),
    ):
        # TODO(decoding): Decode this unit modifier vector into RawUnitArchive.
        _consume_unit_vector(
            reader,
            end=end,
            expected_count=count,
            item_size=4,
            field=f"{field}.archive.{name}",
        )
    # TODO(decoding): Decode the final unit archive fields into RawUnitArchive.
    _consume_unit_fixed_bytes(
        reader,
        end=end,
        size=UNIT_ARCHIVE_FINAL_WORDS * 4,
        field=f"{field}.archive.final_fields",
    )
    if 4 > end - reader.offset:
        reader.fail(
            "serialized unit hash extends beyond the CvUnit record",
            field=f"{field}.unit_hash",
        )
    return reader.u32(f"{field}.unit_hash")


def read_unit(
    data: bytes,
    *,
    start: int,
    end: int,
    record_index: int,
    slot_index: int,
    player_index: int,
) -> CvUnit:
    reader = PlayerReader(data, start, player_index)
    field = f"units.entries[{record_index}]"
    version = reader.u32(f"{field}.version")
    if version != UNIT_VERSION:
        reader.fail(
            f"unsupported CvUnit version {version}; expected {UNIT_VERSION}",
            offset=start,
            field=f"{field}.version",
        )
    # TODO(decoding): Store the three confirmed archive-prefix scalars on
    # RawCvUnit instead of discarding them.
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
    unit_hash = read_unit_hash(reader, end=end, field=field)
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


__all__: tuple[str, ...] = ()
