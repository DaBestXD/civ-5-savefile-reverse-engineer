<!-- markdownlint-disable -->
# `CvMap` and `CvPlot` byte layout

This document is the canonical byte-layout reference for `CvMap`, `CvPlot`,
`CvArea`, and `CvLandmass` in the examined Lekmod v34.11 saves. For the public
Python API, see the [`CvPlot` decoder guide](cv-plot-decoder.md).

## `CvMap` container

The examined multiplayer maps are 48 tiles wide and 42 tiles high. Each map
therefore contains 2,016 plots. Dimensions and counts are serialized and must
not be assumed for other saves.

### Fixed header

| Offset | Type | Meaning | Examined multiplayer value |
|---:|---|---|---:|
| `+0x000` | `u32` | Version | `1` |
| `+0x004` | `i32` | Width | `48` |
| `+0x008` | `i32` | Height | `42` |
| `+0x00C` | `i32` | Land-plot count | `760` |
| `+0x010` | `i32` | Owned-plot count | Variable |
| `+0x014` | `i32` | Natural-wonder count | `3` |
| `+0x018` | `i32` | Top latitude | `90` |
| `+0x01C` | `i32` | Bottom latitude | `-90` |
| `+0x020` | `bool` | Wrap X | `true` |
| `+0x021` | `bool` | Wrap Y | `false` |
| `+0x022` | 16 bytes | Map GUID | Changes at the resync |
| `+0x032` | variable | Total-resource hashed array | `0x1CC` bytes |
| `+0x1FE` | variable | Land-resource hashed array | `0x1CC` bytes |
| `+0x3CA` | `CvPlot` | First plot | Version `7` |

Each resource array contains a count followed by hash-and-value pairs:

```text
u32 entry_count = 57
repeat 57 times:
    u32 resource_type_hash
    i32 value
```

All 57 hashes are nonzero in both arrays in the examined saves.

## `CvPlot` records

`CvMap` stores one sequential `CvPlot` object for each map tile. The plots are
stored in row-major order:

```text
plot_index = (y * map_width) + x
```

All 108,864 plot instances in the multiplayer dataset match this coordinate
order.

A `CvPlot` has no null terminator and no fixed size. Its end is calculated by
reading its counts and the data controlled by those counts. The following tree
shows the currently confirmed structure. "Unknown" means that the field is
known conceptually, but its exact offset or byte length has not yet been
confirmed. `CvPlot` 'end' is after `CvArchaeologyData`.

Lekmod v34.11 commit `f4b96af9200470ab8fe50dee3dad0dce89c16975`
contains the modified version 7 reader and writer. Its compact types and field
order match the examined saves. Compared with Firaxis Expansion 2, Lekmod adds
two one-byte flags and a seventh 2-byte yield.

