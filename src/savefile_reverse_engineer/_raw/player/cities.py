"""Locate and decode nested CvCity records and production data."""

from collections.abc import Sequence
from dataclasses import dataclass

from .._catalogue.buildings import BUILDING_HASH_NAMES
from .._catalogue.production import PROJECT_HASH_NAMES
from .._catalogue.units import UNIT_HASH_NAMES
from .._shared.binary_reader import read_u32_count
from .._shared.free_list import FREE_LIST_INDEX_MASK
from .._shared.types import HashedType, resolve_hashed_type
from .city_models import (
    CityBuildingState,
    CityYieldValues,
    CityYieldVectors,
    CvCity,
    CvCityBuildings,
    ProductionOrder,
    ProductionOrderType,
)
from .constants import (
    CITY_BUILDING_TYPE_COUNT,
    CITY_BUILDINGS_VERSION,
    CITY_DOMAIN_COUNT,
    CITY_DOMAIN_VECTORS,
    CITY_FLAGS_AFTER_SCALARS,
    CITY_IMPROVEMENT_COUNT,
    CITY_OWNER_FIELDS,
    CITY_PLAYER_COUNT,
    CITY_PRODUCTION_QUEUE_CAPACITY,
    CITY_PROJECT_COUNT,
    CITY_RESOURCE_COUNT,
    CITY_SCALARS_AFTER_PREFIX,
    CITY_SPECIALIST_COUNT,
    CITY_UNIT_TYPE_COUNT,
    CITY_VERSION,
    CITY_YIELD_COUNT,
    UNIT_COMBAT_COUNT,
    UNIT_SELECTED_PROMOTION_COUNT,
)
from .infrastructure import CvPlayerDecodeError, PlayerReader
from .locator import read_i32


@dataclass(slots=True)
class _CityCandidate:
    offset: int
    buildings_offset: int
    name_key: str
    yield_vectors: CityYieldVectors


@dataclass(slots=True)
class _CityProbe:
    buildings_offset: int
    name_key: str
    yield_vectors: CityYieldVectors


@dataclass(slots=True)
class _HashedIntEntry:
    hash_value: int
    value: int | None
    hash_offset: int


def _skip_exact_int_vector(
    reader: PlayerReader, *, count: int, field: str
) -> None:
    _ = read_u32_count(reader, field, expected=count)
    _ = reader.read_bytes(count * 4, f"{field}.values")


def _skip_exact_bool_vector(
    reader: PlayerReader, *, count: int, field: str
) -> None:
    _ = read_u32_count(reader, field, expected=count)
    for index in range(count):
        _ = reader.read_bool(f"{field}[{index}]")


def _skip_exact_hashed_int_array(
    reader: PlayerReader, *, count: int, field: str
) -> None:
    _ = read_u32_count(reader, field, expected=count)
    for index in range(count):
        hash_value = reader.u32(f"{field}[{index}].type")
        if hash_value != 0:
            _ = reader.i32(f"{field}[{index}].value")


def _skip_struct_vector(
    reader: PlayerReader, *, item_size: int, field: str
) -> None:
    count = read_u32_count(reader, field)
    _ = reader.read_bytes(count * item_size, f"{field}.entries")


def read_city_yield_values(reader: PlayerReader, *, field: str) -> CityYieldValues:
    _ = read_u32_count(reader, field, expected=CITY_YIELD_COUNT)
    return CityYieldValues(
        food=reader.i32(f"{field}.food"),
        production=reader.i32(f"{field}.production"),
        gold=reader.i32(f"{field}.gold"),
        science=reader.i32(f"{field}.science"),
        culture=reader.i32(f"{field}.culture"),
        faith=reader.i32(f"{field}.faith"),
        golden_age_points=reader.i32(f"{field}.golden_age_points"),
    )


