<!-- markdownlint-disable -->
# `CvPlayer`, `CvCity`, and `CvUnit` byte layout

This document describes the structures confirmed in the examined Lekmod
v34.11 saves. For the Python API, see the
[`CvPlayer` decoder guide](cv-player-decoder.md).

Exactly 64 variable-length `CvPlayerAI` objects follow `CvTeam[64]`. The base
`CvPlayer` data contains three serialized free lists in this order:

```text
CvPlayerAI / CvPlayer
├─ player prefix and variable player and AI fields
├─ FFreeListTrashArray<CvCityAI>
│  └─ live CvCityAI / CvCity records
├─ FFreeListTrashArray<CvUnit>
│  └─ live CvUnit records
├─ FFreeListTrashArray<CvArmyAI>
│  └─ live CvArmyAI records
└─ remaining player tail
```

The decoder uses those three validated free-list headers, player version
prefixes, and team population and land totals to bound all 64 player records.
It does not yet consume every intervening field in source order.

## CvPlayer prefix

All fields below are signed 32-bit integers except the version.

| Offset | Field |
|---:|---|
| `+0x00` | `u32` serialization version, `16` |
| `+0x04` | Starting X |
| `+0x08` | Starting Y |
| `+0x0C` | Total population |
| `+0x10` | Total land |
| `+0x14` | Total land used for score |
| `+0x18` | Culture per turn from free sources |
| `+0x1C` | Culture per turn from minor civilizations |
| `+0x20` | Culture city modifier |
| `+0x24` | Current culture, multiplied by 100 |
| `+0x28` | Lifetime culture, multiplied by 100 |
| `+0x2C` | Culture per wonder |
| `+0x30` | Culture wonder multiplier |
| `+0x34` | Culture per researched technology |
| `+0x38` | Current faith |
| `+0x3C` | Lifetime faith |
| `+0x40` | Happiness |

An unset starting coordinate is stored as `-2147483647` in the examined
records. Active-player population and land match the corresponding `CvTeam`
totals.

## Free-list header

The city, unit, and army containers use the same serialized
`FFreeListTrashArray` header:

```text
i32 slot_count
i32 last_index
i32 free_list_head
i32 free_count
i32 current_id
i32 next_free_indices[slot_count]
i32 live_count
live object records in occupied slot order
```

`last_index + 1` is the number of occupied and deleted slots. It must equal
`live_count + free_count`. Starting at `free_list_head` and following
`next_free_indices` must visit exactly `free_count` distinct slots. A live
object's full ID contains its slot in the low 13 bits:

```text
slot_index = object_id & 0x1FFF
```

The current ID generation is a nonnegative multiple of 8,192. The decoder
supports at most 8,192 slots.

## Confirmed CvCity prefix

The city free list stores `CvCityAI`, whose base `CvCity` serialization starts
with the following confirmed fields:

| Offset | Field |
|---:|---|
| `+0x00` | `u32` serialization version, `6` |
| `+0x04` | City ID |
| `+0x08` | X |
| `+0x0C` | Y |
| `+0x10` | Rally X |
| `+0x14` | Rally Y |
| `+0x18` | Turn founded |
| `+0x1C` | Turn acquired |
| `+0x20` | Population |
| `+0x24` | Highest population |
| `+0x28` | Great People created |
| `+0x2C` | Base Great Person rate |
| `+0x30` | Great Person rate modifier |
| `+0x34` | Stored culture, multiplied by 100 |
| `+0x38` | Culture level |

The decoder follows the remaining source-order fields before the building
object to validate the city start. It exposes the length-prefixed UTF-8 city
localization key as `name_key`. Most of the other values are not exposed.

## Confirmed CvCityBuildings inventory

`CvCityBuildings` follows the city name, script data, resource arrays, and
specialist and project production vectors. Its offset is variable. Version 1
starts with these fields:

| Order | Field |
|---:|---|
| 1 | `u32` serialization version, `1` |
| 2 | Number of buildings |
| 3 | Building production modifier |
| 4 | Building defence |
| 5 | Garrison strength bonus added by Lekmod |
| 6 | Building defence per citizen added by NQ/Lekmod |
| 7 | Building defence modifier |
| 8 | Extra missionary spreads |
| 9 | Landmark tourism percent |
| 10 | Great Works tourism modifier |
| 11 | One-byte sold-building-this-turn flag |

