"""Error and reader infrastructure for raw player decoding."""

from typing import NoReturn, override

from .._shared.binary_reader import LittleEndianReader


class CvPlayerDecodeError(ValueError):
    """Malformed or unsupported value in a serialized CvPlayer array."""

    message: str
    offset: int
    player_index: int
    field: str

    def __init__(
        self, message: str, *, offset: int, player_index: int, field: str
    ) -> None:
        self.message = message
        self.offset = offset
        self.player_index = player_index
        self.field = field
        super().__init__(
            f"player {player_index} {field} at byte offset 0x{offset:X}: {message}"
        )


class PlayerReader(LittleEndianReader):
    __slots__: tuple[str, ...] = ("player_index",)
    _bounds_error_suffix: str = "player-array bytes"
    player_index: int
    offset: int

    def __init__(self, data: bytes, offset: int, player_index: int) -> None:
        super().__init__(data)
        self.offset = offset
        self.player_index = player_index

    @override
    def fail(
        self,
        message: str,
        *,
        offset: int | None = None,
        field: str | None = None,
    ) -> NoReturn:
        raise CvPlayerDecodeError(
            message,
            offset=self.offset if offset is None else offset,
            player_index=self.player_index,
            field="player" if field is None else field,
        )


__all__: tuple[str, ...] = ()