def read_city_yield_vectors(reader: PlayerReader) -> CityYieldVectors:
    field = "cities.probe.yield_vectors"
    return CityYieldVectors(
        sea_plot_yield=read_city_yield_values(reader, field=f"{field}.sea_plot_yield"),
        river_plot_yield=read_city_yield_values(
            reader, field=f"{field}.river_plot_yield"
        ),
        lake_plot_yield=read_city_yield_values(
            reader, field=f"{field}.lake_plot_yield"
        ),
        sea_resource_yield=read_city_yield_values(
            reader, field=f"{field}.sea_resource_yield"
        ),
        base_yield_rate_from_terrain=read_city_yield_values(
            reader, field=f"{field}.base_yield_rate_from_terrain"
        ),
        base_yield_rate_from_buildings=read_city_yield_values(
            reader, field=f"{field}.base_yield_rate_from_buildings"
        ),
        base_yield_rate_from_specialists=read_city_yield_values(
            reader, field=f"{field}.base_yield_rate_from_specialists"
        ),
        base_yield_rate_from_misc=read_city_yield_values(
            reader, field=f"{field}.base_yield_rate_from_misc"
        ),
        base_yield_rate_from_religion=read_city_yield_values(
            reader, field=f"{field}.base_yield_rate_from_religion"
        ),
        base_yield_rate_from_policies=read_city_yield_values(
            reader, field=f"{field}.base_yield_rate_from_policies"
        ),
        garrison_yield_bonus=read_city_yield_values(
            reader, field=f"{field}.garrison_yield_bonus"
        ),
        yield_per_population_x100=read_city_yield_values(
            reader, field=f"{field}.yield_per_population_x100"
        ),
        yield_per_religion_x100=read_city_yield_values(
            reader, field=f"{field}.yield_per_religion_x100"
        ),
        yield_rate_modifier=read_city_yield_values(
            reader, field=f"{field}.yield_rate_modifier"
        ),
        power_yield_rate_modifier=read_city_yield_values(
            reader, field=f"{field}.power_yield_rate_modifier"
        ),
        resource_yield_rate_modifier=read_city_yield_values(
            reader, field=f"{field}.resource_yield_rate_modifier"
        ),
        extra_specialist_yield=read_city_yield_values(
            reader, field=f"{field}.extra_specialist_yield"
        ),
        production_to_yield_modifier=read_city_yield_values(
            reader, field=f"{field}.production_to_yield_modifier"
        ),
    )


def _try_locate_city_buildings(
    data: bytes,
    *,
    start: int,
    end: int,
    player_index: int,
) -> _CityProbe | None:
    reader = PlayerReader(data, start, player_index)
    try:
        _ = reader.read_bytes(15 * 4, "cities.probe.confirmed_prefix")
        _ = reader.read_bytes(
            CITY_SCALARS_AFTER_PREFIX * 4,
            "cities.probe.trailing_scalars",
        )
        for index in range(CITY_FLAGS_AFTER_SCALARS):
            _ = reader.read_bool(f"cities.probe.flags[{index}]")
        _ = reader.read_bytes(
            CITY_OWNER_FIELDS * 4,
            "cities.probe.owner_fields",
        )
        yield_vectors = read_city_yield_vectors(reader)
        for index in range(CITY_DOMAIN_VECTORS):
            # TODO(decoding): Decode city domain modifiers into RawCvCity
            # instead of consuming each integer vector only for alignment.
            _skip_exact_int_vector(
                reader,
                count=CITY_DOMAIN_COUNT,
                field=f"cities.probe.domain_vectors[{index}]",
            )
        for index in range(2):
            # TODO(decoding): Decode city player flags into RawCvCity instead
            # of consuming each Boolean vector only for alignment.
            _skip_exact_bool_vector(
                reader,
                count=CITY_PLAYER_COUNT,
                field=f"cities.probe.player_flags[{index}]",
            )
        _ = reader.read_bool("cities.probe.finished_order_this_turn")
        _ = reader.i32("cities.probe.settler_unit_type")
        name_key = reader.read_utf8("cities.probe.name")
        _ = reader.read_utf8("cities.probe.script_data")
        for index in range(3):
            # TODO(decoding): Decode city resource modifiers into RawCvCity
            # instead of consuming each hashed array only for alignment.
            _skip_exact_hashed_int_array(
                reader,
                count=CITY_RESOURCE_COUNT,
                field=f"cities.probe.resource_arrays[{index}]",
            )
        # TODO(decoding): Decode specialist production into RawCvCity instead
        # of consuming this integer vector only for alignment.
        _skip_exact_int_vector(
            reader,
            count=CITY_SPECIALIST_COUNT,
            field="cities.probe.specialist_production",
        )
        # TODO(decoding): Decode project production into RawCvCity instead of
        # consuming this integer vector only for alignment.
        _skip_exact_int_vector(
            reader,
            count=CITY_PROJECT_COUNT,
            field="cities.probe.project_production",
        )
    except CvPlayerDecodeError:
        return None
    if reader.offset > end:
        return None
    return _CityProbe(
        buildings_offset=reader.offset,
        name_key=name_key,
        yield_vectors=yield_vectors,
    )


