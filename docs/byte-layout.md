# Civilization V save-file byte layout

This document records the byte layout confirmed from the available save files and
source code. It separates the physical `.CIV5SAVE` file from the decompressed
payload stored inside it.

The multiplayer evidence comes from 54 sequential Lekmod saves in
`test-save-file/multi-player`. Their headers identify the game as
`RacismLEKMOD v34.11`, running Civilization V build `1.0.3.279 (403694)` with
Lekmap v5.2. The single-player comparison is
`test-save-file/single-player/before_state.Civ5Save`.

All integer values described here are little-endian unless stated otherwise.
Offsets written as `+0xNN` are relative to the start of the containing record.

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

## Complete `.CIV5SAVE` file

The physical save contains an uncompressed header followed by a chunked zlib
stream. The header length is variable.

```text
physical file offset 0
├─ uncompressed Civilization V save header
│  ├─ "CIV5" magic
│  ├─ outer save version
│  ├─ game build and mod information
│  ├─ player and game setup strings
│  └─ other variable header data
└─ compressed payload chunks
   ├─ u32 compressed_chunk_length
   ├─ u8 compressed_chunk[compressed_chunk_length]
   ├─ u32 compressed_chunk_length
   ├─ u8 compressed_chunk[compressed_chunk_length]
   └─ repeat to physical end of file
```

### Confirmed header information

The exact offsets of all variable header fields are not yet mapped. The following
values are confirmed in every multiplayer save:

| Field | Value |
|---|---|
| Magic | `CIV5` |
| Outer save version | `8` |
| Game version | `1.0.3.279 (403694)` |
| Build | `403694 FINAL_RELEASE` |
| Mod identifier | `RacismLEKMOD v34.11` |
| Map script | `Assets\\Maps\\Lekmap v5.2\\LekmapPangaeaFractalv5.2.lua` |
| World size | `WORLDSIZE_TINY` |
| Game speed | `GAMESPEED_QUICK` |
| Handicap | `HANDICAP_IMMORTAL` |

The first zlib byte is `78 9C`. In the multiplayer dataset, its physical offset
is between `0x2A0E` and `0x2A85`. In the single-player comparison, it is at
`0x2820`.

The first chunk-length word is four bytes before the zlib header:

```text
first_chunk_length_offset = zlib_header_offset - 4
```

### Compressed chunk layout

Each chunk has this physical layout:

| Relative offset | Type | Meaning |
|---:|---|---|
| `+0x00` | `u32` | Compressed chunk-body length |
| `+0x04` | `u8[length]` | Compressed chunk body |

Most non-final chunk bodies are `0x10000` bytes. The final chunk is shorter.
There are 10 to 14 chunks in the multiplayer saves and 11 in the single-player
save.

The four-byte length words are container data. They are not part of the deflate
stream. A decoder must:

1. Start at `zlib_header_offset - 4`.
2. Read a `u32` chunk length.
3. Copy only that chunk body.
4. Repeat until the physical end of the file.
5. Concatenate the copied bodies in order.
6. Pass the combined bytes to one zlib decompressor.

Conceptual pseudocode:

```text
position = zlib_header_offset - 4
compressed_stream = empty bytes

while position < physical_file_size:
    length = read_u32(position)
    position += 4
    compressed_stream += read_bytes(position, length)
    position += length

payload = zlib_decompress(compressed_stream)
```

The decompressor can report `eof = false` even after all output is recovered.
Civilization V appears to store a flushed stream without the conventional zlib
end marker. Valid streams have no unused input and no unconsumed input.

Passing the complete physical tail directly to zlib incorrectly injects later
chunk-length words into the deflate stream. That mistake caused the former false
corruption report at decompressed offset `0x316B4F`.

## Decompressed payload

All offsets in this section are relative to the start of the decompressed
payload, not the physical save file.

The currently confirmed top-level order is:

```text
decompressed offset 0
├─ CvGame and variable game-level data
├─ u32 embedded SQLite length
├─ embedded SQLite database
├─ CvMap
│  ├─ fixed header and resource arrays
│  ├─ CvPlot[map width × map height]
│  ├─ CvArea free-list
│  ├─ CvLandmass free-list
│  └─ i32 AI map hints
├─ CvTeam[64]
├─ CvPlayer[0]
└─ remaining variable player, AI, diplomacy, treasury, city, unit,
   and other game objects
```

