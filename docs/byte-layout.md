# Civilization V save-file and payload layout

This document gives the top-level layout of the examined save files. Detailed
record layouts have one canonical home and are linked from each section.

The main evidence is 54 sequential Lekmod v34.11 multiplayer saves and one
single-player comparison save. The multiplayer headers identify Civilization V
build `1.0.3.279 (403694)`, Lekmap v5.2, and the game name

All confirmed integers are little-endian. Offsets written as `+0xNN` are
relative to the containing record. Other offsets are relative to the start of
the physical file or decompressed payload, as stated.

## Type notation

| Name | Size | Meaning |
|---|---:|---|
| `u8` | 1 byte | Unsigned byte |
| `i8` | 1 byte | Signed byte |
| `bool` | 1 byte | Serialized Boolean |
| `i16` | 2 bytes | Signed 16-bit integer |
| `u32` | 4 bytes | Unsigned 32-bit integer |
| `i32` | 4 bytes | Signed 32-bit integer |
| `IDInfo` | 8 bytes | Two `i32` values: owner and object ID |

## Physical file

A `.CIV5SAVE` file contains a variable-length uncompressed header followed by
a chunked zlib stream:

```text
physical offset 0
├─ uncompressed save header
└─ compressed payload chunks
   ├─ u32 chunk length
   ├─ u8 chunk body[chunk length]
   └─ repeated to physical EOF
```

The header must be parsed in serialization order because variable-length
strings and arrays make the first zlib offset variable. See the
[physical header format](civ5-header-format.md) for the header fields, supported
versions, and boundary validation.

### Compressed chunks

Each physical chunk contains a four-byte length followed by that many body
bytes. Most non-final bodies are `0x10000` bytes; the final body is shorter.
The examined multiplayer saves contain 10 to 14 chunks, and the single-player
comparison contains 11.

The length words are container metadata, not part of the zlib stream. A
decompressor must join only the chunk bodies and pass the combined bytes to one
zlib decompressor:

```text
position = first_zlib_offset - 4
compressed_stream = empty bytes

while position < physical_file_size:
    length = read_u32(position)
    position += 4
    compressed_stream += read_bytes(position, length)
    position += length

payload = zlib_decompress(compressed_stream)
```

The examined streams may omit the conventional zlib end marker. A valid saved
stream can therefore report `eof = false` after producing all output, but it
must have no unused or unconsumed input.

Passing the complete physical tail directly to zlib injects later chunk-length
words into the stream. This caused an earlier false corruption report at
decompressed offset `0x316B4F`.

## Decompressed payload

Offsets in this section are relative to decompressed offset zero.

```text
decompressed offset 0
├─ CvGame and variable game-level data
├─ u32 embedded SQLite length
├─ embedded SQLite database
├─ CvMap
│  ├─ map header and resource arrays
│  ├─ CvPlot[width × height]
│  ├─ CvArea free-list
│  ├─ CvLandmass free-list
│  └─ i32 AI map hints
├─ CvTeam[64]
├─ CvPlayer[64]
│  ├─ player and AI fields
│  ├─ CvCityAI free-list
│  ├─ CvUnit free-list
│  ├─ CvArmyAI free-list
│  └─ remaining player fields
└─ remaining top-level game objects
```

The layout is continuously known through all 64 team records. All 64 player
records and their three object free lists can also be bounded, although many
fields within those ranges are not decoded.

### `CvGame`

`CvGame` begins at offset zero and has a variable serialized length. These
fields are confirmed:

| Offset | Type | Meaning | Observed value or rule |
|---:|---|---|---|
| `+0x00` | `u32` | Serialization version | `1` |
| `+0x08` | `i32` | Elapsed turn | Matches the save turn |
| `+0x0C` | `i32` | Start turn | `0` |
| `+0x10` | `i32` | Winning turn | `0` |
| `+0x14` | `i32` | Starting year | `-4000` |
| `+0x18` | `i32` | Estimated end turn | `330` |
| `+0x28` | `i32` | Total city count | Changes over time |
| `+0x2C` | `i32` | Total population | Changes over time |

Selected fixture values are:

| Save | Elapsed turn | Cities | Population |
|---|---:|---:|---:|
| Initial turn 0 | 0 | 0 | 0 |
| Post turn 0 | 0 | 7 | 7 |
| Post turn 27 | 27 | 10 | 37 |
| Post turn 40 | 40 | 19 | 66 |
| Post turn 50 | 50 | 19 | 88 |
| Post turn 64 | 64 | 19 | 119 |
| Post turn 70 | 70 | 19 | 140 |
| Post turn 76 | 76 | 19 | 143 |

The embedded SQLite signature is the reliable anchor for the end of the
variable game-level section. Raw byte differences before that anchor must not
be assigned field names until the preceding source-order structures are known.