`CvPlot` [variable length]<br>
├─ version<br>
│&nbsp;&nbsp;├─ offset: `+0x000`<br>
│&nbsp;&nbsp;├─ type: `u32`<br>
│&nbsp;&nbsp;└─ length: 4 bytes<br>
├─ coordinates<br>
│&nbsp;&nbsp;├─ X<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;├─ offset: `+0x004`<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;├─ type: `i16`<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;└─ length: 2 bytes<br>
│&nbsp;&nbsp;└─ Y<br>
│&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;├─ offset: `+0x006`<br>
│&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;├─ type: `i16`<br>
│&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;└─ length: 2 bytes<br>
├─ fixed counters and state<br>
│&nbsp;&nbsp;├─ area<br>
│&nbsp;&nbsp;├─ feature variety<br>
│&nbsp;&nbsp;├─ ownership and improvement durations<br>
│&nbsp;&nbsp;├─ upgrade progress and culture<br>
│&nbsp;&nbsp;├─ reveal, city-radius, recon, and river-crossing counts<br>
│&nbsp;&nbsp;├─ resource quantity<br>
│&nbsp;&nbsp;├─ builder scratch values<br>
│&nbsp;&nbsp;├─ landmass<br>
│&nbsp;&nbsp;└─ trade-route bit flags<br>
├─ fourteen serialized flags [`+0x02B..+0x038`]<br>
│&nbsp;&nbsp;├─ type: `bool`<br>
│&nbsp;&nbsp;├─ length: 1 byte each, 14 bytes total<br>
│&nbsp;&nbsp;├─ starting plot and hills<br>
│&nbsp;&nbsp;├─ northeast, west, and northwest river-edge flags<br>
│&nbsp;&nbsp;├─ potential city work<br>
│&nbsp;&nbsp;├─ improvement pillaged<br>
│&nbsp;&nbsp;├─ route pillaged<br>
│&nbsp;&nbsp;├─ route was previously pillaged: `+0x033`<br>
│&nbsp;&nbsp;├─ barbarian-camp conversion control<br>
│&nbsp;&nbsp;├─ rough feature<br>
│&nbsp;&nbsp;├─ resource-linked city active<br>
│&nbsp;&nbsp;├─ improved by a major-civilization gift<br>
│&nbsp;&nbsp;└─ forced fresh water: `+0x038`<br>
├─ tile identity and contents<br>
│&nbsp;&nbsp;├─ owner<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;├─ offset: `+0x039`<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;├─ type: `i8` player ID<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;├─ length: 1 byte<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;└─ `-1`: no owner<br>
│&nbsp;&nbsp;├─ plot type<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;├─ offset: `+0x03A`<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;├─ type: `i8` enum<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;└─ length: 1 byte<br>
│&nbsp;&nbsp;├─ terrain<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;├─ examples: grassland, plains, desert<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;├─ offset: `+0x03B`<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;├─ type: `i8` enum<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;└─ length: 1 byte<br>
│&nbsp;&nbsp;├─ feature<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;├─ examples: forest, jungle, marsh<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;├─ offset: `+0x03C`<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;├─ type: 32-bit database type hash<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;└─ length: 4 bytes<br>
│&nbsp;&nbsp;├─ resource<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;├─ examples: wheat, iron, gold<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;├─ offset: `+0x040`<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;├─ type: 32-bit database type hash<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;└─ length: 4 bytes<br>
│&nbsp;&nbsp;├─ improvement<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;├─ examples: farm, mine, trading post<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;├─ offset: `+0x044`<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;├─ type: 32-bit database type hash<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;└─ length: 4 bytes<br>
│&nbsp;&nbsp;├─ under-construction improvement<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;├─ offset: `+0x048`<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;├─ type: 32-bit database type hash<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;└─ length: 4 bytes<br>
│&nbsp;&nbsp;├─ player that built the improvement: `+0x04C`, `i8`<br>
│&nbsp;&nbsp;├─ player responsible for improvement: `+0x04D`, `i8`<br>
│&nbsp;&nbsp;├─ player responsible for route: `+0x04E`, `i8`<br>
│&nbsp;&nbsp;├─ player that cleared the camp: `+0x04F`, `i8`<br>
│&nbsp;&nbsp;├─ route<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;├─ offset: `+0x050`<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;├─ type: `i8` enum<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;└─ length: 1 byte<br>
│&nbsp;&nbsp;├─ world anchor: `+0x051`, `i8`<br>
│&nbsp;&nbsp;├─ anchor data: `+0x052`, `i8`<br>
│&nbsp;&nbsp;└─ river flow directions<br>
│&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;├─ east edge: `+0x053`, `i8`<br>
│&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;├─ southeast edge: `+0x054`, `i8`<br>
│&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;└─ southwest edge: `+0x055`, `i8`<br>
├─ city-center `IDInfo`<br>
│&nbsp;&nbsp;├─ offset: `+0x056`<br>
│&nbsp;&nbsp;├─ owner: `i32` [4 bytes]<br>
│&nbsp;&nbsp;├─ city ID: `i32` [4 bytes]<br>
│&nbsp;&nbsp;└─ length: 8 bytes<br>
├─ working-city/catchment `IDInfo`<br>
│&nbsp;&nbsp;├─ offset: `+0x05E`<br>
│&nbsp;&nbsp;├─ owner: `i32` [4 bytes]<br>
│&nbsp;&nbsp;├─ city ID: `i32` [4 bytes]<br>
│&nbsp;&nbsp;└─ length: 8 bytes<br>
├─ working-city override `IDInfo`<br>
│&nbsp;&nbsp;├─ offset: `+0x066`<br>
│&nbsp;&nbsp;└─ length: 8 bytes<br>
├─ resource-linked city `IDInfo`<br>
│&nbsp;&nbsp;├─ offset: `+0x06E`<br>
│&nbsp;&nbsp;└─ length: 8 bytes<br>
├─ purchase city `IDInfo`<br>
│&nbsp;&nbsp;├─ offset: `+0x076`<br>
│&nbsp;&nbsp;└─ length: 8 bytes<br>
├─ fixed arrays<br>
│&nbsp;&nbsp;├─ yields<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;├─ Lekmod offset: `+0x07E`<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;├─ type: `i16[7]`<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;├─ length: 14 bytes<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;└─ order: food, production, gold, science, culture, faith, Golden Age Points<br>
│&nbsp;&nbsp;├─ found values by player: `+0x08C`, `i32[80]` [320 bytes]<br>
│&nbsp;&nbsp;├─ city-radius counts by player: `+0x1CC`, `i8[80]` [80 bytes]<br>
│&nbsp;&nbsp;├─ visibility counts by team: `+0x21C`, `i16[80]` [160 bytes]<br>
│&nbsp;&nbsp;├─ revealed owners by team: `+0x2BC`, `i8[80]` [80 bytes]<br>
│&nbsp;&nbsp;├─ river-crossing byte: `+0x30C`, `i8` [1 byte]<br>
│&nbsp;&nbsp;├─ revealed bits: `+0x30D`, `u32[4]` [16 bytes]<br>
│&nbsp;&nbsp;├─ force-revealed resources: `+0x31D`, `bool[80]` [80 bytes]<br>
│&nbsp;&nbsp;├─ revealed improvements: `+0x36D`, `u32 hash[80]` [320 bytes]<br>
│&nbsp;&nbsp;├─ revealed routes: `+0x4AD`, `i16[80]` [160 bytes]<br>
│&nbsp;&nbsp;└─ no-settling flags: `+0x54D`, `bool[22]` [22 bytes]<br>
├─ `has_script_data`<br>
│&nbsp;&nbsp;├─ offset: `+0x563`<br>
│&nbsp;&nbsp;├─ type: `bool`<br>
│&nbsp;&nbsp;├─ length: 1 byte<br>
│&nbsp;&nbsp;├─ observed value: `false`<br>
│&nbsp;&nbsp;└─ when true: a streamed `std::string` follows; its framing is not yet confirmed<br>
├─ `outer_build_count`<br>
│&nbsp;&nbsp;├─ offset without script data: `+0x564`<br>
│&nbsp;&nbsp;├─ type: `i32`<br>
│&nbsp;&nbsp;├─ length: 4 bytes<br>
│&nbsp;&nbsp;└─ observed values: 0 or 70<br>
├─ build-progress data [conditional]<br>
│&nbsp;&nbsp;├─ present when: `outer_build_count = 70`<br>
│&nbsp;&nbsp;├─ inner count: `i32` [4 bytes], observed value 70<br>
│&nbsp;&nbsp;├─ entries are interleaved in slot order<br>
│&nbsp;&nbsp;├─ each entry starts with a 4-byte build hash<br>
│&nbsp;&nbsp;├─ a nonzero hash is immediately followed by `i16` progress<br>
│&nbsp;&nbsp;├─ observed hashes: 68 nonzero and 2 zero<br>
│&nbsp;&nbsp;└─ total added length: `0x1A4` bytes (420 bytes)<br>
├─ `invisible_visibility`<br>
│&nbsp;&nbsp;├─ type: `i16[80]`<br>
│&nbsp;&nbsp;├─ length: `0x0A0` bytes (160 bytes)<br>
│&nbsp;&nbsp;├─ offset without build progress: `+0x568`<br>
│&nbsp;&nbsp;└─ offset with build progress: `+0x70C`<br>
├─ `plot_unit_count`<br>
│&nbsp;&nbsp;├─ type: `u32`<br>
│&nbsp;&nbsp;├─ length: 4 bytes<br>
│&nbsp;&nbsp;├─ offset without build progress: `+0x608`<br>
│&nbsp;&nbsp;└─ offset with build progress: `+0x7AC`<br>
├─ unit `IDInfo` array [`plot_unit_count` entries]<br>
│&nbsp;&nbsp;├─ each entry<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;├─ owner: `i32` [4 bytes]<br>
│&nbsp;&nbsp;│&nbsp;&nbsp;└─ unit ID: `i32` [4 bytes]<br>
│&nbsp;&nbsp;└─ total length: `plot_unit_count * 8` bytes<br>
├─ continent<br>
│&nbsp;&nbsp;├─ type: `i8`<br>
│&nbsp;&nbsp;└─ length: 1 byte<br>
└─ `CvArchaeologyData`<br>
&nbsp;&nbsp;&nbsp;├─ version: `u32` [4 bytes], observed value 2<br>
&nbsp;&nbsp;&nbsp;├─ artifact type: 4 bytes<br>
&nbsp;&nbsp;&nbsp;├─ era: 4 bytes<br>
&nbsp;&nbsp;&nbsp;├─ player 1: 4 bytes<br>
&nbsp;&nbsp;&nbsp;├─ player 2: 4 bytes<br>
&nbsp;&nbsp;&nbsp;├─ work: 4 bytes [version 2 and later]<br>
&nbsp;&nbsp;&nbsp;├─ version 1 length: `0x14` bytes (20 bytes)<br>
&nbsp;&nbsp;&nbsp;├─ version 2 length: `0x18` bytes (24 bytes)<br>
&nbsp;&nbsp;&nbsp;└─ final field in `CvPlot`

