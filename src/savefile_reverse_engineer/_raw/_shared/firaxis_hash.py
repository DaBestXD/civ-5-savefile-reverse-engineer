"""Private Firaxis database type hashing."""

import zlib


def firaxis_hash(type_name: str) -> int:
    """Return the serialized hash for a Firaxis database type name."""
    return (~zlib.crc32(type_name.encode("ascii"))) & 0xFFFFFFFF


__all__: tuple[str, ...] = ()