### Embedded SQLite database

The database is stored immediately before `CvMap`:

```text
u32 sqlite_length = 0xC00
u8 sqlite_database[0xC00]
CvMap
```

Useful anchor formulas are:

```text
sqlite_length_offset = sqlite_signature_offset - 4
CvMap_offset          = sqlite_signature_offset + 0xC00
first_plot_offset     = CvMap_offset + 0x3CA
```

The database is identical in the examined saves:

| Property | Value |
|---|---|
| Length | `3072` bytes (`0xC00`) |
| SHA-256 | `1b36fbd3619715451a12ee39ca42b0588ff9f749ec9e1a784dd7cc206c685912` |
| Page size | `1024` |
| Page count | `3` |
| Integrity check | `ok` |
| Table | `SimpleValues(Name TEXT Primary Key, Value VARIANT)` |
| Rows | `0` |

### `CvMap` and `CvPlot`

`CvMap` contains the map dimensions, two hashed resource arrays, a variable
`CvPlot` record for every tile, two object free lists, and the AI map-hints
value. Plot records must be parsed in sequence because their build-progress and
unit-reference sections are variable.

See [`CvMap` and `CvPlot` byte layout](map-information.md) for confirmed fields,
enum values, hash rules, version differences, and source references. See the
[`CvPlot` API guide](cv-plot-decoder.md) for public result types and errors.

### `CvTeam[64]`

Exactly 64 `CvTeam` records follow `CvMap`. Each record is `0x3424` bytes in
the examined v34.11 saves, but database catalogue counts and optional vectors
can change that length in another layout.

See the [`CvTeam` byte layout](team-information.md) and
[`CvTeam` API guide](cv-team-decoder.md).

### `CvPlayer[64]`

Exactly 64 variable-length `CvPlayerAI` records follow the teams. The decoder
bounds each player by validating its version prefix and the city, unit, and
army free lists. It exposes confirmed player fields, live cities, live units,
and city building inventories.

See the [`CvPlayer`, `CvCity`, and `CvUnit` byte layout](player-information.md)
and [`CvPlayer` API guide](cv-player-decoder.md).

## Selected validation offsets

These decompressed offsets are fixture evidence and useful regression values.
They are not fixed offsets for other saves.

| Save | `CvMap` | First plot | Final plot end | Team 0 | Player 0 |
|---|---:|---:|---:|---:|---:|
| Initial turn 0 | `0x30C7` | `0x3491` | `0x309841` | `0x33E6B7` | `0x40EFB7` |
| Post turn 0 | `0x33F6` | `0x37C0` | `0x309B38` | `0x33E9AE` | `0x40F2AE` |
| Post turn 27 | `0x428E` | `0x4658` | `0x30BFBC` | `0x340E32` | `0x411732` |
| Post turn 50 | `0x6921` | `0x6CEB` | `0x31625B` | `0x34B0D1` | `0x41B9D1` |
| Post turn 64 | `0x71A8` | `0x7572` | `0x31C42A` | `0x3512A0` | `0x421BA0` |
| Resync | `0x71A8` | `0x7572` | `0x31C432` | `0x3512A8` | `0x421BA8` |
| Turn-70 autosave | `0x7B35` | `0x7EFF` | `0x31DB17` | `0x35298D` | `0x42328D` |
| Post turn 70 | `0x7B5B` | `0x7F25` | `0x31DE6D` | `0x352CE3` | `0x4235E3` |
| Post turn 76 | `0x7F95` | `0x835F` | `0x31F9C7` | `0x35483D` | `0x42513D` |

## Known limits

For the examined multiplayer payloads, the continuous source-order layout
through `CvMap` covers about 22% to 24% of the payload. Extending through all
64 teams covers about 28% to 30%. The following 64 player records have known
outer and free-list boundaries but not complete source-order field mappings.

The following regions still need complete source-order decoding:

- most fields inside each bounded `CvPlayer` record
- most player AI objects, diplomacy state, and `CvTreasury`
- city citizens and fields after the confirmed city prefix
- building yield changes and Great Work assignments
- unit promotions, missions, and fields after the confirmed unit prefix
- `CvArmyAI` entries
- later top-level objects near the end of the payload

`CvTreasury::Write` is known from source to write version `1` followed by 12
`i32` fields, with gold first. Its absolute offset is not confirmed because it
follows variable player and AI objects.

## Decoder cautions

- Remove every physical chunk-length prefix before zlib decompression.
- Parse plots sequentially; do not assume a fixed record size.
- Use serialized hashes for XML-backed types instead of runtime row indexes.
- Treat the resync save as another turn-64 snapshot, not turn 65.
- Treat the standalone turn-70 autosave and Post turn 70 as separate snapshots.
- Do not apply observed Lekmod record sizes to another game or mod version
  without representative saves and regression tests.
