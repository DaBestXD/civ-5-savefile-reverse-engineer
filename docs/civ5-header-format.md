# How the Civilization V physical save header works

This document explains the uncompressed header at the start of the examined
`.CIV5SAVE` files. It also explains the design decisions in the header decoder.

The supported files use:

- Civilization V build `403694`
- Outer save version `8`
- Slot-hint version `3`
- `CvPreGame` archive version `6`
- `CvWorldInfo` version `2`

Other versions may use different fields or field widths. The decoder rejects
them until their layouts are confirmed with real saves and matching source.

The examined multiplayer saves contain these values. They are fixture evidence,
not required values for every supported save:

| Field | Examined value |
|---|---|
| Game version | `1.0.3.279 (403694)` |
| Build string | `403694 FINAL_RELEASE` |
| Pregame game name | `RacismLEKMOD v34.11` |
| Map script | `Assets\\Maps\\Lekmap v5.2\\LekmapPangaeaFractalv5.2.lua` |
| World size | `WORLDSIZE_TINY` |
| Game speed | `GAMESPEED_QUICK` |
| Handicap | `HANDICAP_IMMORTAL` |

## Physical file layout

A physical save contains an uncompressed header followed by a chunked zlib
stream:

```text
physical offset 0
├─ quick-reference header
├─ partially understood bridge
├─ slot hints
├─ full CvPreGame archive
├─ u32 compression type
├─ u32 first compressed-chunk length
├─ first compressed chunk
├─ u32 next compressed-chunk length
├─ next compressed chunk
└─ repeated to physical EOF
```

All confirmed integers are little-endian. Strings use this framing:

```text
u32 UTF-8 byte length
u8  text[length]
```

Most arrays begin with a `u32` item count. The item type determines the size of
each following value. An array of strings therefore contains a count followed
by that many independently length-prefixed strings.

## Layer 1: quick-reference header

The first layer begins with `CIV5`. It contains information the game can show
without decompressing the complete save:

1. `CIV5` signature
2. Outer save version
3. Game version string
4. Build string
5. Saved turn
6. Quick game mode
7. Active civilization context
8. Difficulty
9. Starting era
10. Current era
11. Game speed
12. World size
13. Map-script path
14. Enabled DLC array
15. Formal enabled-mod array
16. Player color and bridge data

The active civilization, current era, and difficulty can describe the active
player's view of the game. They must not automatically be treated as global
state.

### Enabled DLC

Each examined DLC entry contains:

```text
16-byte GUID
u32 value
length-prefixed display name
```

The decoder returns the GUID as its conventional text form. It calls the
four-byte field `value` because its exact meaning has not been proven. Every
examined enabled entry uses `1`.

The multiplayer saves list content such as Mongolia, Babylon, Gods and Kings,
and Brave New World. Some single-player saves also list the single-player map
DLC packages.

### Formal mods and the game name

The formal enabled-mod array is empty in all 61 supplied saves. A nonempty
array is currently rejected because no matching build-403694 fixture confirms
its entry layout.

The multiplayer text `RacismLEKMOD v34.11` is not stored in that formal mod
array. It appears later in the exact position where `CvPreGame::writeArchive`
writes `s_gameName`. The bytes around it follow this order:

```text
deprecated force-control array
game mode
game name                  "RacismLEKMOD v34.11"
game speed
game-started Boolean
game turn
game type
map type
```

For that reason, the decoder returns the text as `pregame.game_name`. It does
not create inferred `mod_name` or `mod_version` fields. This avoids claiming
that any version-like string is authoritative mod metadata.

Single-player saves demonstrate why this matters. They contain Lekmap v5.2
paths but do not contain `LEKMOD` or `v34.11`. Their exact mod version cannot be
proved from the physical header.

## Layer 2: partially understood bridge

Between the quick fields and the slot hints is a short bridge. Its framing is
known, but the meaning of every value is not.

The decoder reads enough structure to reach the slot hints safely. It returns
the unconfirmed portions in `unknown_spans`. Each span contains:

- A descriptive label
- Its physical byte offset
- Its byte length
- The exact original bytes

Preserving these bytes has two benefits. No information is silently lost, and
future reverse-engineering work can assign meanings without changing how the
rest of the file is located.

The decoder does not guess names from printable text inside an unknown span.
Readable bytes are evidence, but they do not prove the surrounding field's
purpose.

## Layer 3: slot hints

The version-3 slot-hint block is written before the full pregame archive. It
contains:

1. Slot-hint version
2. Game-speed database index
3. World-size database index
4. Map-script path
5. 64 civilization indices
6. 64 nicknames
7. 64 slot statuses
8. 64 slot claims
9. 64 team indices
10. 64 handicaps
11. 64 civilization type keys
12. 64 leader type keys

These parallel arrays are combined into 64 `PlayerSlot` results. Combining
them prevents callers from accidentally joining arrays with different indices.
The original values are still preserved in each slot.

### Multiplayer names and Steam IDs

Multiplayer nicknames use this observed form:

```text
display name@17-digit Steam ID
```

The decoder retains the complete value as `raw_nickname`. It also returns
`display_name` and `steam_id` when, and only when, the suffix after the final
`@` is exactly 17 ASCII digits. This rule avoids splitting ordinary names that
happen to contain `@`.