### Enum values

The plot type, terrain, route, and flow-direction fields are numeric enums, not
database hashes.

| Value | Plot type | Terrain | Route | Flow direction |
|---:|---|---|---|---|
| `-1` | None | None | None | None |
| `0` | Mountain | Grass | Road | North |
| `1` | Hills | Plains | Railroad | Northeast |
| `2` | Land | Desert | — | Southeast |
| `3` | Ocean | Tundra | — | South |
| `4` | — | Snow | — | Southwest |
| `5` | — | Coast | — | Northwest |
| `6` | — | Ocean | — | — |
| `7` | — | Mountain | — | — |
| `8` | — | Hill | — | — |

### Hashed type fields

Version 7 stores feature, resource, improvement, under-construction
improvement, and revealed-improvement values as 32-bit hashes. A zero hash
means no type. The writer hashes the database `Type` string, and the reader
resolves the hash through `GC.getInfoTypeForHash`.

For example, a completed farm is represented by the hash of
`IMPROVEMENT_FARM`. A decoder needs a hash-to-`Type` lookup built from the exact
game and mod database.

Lekmod uses Firaxis CRC32 over the ASCII bytes of the exact type name, excluding
the null terminator. The practical formula is:

```python
hash_value = (~zlib.crc32(type_name.encode("ascii"))) & 0xffffffff
```

