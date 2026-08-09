"""Shared helpers for binary-decoder tests."""


def replace_unsigned(data: bytes, offset: int, size: int, value: int) -> bytes:
    """Replace one unsigned little-endian value in immutable test data."""
    replacement = value.to_bytes(size, byteorder="little", signed=False)
    return data[:offset] + replacement + data[offset + size :]