The exact continuous layout is known through all 64 `CvTeam` records. The
`CvPlayer` prefix is partly decoded, but the complete variable player record and
the records after it are not yet bounded.

### `CvGame`

`CvGame` begins at decompressed offset zero. Its complete serialized length is
variable.

Confirmed fields:

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

Selected validation values:

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

The embedded SQLite signature is the reliable anchor for locating the end of the
variable game-level section.

### Embedded SQLite database

The database is stored immediately before `CvMap`:

```text
u32 sqlite_length = 0xC00
u8 sqlite_database[0xC00]
CvMap
```

Anchor formulas:

```text
sqlite_length_offset = sqlite_signature_offset - 4
CvMap_offset          = sqlite_signature_offset + 0xC00
first_plot_offset     = CvMap_offset + 0x3CA
```

The database is identical in every examined save:

| Property | Value |
|---|---|
| Length | `3072` bytes, `0xC00` |
| SHA-256 | `1b36fbd3619715451a12ee39ca42b0588ff9f749ec9e1a784dd7cc206c685912` |
| Page size | `1024` |
| Page count | `3` |
| Integrity check | `ok` |
| Table | `SimpleValues(Name TEXT Primary Key, Value VARIANT)` |
| Table rows | `0` |

### `CvMap`

The multiplayer maps are `48 × 42`, giving 2,016 serialized plots.

#### Fixed map header

| Offset | Type | Meaning | Multiplayer value |
|---:|---|---|---:|
| `+0x00` | `u32` | Version | `1` |
| `+0x04` | `i32` | Width | `48` |
| `+0x08` | `i32` | Height | `42` |
| `+0x0C` | `i32` | Land-plot count | `760` |
| `+0x10` | `i32` | Owned-plot count | Variable |
| `+0x14` | `i32` | Natural-wonder count | `3` |
| `+0x18` | `i32` | Top latitude | `90` |
| `+0x1C` | `i32` | Bottom latitude | `-90` |
| `+0x20` | `bool` | Wrap X | `1` |
| `+0x21` | `bool` | Wrap Y | `0` |
| `+0x22` | 16 bytes | Map GUID | Changes at the resync |
| `+0x32` | variable | Total-resource hashed array | `0x1CC` bytes |
| `+0x1FE` | variable | Land-resource hashed array | `0x1CC` bytes |
| `+0x3CA` | `CvPlot` | First plot | Version `7` |

Each resource array has this structure:

```text
u32 entry_count = 57
repeat 57 times:
    u32 type_hash
    i32 value
```

All 57 hashes are nonzero in both arrays. Each complete array is `0x1CC`
bytes.

#### `CvPlot` array

Plots are serialized in row-major coordinate order:

```text
x = plot_index % map_width
y = plot_index // map_width
```

All 108,864 multiplayer plot instances were checked, and every coordinate
matched this rule.

`CvPlot` is a variable-length record. Its minimum confirmed length in Lekmod
v34.11 is `0x625` bytes. Only the decoder-relevant anchors currently confirmed
inside the record are listed below. The unnamed ranges still contain fixed plot
fields described by `CvPlot::write`, but they have not all been assigned names in
this document.

| Offset | Type | Meaning |
|---:|---|---|
| `+0x00` | `u32` | Plot serialization version, `7` |
| `+0x56` | `IDInfo` | Plot city: owner and city ID |
| `+0x5E` | `IDInfo` | Working-city or city-catchment assignment |
| `+0x563` | `bool` | Has script data |
| `+0x564` | `i32` | Outer build-progress count |

No examined plot has script data.

When the build-progress count is zero, the fixed tail continues as follows:

| Offset | Type | Meaning |
|---:|---|---|
| `+0x568` | `i16[80]` | Invisible-visibility values |
| `+0x608` | `u32` | Plot unit-reference count |
| variable | `IDInfo[count]` | Owner and ID for each unit on the plot |
| variable | `i8` | Continent |
| variable | 24 bytes | `CvArchaeologyData`, version `2` |