Confirmed calculated examples are:

| Type string | Hash | Little-endian bytes |
|---|---:|---|
| `IMPROVEMENT_FARM` | `0x0A0929B1` | `B1 29 09 0A` |
| `BUILD_FARM` | `0x6ACB706B` | `6B 70 CB 6A` |
| `FEATURE_FOREST` | `0x0A220944` | `44 09 22 0A` |
| `RESOURCE_WHEAT` | `0x2E1008E0` | `E0 08 10 2E` |

The v34.11 database contains 9 terrains, 25 features, 57 resources, 45
improvements, 2 routes, and 68 builds. Build IDs occupy slots `0..69`, with IDs
45 and 46 missing. Improvement ID 27 is also missing. A general decoder should
hash every `Type` string from the exact effective database and construct a
reverse lookup instead of relying only on this version's catalogue.

### Expansion 2 and Lekmod differences

Lekmod v34.11 contains its modified DLL source directly under `LEKMOD_DLL`.
Compared with the Firaxis Expansion 2 version 7 writer, it adds two serialized
booleans and one yield.

| Field | Expansion 2 offset or count | Lekmod offset or count | Difference |
|---|---:|---:|---|
| Serialized flags | 12 | 14 | Lekmod adds `m_bWasRoutePillaged` and `m_bIsSetFreshWater` |
| Plot owner | `+0x037` | `+0x039` | Shifted by two added flags |
| River-flow bytes | `+0x051..+0x053` | `+0x053..+0x055` | Shifted by two added flags |
| Plot-city `IDInfo` | `+0x054` | `+0x056` | Shifted by two added flags |
| Working-city `IDInfo` | `+0x05C` | `+0x05E` | Shifted by two added flags |
| Yield count | 6 | 7 | Lekmod adds one 2-byte yield |
| Script-data flag | `+0x55F` | `+0x563` | Total shift is now four bytes |
| Outer build count | `+0x560` | `+0x564` | Applies when script data is absent |

The bytes at Lekmod `+0x054` and `+0x055` are not unknown extensions. They are
the southeast- and southwest-edge river-flow directions. The two added
booleans occur earlier at `+0x033` and `+0x038`, and neither has a serialization
version gate. A later v35-only `m_bPseudoLake` field must not be applied to
v34.11 saves.

