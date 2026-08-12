"""Public decoding errors raised by the semantic API."""


class Civ5SaveHeaderDecodeError(ValueError):
    """A malformed or unsupported physical save header."""

    offset: int
    field: str

    def __init__(
        self, message: str, *, offset: int, field: str
    ) -> None:
        self.offset = offset
        self.field = field
        super().__init__(
            f"{field} at physical byte offset 0x{offset:X}: {message}"
        )


class Civ5SavePayloadDecompressionError(ValueError):
    """A compressed save payload that cannot be decompressed."""


class Civ5SavePayloadDecodeError(ValueError):
    """Malformed or unsupported framing in a decompressed payload."""

    offset: int
    field: str

    def __init__(
        self, message: str, *, offset: int, field: str
    ) -> None:
        self.offset = offset
        self.field = field
        super().__init__(
            f"{field} at decompressed byte offset 0x{offset:X}: {message}"
        )


class CvPlotDecodeError(ValueError):
    """Malformed or unsupported data in a serialized plot array."""

    offset: int
    plot_index: int

    def __init__(
        self, message: str, *, offset: int, plot_index: int
    ) -> None:
        self.offset = offset
        self.plot_index = plot_index
        super().__init__(
            f"plot {plot_index} at byte offset 0x{offset:X}: {message}"
        )


class CvTeamDecodeError(ValueError):
    """Malformed or unsupported data in a serialized team array."""

    offset: int
    team_index: int

    def __init__(
        self, message: str, *, offset: int, team_index: int
    ) -> None:
        self.offset = offset
        self.team_index = team_index
        super().__init__(
            f"team {team_index} at byte offset 0x{offset:X}: {message}"
        )


class CvPlayerDecodeError(ValueError):
    """Malformed or unsupported data in a serialized player array."""

    offset: int
    player_index: int
    field: str

    def __init__(
        self,
        message: str,
        *,
        offset: int,
        player_index: int,
        field: str,
    ) -> None:
        self.offset = offset
        self.player_index = player_index
        self.field = field
        super().__init__(
            f"player {player_index} {field} at byte offset 0x{offset:X}: {message}"
        )


__all__ = (
    "Civ5SaveHeaderDecodeError",
    "Civ5SavePayloadDecodeError",
    "Civ5SavePayloadDecompressionError",
    "CvPlayerDecodeError",
    "CvPlotDecodeError",
    "CvTeamDecodeError",
)