When build progress is present, the observed structure has outer count `70`,
inner count `70`, 68 nonzero hashes, and two zero hashes. It adds exactly
`0x1A4` bytes:

```text
4 + (70 × 4) + (68 × 2) = 420 bytes = 0x1A4
```

Each unit reference adds eight bytes. The highest observed unit-reference count
is four.

| Plot length | Meaning |
|---:|---|
| `0x625` | Base record |
| `0x62D` | Base plus one unit |
| `0x635` | Base plus two units |
| `0x63D` | Base plus three units |
| `0x645` | Base plus four units |
| `0x7C9` | Build progress |
| `0x7D1` | Build progress plus one unit |
| `0x7D9` | Build progress plus two units |

There is no unknown four-byte plot extension. The four bytes missing from an
earlier size calculation are the serialized `m_uiTradeRouteBitFlags` field in
the fixed plot prefix.

Because plot records are variable, a decoder must parse each plot in sequence.
It must not calculate a later plot from a fixed record size.

#### `CvArea` free-list

The area free-list starts immediately after the final plot. It always occupies
`0x34BCA` bytes in the multiplayer dataset.

Free-list metadata is `0x118` bytes:

| Field | Value |
|---|---:|
| Number of slots | `64` |
| Last index | `44` |
| Free-list head | `-1` |
| Free-list count | `0` |
| Live-object count | `45` |

There are 45 live `CvArea` objects. Each is 4,794 bytes, or `0x12BA`:

```text
u32 version = 1
10 × i32 area counters
4 × i32 boundaries
2 × bool flags
5 × i32[80] player or team arrays
64 × IDInfo
64 × i32[7] yield modifiers
hashed resource array:
    count = 57
    57 nonzero hash/value entries
hashed improvement array:
    count = 46
    45 nonzero hash/value entries
    1 zero hash
```

#### `CvLandmass` free-list

The landmass free-list follows the area free-list. It always occupies `0x2A8`
bytes in the multiplayer dataset.

Its metadata is `0x98` bytes:

| Field | Value |
|---|---:|
| Number of slots | `32` |
| Last index | `23` |
| Free-list head | `-1` |
| Free-list count | `0` |
| Live-object count | `24` |

Each of the 24 live landmass objects is 22 bytes, or `0x16`:

| Relative field order | Type | Meaning |
|---:|---|---|
| 1 | `u32` | Version |
| 2 | `i32` | ID |
| 3 | `i32` | Tile count |
| 4 | `i32` | Centroid X total |
| 5 | `i32` | Centroid Y total |
| 6 | `bool` | Water |
| 7 | `i8` | Continent type |

#### End of `CvMap`

The landmass list is followed by one `i32` AI-map-hints value. It is zero in all
examined saves.

```text
CvMap_end = final_plot_end
          + 0x34BCA  CvArea free-list
          + 0x002A8  CvLandmass free-list
          + 0x00004  AI map hints
          = final_plot_end + 0x34E76
```

### `CvTeam[64]`

Exactly 64 consecutive serialized `CvTeam` objects follow `CvMap`. This is a
useful array model for decoding, but these are serialized C++ objects rather
than copies of their in-memory structs.

Each team record is exactly `0x3424` bytes in all examined Lekmod v34.11
multiplayer saves, including inactive team slots:

```text
CvTeam[i]   = CvMap_end + (i × 0x3424)
CvPlayer[0] = CvMap_end + (64 × 0x3424)
            = CvMap_end + 0xD0900
```

This fixed size is proven for this Lekmod v34.11 dataset. It must not be assumed
for vanilla Civilization V or another mod version without validation.

Confirmed team fields:

| Offset | Type | Meaning |
|---:|---|---|
| `+0x00` | `u32` | Team serialization version, `1` |
| `+0x10` | `i32` | City count |
| `+0x14` | `i32` | Population |
| `+0x18` | `i32` | Land |
| `+0x78` | `bool[8]` | Eight team flags begin here |
| `+0x84` | `i32` | Team ID |
| `+0x88` | `i32` | Current era |
| `+0x1E0C` | variable | `CvTeamTechs` begins |