### Serialization version differences

| `CvPlot` version | Behavior |
|---:|---|
| Before 2 | Does not store the player-built-improvement byte |
| 3 and later | Stores feature as a 4-byte hash; earlier versions use a raw byte |
| All versions in this reader | Store resource as a 4-byte hash |
| 5 and later | Store improvement as a 4-byte hash; earlier versions use a raw byte |
| 6 and later | Store 80 revealed improvements as hashes; earlier versions use 80 `i16` values |
| 7 and later | Add the 4-byte under-construction improvement hash |

`CvArchaeologyData` has an independent serialization version. Its version 1
record omits the final work field.

For plots without script data, the observed serialized length is:

```text
CvPlot length = 0x625
              + (plot_unit_count * 8)
              + (0x1A4 when build progress is present)
```

Observed examples:

```text
Base plot                       0x625 bytes (1,573)
Base plot + 1 unit              0x62D bytes (1,581)
Base plot + 2 units             0x635 bytes (1,589)
Base plot + 3 units             0x63D bytes (1,597)
Base plot + 4 units             0x645 bytes (1,605)
Build progress                  0x7C9 bytes (1,993)
Build progress + 1 unit         0x7D1 bytes (2,001)
Build progress + 2 units        0x7D9 bytes (2,009)
```

The next `CvPlot` begins immediately after `CvArchaeologyData`. After exactly
`map_width * map_height` plots, the `CvArea` free-list begins.

There is no unknown four-byte plot extension in this layout. The field omitted
from an earlier size calculation was the serialized trade-route bit flags in
the fixed prefix.

## Structures after the plot array

The sizes in this section are confirmed for the examined multiplayer dataset.
They depend on saved object counts and must not be treated as universal
constants.

### `CvArea` free-list

The area free-list begins immediately after the final plot. It occupies
`0x34BCA` bytes in every examined multiplayer save.

Its `0x118`-byte metadata has these values:

| Field | Value |
|---|---:|
| Slot count | `64` |
| Last index | `44` |
| Free-list head | `-1` |
| Free count | `0` |
| Live-object count | `45` |

Each of the 45 live `CvArea` objects is `0x12BA` bytes:

```text
u32 version = 1
10 × i32 area counters
4 × i32 boundaries
2 × bool flags
5 × i32[80] player or team arrays
64 × IDInfo
64 × i32[7] yield modifiers
hashed resource array: 57 nonzero hash/value entries
hashed improvement array: 45 nonzero and 1 zero hash slot
```

### `CvLandmass` free-list

The landmass free-list follows the area free-list and occupies `0x2A8` bytes in
the examined multiplayer saves. Its `0x98`-byte metadata reports 32 slots, last
index 23, no free entries, and 24 live objects.

Each live object is `0x16` bytes:

| Order | Type | Meaning |
|---:|---|---|
| 1 | `u32` | Version |
| 2 | `i32` | ID |
| 3 | `i32` | Tile count |
| 4 | `i32` | Centroid X total |
| 5 | `i32` | Centroid Y total |
| 6 | `bool` | Water |
| 7 | `i8` | Continent type |

### End of `CvMap`

One `i32` AI map-hints value follows the landmass list. It is zero in all
examined saves. For this dataset:

```text
CvMap_end = final_plot_end
          + 0x34BCA  CvArea free-list
          + 0x002A8  CvLandmass free-list
          + 0x00004  AI map hints
          = final_plot_end + 0x34E76
```

A resync can regenerate the map GUID and landmass IDs without changing the
logical game turn.

## Source references