Slot hints describe lobby and load-time setup. They are separate from detailed
`CvPlayer` objects in the decompressed payload.

## Layer 4: full CvPreGame archive

After the slot hints, `CvPreGame::writeArchive` writes a versioned archive. The
supported archive is version `6`.

The decoder follows the source serialization order rather than looking for
recognizable strings or byte patterns. It reads all fields, including:

- Active player and aliases
- Administrator and civilization passwords
- Civilization descriptions and leader names
- Game mode, game name, speed, and turn
- Handicap, team, slot, and network arrays
- Map script, random seed, and scenario settings
- Minor-civilization and player-color type keys
- Multiplayer, quick-combat, and readiness settings
- Turn-timer and victory settings
- Game and map custom options
- Steam and email notification settings

Several embedded database records inherit the common `CvBaseInfo` fields:

- Calendar information
- Climate information
- Sea-level information
- Turn-timer information
- World-size information

The world-size record has its own version. The examined files use version `2`,
which includes 19 integer settings after the common text fields.

### Why duplicate values are kept

Some information appears in more than one layer. Turn, speed, world size, map
script, player names, and slot data can have both quick and archive forms.

The decoder keeps each serialized value in its original section. It does not
merge them or require them to agree. The layers serve different game systems,
and some values describe the active player while others describe lobby or
global setup. Keeping both values makes inconsistencies visible instead of
hiding them behind a precedence rule.

### Enum values and database values

Stable enums are returned as `IntEnum` values. Examples include quick game
mode, slot status, slot claim, archive game mode, and map type.

Database-dependent identifiers remain raw integers or serialized type-key
strings. A database row index can change when DLC or mods alter the effective
database. Returning an invented enum name would make the result appear more
certain than the bytes allow.

## Finding the compressed-data boundary

The first zlib offset is variable because the header contains variable-length
strings and arrays. There is no universal starting offset.

The decoder does not scan for `78 9C`. Those two bytes can occur naturally in
header data or later compressed bytes. Searching would also assume one zlib
compression level even though RFC 1950 permits other valid flag bytes.

Instead, the decoder:

1. Parses every supported header field in order.
2. Reads and validates the compression type.
3. Records the current position as the first chunk-length offset.
4. Reads the first `u32` chunk length.
5. Records the following position as the zlib offset.
6. Validates the first two bytes as an RFC 1950 header.
7. Walks every remaining length-prefixed chunk to physical EOF.

The relationship is:

```text
first_chunk_length_offset = zlib_offset - 4
```

The first zlib byte is at physical offsets `0x2A0E..0x2A85` in the multiplayer
fixtures and `0x2820` in the single-player comparison. These offsets vary with
the serialized header data.

The length words are container metadata. They are not part of the zlib stream.
A payload decompressor must concatenate only the chunk bodies before passing
them to zlib.

The header decoder validates chunk framing but does not decompress the bodies.
This keeps its responsibility limited to the physical header and container.

## Validation decisions

The decoder is deliberately strict. It rejects:

- A signature other than `CIV5`
- Unsupported outer, slot-hint, pregame, or world-info versions
- A build other than `403694`
- Invalid Boolean bytes
- Invalid stable enum values
- Invalid UTF-8 strings
- Counts that exceed the remaining bytes
- Slot arrays that do not contain exactly 64 entries
- A nonempty formal enabled-mod array
- An unsupported compression type
- Zero-length or truncated compressed chunks
- An invalid first RFC 1950 header
- Bytes that cannot be consumed as complete chunks through physical EOF

Strict version checks prevent a newer or older layout from being decoded with
the wrong field order. Returning a plausible but misaligned result would be
more dangerous than reporting that the version is unsupported.

Every error includes a field path and physical byte offset. This makes malformed
files easier to diagnose and supports further byte-layout research.

## Shared binary reader

The header, payload, plot, team, player, and free-list decoders use the same
bounded `LittleEndianReader`. It provides:

- Exact-length byte reads
- Signed and unsigned 8-, 16-, and 32-bit integers
- IEEE 754 32-bit floats
- Strict one-byte Booleans
- Length-prefixed UTF-8 strings
- Remaining-byte tracking
- Count-versus-buffer validation

Decoder-specific subclasses translate low-level failures into errors with the
right context. Header failures report a field path. Plot failures retain their
plot index and plot-relative behavior. Sharing primitive reads removes duplicate
bounds logic without weakening either decoder's public errors.

## Security and privacy

The pregame archive can contain passwords, email addresses, Steam IDs, a local
username, a save path, and an SMTP host. The decoder returns serialized values
faithfully; it does not redact them.

Applications should avoid logging or publishing the complete result. Select
only the fields needed for the task.

## Current limits

The decoder is not a universal Civilization V save parser. It currently does
not:

- Support other outer or archive versions
- Support builds other than `403694`
- Decode nonempty formal mod arrays
- Assign meanings to the preserved bridge spans
- Interpret decompressed payload structures as part of header parsing
- Treat quick-header player context as global game state

New compatibility should be added only with representative saves, confirmed
field boundaries, and regression tests for the complete physical chunk
sequence.
