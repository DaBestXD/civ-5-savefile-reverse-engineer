"""Tests for the shared bounded little-endian reader."""

import math

import pytest

from savefile_reverse_engineer._binary_reader import (
    BinaryReadError,
    LittleEndianReader,
)


def test_reads_primitives_and_tracks_remaining_bytes() -> None:
    data = (
        b"\xff\xfe\x34\x12\xfe\xff\x78\x56\x34\x12\xfe\xff\xff\xff\x00\x00\xc0\x3f\x01"
    )
    reader = LittleEndianReader(data)

    assert reader.u8("u8") == 255
    assert reader.i8("i8") == -2
    assert reader.u16("u16") == 0x1234
    assert reader.i16("i16") == -2
    assert reader.u32("u32") == 0x12345678
    assert reader.i32("i32") == -2
    assert reader.f32("f32") == 1.5
    assert reader.read_bool("bool")
    assert reader.remaining == 0


def test_reads_special_float_values() -> None:
    reader = LittleEndianReader(b"\x00\x00\x80\x7f\x00\x00\x80\xff\x00\x00\xc0\x7f")

    assert reader.f32("positive_infinity") == math.inf
    assert reader.f32("negative_infinity") == -math.inf
    assert math.isnan(reader.f32("not_a_number"))


def test_reads_length_prefixed_utf8() -> None:
    reader = LittleEndianReader(b"\x05\x00\x00\x00Lekmod")

    assert reader.read_utf8("name") == "Lekmo"
    assert reader.remaining == 1


def test_rejects_invalid_boolean_utf8_and_truncation() -> None:
    with pytest.raises(BinaryReadError, match="Boolean byte") as boolean:
        _ = LittleEndianReader(b"\x02").read_bool("flag")
    assert boolean.value.offset == 0
    assert boolean.value.field == "flag"

    with pytest.raises(BinaryReadError, match="valid UTF-8") as utf8:
        _ = LittleEndianReader(b"\x01\x00\x00\x00\xff").read_utf8("text")
    assert utf8.value.offset == 4
    assert utf8.value.field == "text"

    with pytest.raises(BinaryReadError, match="truncated value") as truncated:
        _ = LittleEndianReader(b"\x01\x02").u32("value")
    assert truncated.value.offset == 0


def test_rejects_count_that_cannot_fit() -> None:
    reader = LittleEndianReader(b"\x00" * 7)

    with pytest.raises(BinaryReadError, match="count 2 extends"):
        reader.ensure_count_fits(
            2,
            item_size=4,
            reserved_bytes=0,
            field="items",
        )
