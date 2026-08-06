"""Shared bounded reader for little-endian Civilization V data."""

import math
from typing import NoReturn


class BinaryReadError(ValueError):
    """An invalid or truncated value read from binary data."""

    offset: int
    field: str | None

    def __init__(self, message: str, *, offset: int, field: str | None) -> None:
        self.offset = offset
        self.field = field
        super().__init__(message)


class LittleEndianReader:
    """Read bounded primitive values from an in-memory byte sequence."""

    __slots__: tuple[str, ...] = ("data", "offset")
    _bounds_error_suffix: str = "bytes"

    data: bytes
    offset: int

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.offset = 0

    @property
    def remaining(self) -> int:
        """Return the number of unread bytes."""
        return len(self.data) - self.offset

    def fail(
        self,
        message: str,
        *,
        offset: int | None = None,
        field: str | None = None,
    ) -> NoReturn:
        """Raise an offset-aware binary read error."""
        raise BinaryReadError(
            message,
            offset=self.offset if offset is None else offset,
            field=field,
        )

    def read_bytes(self, size: int, field: str) -> bytes:
        """Read exactly *size* bytes."""
        start = self.offset
        end = start + size
        if size < 0 or end > len(self.data):
            self.fail(
                f"truncated {field}; need {size} bytes but only {self.remaining} remain",
                offset=start,
                field=field,
            )
        self.offset = end
        return self.data[start:end]

    def _read_int(self, size: int, *, signed: bool, field: str) -> int:
        return int.from_bytes(
            self.read_bytes(size, field), byteorder="little", signed=signed
        )

    def read_bool(self, field: str) -> bool:
        """Read a Boolean stored as one byte and require zero or one."""
        start = self.offset
        value = self._read_int(1, signed=False, field=field)
        if value not in (0, 1):
            self.fail(
                f"{field} Boolean byte is {value}, expected 0 or 1",
                offset=start,
                field=field,
            )
        return value == 1

    def i8(self, field: str) -> int:
        """Read a signed 8-bit integer."""
        return self._read_int(1, signed=True, field=field)

    def u8(self, field: str) -> int:
        """Read an unsigned 8-bit integer."""
        return self._read_int(1, signed=False, field=field)

    def i16(self, field: str) -> int:
        """Read a signed little-endian 16-bit integer."""
        return self._read_int(2, signed=True, field=field)

    def u16(self, field: str) -> int:
        """Read an unsigned little-endian 16-bit integer."""
        return self._read_int(2, signed=False, field=field)

    def i32(self, field: str) -> int:
        """Read a signed little-endian 32-bit integer."""
        return self._read_int(4, signed=True, field=field)

    def u32(self, field: str) -> int:
        """Read an unsigned little-endian 32-bit integer."""
        return self._read_int(4, signed=False, field=field)

    def f32(self, field: str) -> float:
        """Read an IEEE 754 little-endian 32-bit float."""
        bits = int.from_bytes(self.read_bytes(4, field), byteorder="little")
        sign = -1.0 if bits & 0x80000000 else 1.0
        exponent = (bits >> 23) & 0xFF
        fraction = bits & 0x7FFFFF
        if exponent == 0xFF:
            if fraction:
                return math.nan
            return math.copysign(math.inf, sign)
        if exponent == 0:
            return sign * math.ldexp(float(fraction), -149)
        return sign * math.ldexp(float(0x800000 | fraction), exponent - 150)

    def read_utf8(self, field: str) -> str:
        """Read a u32-length-prefixed UTF-8 string."""
        length_offset = self.offset
        length = self.u32(f"{field}.length")
        self.ensure_count_fits(
            length,
            item_size=1,
            reserved_bytes=0,
            field=f"{field}.length",
        )
        raw_value = self.read_bytes(length, field)
        try:
            return raw_value.decode("utf-8")
        except UnicodeDecodeError as error:
            self.fail(
                f"{field} is not valid UTF-8: {error.reason}",
                offset=length_offset + 4 + error.start,
                field=field,
            )

    def ensure_count_fits(
        self,
        count: int,
        *,
        item_size: int,
        reserved_bytes: int,
        field: str,
    ) -> None:
        """Require a count of fixed-size items to fit in the unread data."""
        available = self.remaining - reserved_bytes
        if item_size <= 0:
            self.fail(
                f"internal item size for {field} is {item_size}, expected a positive value",
                field=field,
            )
        if available < 0 or count > available // item_size:
            self.fail(
                f"{field} count {count} extends beyond the supplied "
                + self._bounds_error_suffix,
                field=field,
            )
