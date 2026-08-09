"""Public result types for nested Lekmod v34.11 CvUnit records."""

from dataclasses import dataclass


@dataclass(slots=True)
class CvUnit:
    """Confirmed leading sync-archive fields from one CvUnit free-list entry."""

    record_index: int
    slot_index: int
    byte_offset: int
    byte_length: int
    version: int
    unit_id: int
    unit_hash: int
    unit_name: str | None
    x: int
    y: int


__all__: tuple[str, ...] = ()