#### `CvTeamTechs`

Known order relative to the containing `CvTeam`:

```text
+0x1E0C  u32 version
+0x1E10  i32 last_technology
+0x1E14  i32 technology_count = 81
         u32 technology_hash[81]
         bool has_technology[81]
         bool no_trade_technology[81]
         bool has_technology_by_human[81]
         bool has_technology_for_league[81]
+0x20A0  i32 research_progress[81]
         technology-count data
```

Research progress is stored in hundredths. Lekmod serializes four 81-byte
Boolean arrays here. Assuming the two arrays used by an unmodified layout makes
the following fields appear 162 bytes too early.

The preceding hash vector must be used to identify technologies. Runtime XML
indices must not be assumed to be stable.

### `CvPlayer`

The exact start of `CvPlayer[0]` follows from the fixed team array. The complete
player record is variable-length and has not yet been structurally bounded.

Confirmed prefix fields for Player 0:

| Offset | Type | Meaning |
|---:|---|---|
| `+0x00` | `u32` | Player serialization version, `16` |
| `+0x04` | `i32` | Starting X; observed Player 0 value `11` |
| `+0x08` | `i32` | Starting Y; observed Player 0 value `16` |
| `+0x0C` | `i32` | Population |
| `+0x10` | `i32` | Land |
| `+0x14` | `i32` | Scored land |
| `+0x24` | `i32` | Current culture, multiplied by 100 |
| `+0x28` | `i32` | Lifetime culture, multiplied by 100 |
| `+0x38` | `i32` | Current faith |
| `+0x3C` | `i32` | Lifetime faith |

Player 0 population and land match Team 0 throughout the sequential saves.

Later player starts can currently be detected with an alignment-aware candidate
signature:

```text
u32 version = 16
i32 starting_x
i32 starting_y
i32 team_population
i32 team_land
i32 scored_land
```

This is a useful validation method, but it does not replace parsing the complete
preceding player record.

Map plots provide additional player-related information before the complete
player layout is known:

- Plot city `IDInfo` gives a city owner, city ID, and map coordinate.
- Plot unit references give unit owners, unit IDs, and map coordinates.
- Plot unit references do not identify unit types.
- A plot's working-city field assigns the plot to a city catchment. Actual
  worked citizens are stored in `CvCityCitizens`.

### Selected decompressed validation offsets

These offsets can be used as regression tests. `CvTeam[0]` begins at `CvMap`
end.

| Save | `CvMap` start | First plot | Final plot end | `CvMap` end / Team 0 | Player 0 |
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

### Known and unknown coverage

For the multiplayer payloads:

- The exact continuous layout through `CvMap` covers about 22% to 24%.
- The exact continuous layout through all 64 teams covers about 28% to 30%.
- Approximately 70% to 72% remains without continuous byte boundaries.

The beginning of `CvPlayer` is partly decoded. The following later structures
still need reliable byte boundaries and conditional-length rules:

- The remainder of each `CvPlayer` record
- Most player AI subobjects
- Diplomacy state
- `CvTreasury`
- City free-lists and complete `CvCity` records
- Unit free-lists and complete `CvUnit` records
- Later top-level objects near the end of the payload

The source describes `CvTreasury::Write` as version `1` followed by 12 `i32`
fields, with gold first. Its absolute offset is not yet known because it follows
several variable-length AI objects. Raw byte differences must not be labelled as
gold or another field until the preceding structures are parsed.

### Decoder cautions

- Remove every physical chunk-length prefix before zlib decompression.
- Parse plots sequentially because their build-progress and unit-reference tails
  are variable.
- Use serialized hashes to identify XML-backed types. Do not rely on runtime row
  indices.
- Treat the Resync save as another snapshot of turn 64, not turn 65.
- Treat the standalone turn-70 autosave and Post turn 70 as distinct snapshots.
- A resync can regenerate map GUIDs and landmass IDs without changing the logical
  game turn.
- Do not apply the observed Lekmod team size to another game or mod version
  without testing it.
