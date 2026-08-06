# Physical Civ V save-header decoder

For the byte layout and the reasoning behind the decoder's design, see
[How the Civilization V physical save header works](civ5-header-format.md).

The header decoder reads a complete physical `.CIV5SAVE` file and returns the
uncompressed information that precedes the chunked zlib payload. It supports
the supplied Civilization V build 403694 saves with these serialization
versions:

- Outer save version 8
- Slot-hint version 3
- `CvPreGame` archive version 6
- `CvWorldInfo` version 2

```python
from pathlib import Path

from savefile_reverse_engineer import decode_civ5_save_header

save_bytes = Path("AutoSave.Civ5Save").read_bytes()
header = decode_civ5_save_header(save_bytes)

print(header["quick"]["turn"])
print(header["pregame"]["game_name"])
for player in header["slot_hints"]["players"]:
    if player["display_name"] is not None:
        print(player["display_name"], player["steam_id"])
```

The input must contain the complete physical file. The decoder validates every
compressed chunk length through physical EOF, but it does not copy or
decompress the payload.

## Result sections

`quick` contains the fields used for the save browser, including the game and
build versions, turn, active civilization context, difficulty, eras, speed,
world size, map script, DLC, and formal enabled-mod array.

`slot_hints` contains all 64 player slots. A multiplayer nickname ending in
`@` and a 17-digit Steam ID is also exposed as separate `display_name` and
`steam_id` values. The unmodified nickname remains in `raw_nickname`.

`pregame` contains every field written by the supported version of
`CvPreGame::writeArchive`. It includes the serialized calendar, climate,
sea-level, turn-timer, and world records, plus game and map options.

`unknown_spans` preserves the exact offsets and bytes of the quick-header
bridge fields whose meanings are not confirmed.

`compressed_chunks` contains only physical offsets and lengths. The first
chunk's data offset is also available as `zlib_offset`.

## Mod and version strings

`RacismLEKMOD v34.11` occupies the serialized `pregame.game_name` field in the
multiplayer saves. It is returned there and is not promoted to a formal mod
identifier. The formal `quick.enabled_mods` array is empty in all supplied
saves. Nonempty formal mod arrays are rejected until their build-403694 layout
is confirmed with a fixture.

`pregame.version_string` is a different field. It contains
`403694 FINAL_RELEASE` in the supplied saves.

## Errors and sensitive values

Malformed or unsupported data raises `Civ5SaveHeaderDecodeError`. Its `field`
and `offset` attributes identify the failing header path and physical byte.

The full pregame archive can contain administrator or civilization passwords,
email addresses, and an SMTP host. Do not log the complete decoded result
without considering those values.
