"""Locate and decode serialized CvPlayer policy information."""

from dataclasses import dataclass

from .._catalogue.policies import POLICY_BRANCH_HASH_NAMES, POLICY_HASH_NAMES
from .._shared.binary_reader import read_u32_count
from .._shared.types import resolve_hashed_type
from .constants import (
    PLAYER_POLICIES_VERSION,
    POLICY_BRANCH_COUNT,
    POLICY_SLOT_COUNT,
)
from .infrastructure import CvPlayerDecodeError, PlayerReader
from .models import (
    CvPlayerPolicy,
    CvPlayerPolicyBranch,
    CvPlayerPolicyInformation,
)


@dataclass(slots=True)
class _HashedBoolEntry:
    hash_value: int
    value: bool | None


def _read_exact_hashed_bool_array(
    reader: PlayerReader, *, count: int, field: str
) -> tuple[_HashedBoolEntry, ...]:
    _ = read_u32_count(reader, field, expected=count)
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
    reader = PlayerReader(data, offset, player_index)
    try:
        version = reader.u32("policy_information.version")
        if version != PLAYER_POLICIES_VERSION:
            return None
        policy_arrays = tuple(
            _read_exact_hashed_bool_array(
                reader,
                count=POLICY_SLOT_COUNT,
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
                count=POLICY_BRANCH_COUNT,
                field=f"policy_information.branch_arrays[{array_index}]",
            )
            for array_index in range(2)
        )
        branch_hashes = tuple(entry.hash_value for entry in branch_arrays[0])
        if (
            any(hash_value == 0 for hash_value in branch_hashes)
            or tuple(entry.hash_value for entry in branch_arrays[1]) != branch_hashes
            or reader.offset > limit
        ):
            return None
    except CvPlayerDecodeError:
        return None

    policy_slots = tuple(
        CvPlayerPolicy(
            policy_type=resolve_hashed_type(entry.hash_value, POLICY_HASH_NAMES),
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
                branch_type=resolve_hashed_type(
                    entry.hash_value, POLICY_BRANCH_HASH_NAMES
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


def locate_policy_information(
    data: bytes,
    *,
    start: int,
    end: int,
    player_index: int,
) -> CvPlayerPolicyInformation:
    marker = b"".join(
        (
            PLAYER_POLICIES_VERSION.to_bytes(4, "little"),
            POLICY_SLOT_COUNT.to_bytes(4, "little"),
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
        reader = PlayerReader(data, start, player_index)
        reader.fail(
            f"found {len(candidates)} structurally valid policy blocks, expected 1",
            offset=start,
            field="policy_information",
        )
    return candidates[0]


__all__: tuple[str, ...] = ()