Lekmod v34.11 is commit
[`f4b96af9200470ab8fe50dee3dad0dce89c16975`](https://github.com/EnormousApplePie/Lekmod/commit/f4b96af9200470ab8fe50dee3dad0dce89c16975),
dated 2025-12-14. It is a commit subject, not a Git tag or GitHub release.

- [`CvPlot` version 7](https://github.com/EnormousApplePie/Lekmod/blob/f4b96af9200470ab8fe50dee3dad0dce89c16975/LEKMOD_DLL/CvGameCoreDLL_Expansion2/CvPlot.cpp#L53)
- [`CvPlot::read`](https://github.com/EnormousApplePie/Lekmod/blob/f4b96af9200470ab8fe50dee3dad0dce89c16975/LEKMOD_DLL/CvGameCoreDLL_Expansion2/CvPlot.cpp#L10546)
- [`CvPlot::write`](https://github.com/EnormousApplePie/Lekmod/blob/f4b96af9200470ab8fe50dee3dad0dce89c16975/LEKMOD_DLL/CvGameCoreDLL_Expansion2/CvPlot.cpp#L10784)
- [Lekmod-added booleans](https://github.com/EnormousApplePie/Lekmod/blob/f4b96af9200470ab8fe50dee3dad0dce89c16975/LEKMOD_DLL/CvGameCoreDLL_Expansion2/CvPlot.cpp#L10816-L10828)
- [Compact `CvPlot` member types](https://github.com/EnormousApplePie/Lekmod/blob/f4b96af9200470ab8fe50dee3dad0dce89c16975/LEKMOD_DLL/CvGameCoreDLL_Expansion2/CvPlot.h#L833-L973)
- [Tile hashes, compact fields, river flows, city IDs, and yields](https://github.com/EnormousApplePie/Lekmod/blob/f4b96af9200470ab8fe50dee3dad0dce89c16975/LEKMOD_DLL/CvGameCoreDLL_Expansion2/CvPlot.cpp#L10830-L10862)
- [Golden Age Points yield enum](https://github.com/EnormousApplePie/Lekmod/blob/f4b96af9200470ab8fe50dee3dad0dce89c16975/LEKMOD_DLL/CvGameCoreDLL_Expansion2/CvGameCoreEnums.h#L11-L24)
- [Archaeology reader and writer](https://github.com/EnormousApplePie/Lekmod/blob/f4b96af9200470ab8fe50dee3dad0dce89c16975/LEKMOD_DLL/CvGameCoreDLL_Expansion2/CvPlot.cpp#L108-L142)
- [Interleaved build-array writer](https://github.com/EnormousApplePie/Lekmod/blob/f4b96af9200470ab8fe50dee3dad0dce89c16975/LEKMOD_DLL/CvGameCoreDLL_Expansion2/CvInfos.cpp#L3974-L3996)
- [Hashed-type writer](https://github.com/EnormousApplePie/Lekmod/blob/f4b96af9200470ab8fe50dee3dad0dce89c16975/LEKMOD_DLL/CvGameCoreDLL_Expansion2/CvInfosSerializationHelper.cpp#L168-L185)
- [Hashed-type reader](https://github.com/EnormousApplePie/Lekmod/blob/f4b96af9200470ab8fe50dee3dad0dce89c16975/LEKMOD_DLL/CvGameCoreDLL_Expansion2/CvInfosSerializationHelper.cpp#L288-L300)
- [`FStringA::Hash`](https://github.com/EnormousApplePie/Lekmod/blob/f4b96af9200470ab8fe50dee3dad0dce89c16975/LEKMOD_DLL/CvGameCoreDLL_Expansion2/FirePlace/include/FireWorks/FStringA.inl#L988-L1001)
- [CRC32 parameters](https://github.com/EnormousApplePie/Lekmod/blob/f4b96af9200470ab8fe50dee3dad0dce89c16975/LEKMOD_DLL/CvGameCoreDLL_Expansion2/FirePlace/include/FireWorks/FCrc32.h#L78-L106)
- [Flow-direction enum](https://github.com/EnormousApplePie/Lekmod/blob/f4b96af9200470ab8fe50dee3dad0dce89c16975/LEKMOD_DLL/CvGameCoreDLL_Expansion2/CvGameCoreDLLUtil/include/CvEnums.h#L464-L475)
- [Terrain enum](https://github.com/EnormousApplePie/Lekmod/blob/f4b96af9200470ab8fe50dee3dad0dce89c16975/LEKMOD_DLL/CvGameCoreDLL_Expansion2/CvGameCoreDLLUtil/include/CvEnums.h#L1022-L1037)
- [Plot-type enum](https://github.com/EnormousApplePie/Lekmod/blob/f4b96af9200470ab8fe50dee3dad0dce89c16975/LEKMOD_DLL/CvGameCoreDLL_Expansion2/CvGameCoreDLLUtil/include/CvEnums.h#L1039-L1048)
- [Route enum](https://github.com/EnormousApplePie/Lekmod/blob/f4b96af9200470ab8fe50dee3dad0dce89c16975/LEKMOD_DLL/CvGameCoreDLL_Expansion2/CvGameCoreDLLUtil/include/CvEnums.h#L1216-L1224)
