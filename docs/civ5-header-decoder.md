# `Civ5SaveDecoder` header and payload API

For the byte layout and the reasoning behind the decoder's design, see
[How the Civilization V physical save header works](civ5-header-format.md).

`Civ5SaveDecoder` reads one complete physical `.CIV5SAVE` file. It provides
access to the header and decompressed payload, plus lazy iterators for
`CvPlot`, `CvTeam`, and partial `CvPlayer` records. It supports the supplied
Civilization V build 403694 saves with these serialization versions:

- Outer save version 8
- Slot-hint version 3
- `CvPreGame` archive version 6
- `CvWorldInfo` version 2

```python
from savefile_reverse_engineer import Civ5SaveDecoder

decoder = Civ5SaveDecoder("AutoSave.Civ5Save")
header = decoder.header

print(header.quick.turn)
print(header.pregame.game_name)
for player in header.slot_hints.players:
    if player.display_name is not None:
        print(player.display_name, player.steam_id)
```

The constructor accepts a string or path-like object. It reads the file once,
so later filesystem changes do not affect the decoder. Header decoding is
deferred until `header` is first accessed and its result is cached.

Use `decompress_payload` to return the complete decompressed payload:

```python
payload = decoder.decompress_payload()
```

The method validates the header and chunk framing, removes the physical chunk
lengths, joins the chunk bodies, and decompresses them as one zlib stream. The
returned `bytes` value is cached for later payload decoders.

## Result sections

The `header` property returns a `Civ5SaveHeader` data class. Its nested result
records are data classes too, and their fields are available as attributes.

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
Invalid compressed data raises `Civ5SavePayloadDecompressionError`.
Invalid SQLite, `CvMap`, or map-tail framing encountered while locating payload
records raises `Civ5SavePayloadDecodeError`.

The full pregame archive can contain administrator or civilization passwords,
email addresses, and an SMTP host. Do not log the complete decoded result
without considering those values.