def find_city_candidates(
    data: bytes,
    *,
    start: int,
    end: int,
    live_slots: Sequence[int],
    player_index: int,
) -> tuple[_CityCandidate, ...]:
    if live_slots and (start + 4 > end or read_i32(data, start) != CITY_VERSION):
        raise CvPlayerDecodeError(
            f"unsupported version {read_i32(data, start)}; expected {CITY_VERSION}",
            offset=start,
            player_index=player_index,
            field="cities.entries[0].version",
        )
    live_slot_set = set(live_slots)
    candidates_by_slot: dict[int, list[_CityCandidate]] = {
        slot_index: [] for slot_index in live_slots
    }
    marker = CITY_VERSION.to_bytes(4, "little")
    candidate_offset = start
    while True:
        candidate_offset = data.find(marker, candidate_offset, end)
        if candidate_offset < 0:
            break
        if candidate_offset + 60 <= end:
            city_id = read_i32(data, candidate_offset + 4)
            slot_index = city_id & FREE_LIST_INDEX_MASK
            has_valid_prefix = (
                city_id >= 0
                and slot_index in live_slot_set
                and 0 <= read_i32(data, candidate_offset + 8) < 512
                and 0 <= read_i32(data, candidate_offset + 12) < 512
                and read_i32(data, candidate_offset + 32) >= 0
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
                            yield_vectors=probe.yield_vectors,
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


def _read_building_array(
    reader: PlayerReader, *, field: str
) -> tuple[_HashedIntEntry, ...]:
    count_offset = reader.offset
    count = reader.i32(f"{field}.count")
    if count != CITY_BUILDING_TYPE_COUNT:
        reader.fail(
            f"saved count is {count}, expected {CITY_BUILDING_TYPE_COUNT}",
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


def read_city_buildings(
    data: bytes,
    *,
    start: int,
    end: int,
    record_index: int,
    player_index: int,
) -> CvCityBuildings:
    reader = PlayerReader(data, start, player_index)
    field = f"cities.entries[{record_index}].buildings"
    version = reader.u32(f"{field}.version")
    if version != CITY_BUILDINGS_VERSION:
        reader.fail(
            f"unsupported CvCityBuildings version {version}; expected {CITY_BUILDINGS_VERSION}",
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
            building=resolve_hashed_type(expected_hashes[index], BUILDING_HASH_NAMES),
            production_times_100=arrays[0][index].value,
            production_turns=arrays[1][index].value,
            original_owner=arrays[2][index].value,
            original_year=arrays[3][index].value,
            real_count=arrays[4][index].value,
            free_count=arrays[5][index].value,
        )
        for index in range(CITY_BUILDING_TYPE_COUNT)
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


def read_city_production_queue(
    data: bytes,
    *,
    start: int,
    end: int,
    record_index: int,
    player_index: int,
) -> tuple[ProductionOrder, ...]:
    reader = PlayerReader(data, start, player_index)
    field = f"cities.entries[{record_index}]"

    # TODO(decoding): Decode building yield changes into RawCvCityBuildings.
    _skip_struct_vector(
        reader,
        item_size=3 * 4,
        field=f"{field}.buildings.yield_changes",
    )
    # TODO(decoding): Decode building great works into RawCvCityBuildings.
    _skip_struct_vector(
        reader,
        item_size=3 * 4,
        field=f"{field}.buildings.great_works",
    )
    for array_name in ("unit_production", "unit_production_time"):
        # TODO(decoding): Decode this unit production array into RawCvCity.
        _skip_exact_hashed_int_array(
            reader,
            count=CITY_UNIT_TYPE_COUNT,
            field=f"{field}.{array_name}",
        )
    for vector_name, count in (
        ("specialist_count", CITY_SPECIALIST_COUNT),
        ("maximum_specialist_count", CITY_SPECIALIST_COUNT),
        ("forced_specialist_count", CITY_SPECIALIST_COUNT),
        ("free_specialist_count", CITY_SPECIALIST_COUNT),
        ("improvement_free_specialists", CITY_IMPROVEMENT_COUNT),
        ("unit_combat_free_experience", UNIT_COMBAT_COUNT),
        ("unit_combat_production_modifier", UNIT_COMBAT_COUNT),
    ):
        # TODO(decoding): Decode this named city vector into RawCvCity.
        _skip_exact_int_vector(
            reader,
            count=count,
            field=f"{field}.{vector_name}",
        )
    # TODO(decoding): Decode free promotion counts into RawCvCity.
    _skip_exact_hashed_int_array(
        reader,
        count=UNIT_SELECTED_PROMOTION_COUNT,
        field=f"{field}.free_promotion_count",
    )

    count_offset = reader.offset
    count = reader.u32(f"{field}.production_queue.count")
    if count > CITY_PRODUCTION_QUEUE_CAPACITY:
        reader.fail(
            (f"saved count is {count}, maximum is {CITY_PRODUCTION_QUEUE_CAPACITY}"),
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


def read_city(
    data: bytes,
    *,
    start: int,
    buildings_offset: int,
    end: int,
    record_index: int,
    slot_index: int,
    player_index: int,
    name_key: str,
    yield_vectors: CityYieldVectors,
) -> CvCity:
    reader = PlayerReader(data, start, player_index)
    field = f"cities.entries[{record_index}]"
    version = reader.u32(f"{field}.version")
    if version != CITY_VERSION:
        reader.fail(
            f"unsupported CvCity version {version}; expected {CITY_VERSION}",
            offset=start,
            field=f"{field}.version",
        )
    city_id = reader.i32(f"{field}.city_id")
    if city_id & FREE_LIST_INDEX_MASK != slot_index:
        reader.fail(
            f"city ID {city_id} does not name free-list slot {slot_index}",
            field=f"{field}.city_id",
        )
    buildings = read_city_buildings(
        data,
        start=buildings_offset,
        end=end,
        record_index=record_index,
        player_index=player_index,
    )
    production_queue = read_city_production_queue(
        data,
        start=buildings.byte_offset + buildings.inventory_byte_length,
        end=end,
        record_index=record_index,
        player_index=player_index,
    )
    building_hashes = {state.building.hash_value for state in buildings.entries}
    for order in production_queue:
        if (
            order.order_type is ProductionOrderType.CONSTRUCT_BUILDING
            and order.item.hash_value not in building_hashes
        ):
            reader.fail(
                f"queued building hash 0x{order.item.hash_value:08X} is absent from the inventory",
                offset=order.byte_offset + 4,
                field=f"{field}.production_queue[{order.queue_index}].item",
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
        yield_vectors=yield_vectors,
        buildings=buildings,
        production_queue=production_queue,
    )


__all__: tuple[str, ...] = ()