Six hashed integer arrays follow in this order:

1. Production stored in hundredths
2. Turns under production
3. Original owner
4. Original construction year
5. Real building count
6. Free building count

Each array has 268 entries in the examined v34.11 saves. Each nonzero entry is
a four-byte building-type hash followed by a signed four-byte value. All six
arrays use the same hash order. Known hashes resolve to names such as
`BUILDING_LIBRARY` and `BUILDING_GRANARY`; unknown hashes retain their integer
value and use `None` for the name. A zero-hash placeholder has no serialized
integer value.

The public `CvCityBuildings.inventory_byte_length` ends after these arrays.
The following building yield changes and Great Work assignments are not yet
decoded.

## Confirmed CvUnit prefix

`CvUnit` uses a sync archive after its version word. The confirmed leading
archive values are:

| Offset | Field |
|---:|---|
| `+0x00` | `u32` serialization version, `9` |
| `+0x04` | Archive prefix value, not exposed |
| `+0x08` | Archive prefix value, not exposed |
| `+0x0C` | Runtime unit-type index |
| `+0x10` | X |
| `+0x14` | Y |
| `+0x18` | Unit ID |

The sync archive continues with movement, combat, promotion, type-catalogue,
and AI state. Its vectors and strings make its serialized length variable. A
four-byte unit `Type` hash follows the complete sync archive. The current
Lekmod v34.11 fixtures place that hash at `+0x817` for ordinary records, but
the decoder calculates its position from the archive structure rather than
assuming a fixed offset.

The record continues after the hash with promotions, missions, transport, and
other state. Those bytes are included in `CvUnit.byte_length` but are not yet
exposed.

## Turn 76 validation values

For `AutoSave_Post_0076 AD-0040.Civ5Save`:

- `CvPlayer[0]` starts at decompressed offset `0x42513D`.
- It has population 44, land 56, culture 23,000 hundredths, and faith 62.
- Its four live cities use slots 0 through 3 and IDs 8192, 16385, 24578, and
  32771.
- Those cities are at `(11, 16)`, `(16, 14)`, `(7, 20)`, and `(6, 26)` with
  populations 16, 9, 10, and 9.
- Its unit list has 16 live entries and one deleted slot, slot 14.
- Its first unit has ID 57344, serialized type `UNIT_WORKER`, and coordinate
  `(12, 15)`.
- Its second city has real libraries and granaries with count 1.
- Its capital has 7,081 hundredths of production stored toward the Great
  Lighthouse.

## Source references

- [Lekmod v34.11 commit](https://github.com/EnormousApplePie/Lekmod/commit/f4b96af9200470ab8fe50dee3dad0dce89c16975)
- [`CvPlayer::Read/Write`](https://github.com/EnormousApplePie/Lekmod/blob/f4b96af9200470ab8fe50dee3dad0dce89c16975/LEKMOD_DLL/CvGameCoreDLL_Expansion2/CvPlayer.cpp)
- [`CvCity::read/write`](https://github.com/EnormousApplePie/Lekmod/blob/f4b96af9200470ab8fe50dee3dad0dce89c16975/LEKMOD_DLL/CvGameCoreDLL_Expansion2/CvCity.cpp)
- [`CvCityBuildings::Read/Write` and building-array helpers](https://github.com/EnormousApplePie/Lekmod/blob/f4b96af9200470ab8fe50dee3dad0dce89c16975/LEKMOD_DLL/CvGameCoreDLL_Expansion2/CvBuildingClasses.cpp#L2787-L2857)
- [`CvUnit::read/write`](https://github.com/EnormousApplePie/Lekmod/blob/f4b96af9200470ab8fe50dee3dad0dce89c16975/LEKMOD_DLL/CvGameCoreDLL_Expansion2/CvUnit.cpp)
- [`FFreeListTrashArray` serialization](https://github.com/EnormousApplePie/Lekmod/blob/f4b96af9200470ab8fe50dee3dad0dce89c16975/LEKMOD_DLL/CvGameCoreDLL_Expansion2/FirePlace/include/FireWorks/FFreeListTrashArray.h)
