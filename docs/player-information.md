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

## Confirmed player policy information

Each bounded player contains one `CvPlayerPolicies` version-2 object before its
city free list. The decoder locates it by validating its repeated hashed-array
structure rather than assuming a fixed player-relative offset.

The pinned Lekmod v34.11 layout has 138 policy slots. Fourteen slots contain a
zero hash and therefore have no following value byte; the other entries store
a four-byte policy hash followed by a one-byte Boolean. The first three arrays
use identical hash order and save owned, one-shot-fired, and free-unit-fired
state. Only the owned state is exposed.

The policy arrays are followed by 12 policy-branch entries. The confirmed
unlocked array stores a four-byte branch hash and one-byte Boolean for every
branch. Known hashes resolve to keys from `POLICY_BRANCH_TRADITION` through
`POLICY_BRANCH_AUTOCRACY`.

The examined saves contain additional branch-keyed arrays whose exact meanings
differ from the bundled source layout. They help validate the policy-block
location but are not assigned public field names.

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
localization key as `name_key` and the 18 yield vectors described below. Most
of the other values are not exposed.

## Confirmed CvCity yield vectors

Eighteen length-prefixed integer vectors follow the city owner fields. Each
vector contains seven values in this order: food, production, gold, science,
culture, faith, and Golden Age Points.

| Order | Public field | Source member |
|---:|---|---|
| 1 | `sea_plot_yield` | `m_aiSeaPlotYield` |
| 2 | `river_plot_yield` | `m_aiRiverPlotYield` |
| 3 | `lake_plot_yield` | `m_aiLakePlotYield` |
| 4 | `sea_resource_yield` | `m_aiSeaResourceYield` |
| 5 | `base_yield_rate_from_terrain` | `m_aiBaseYieldRateFromTerrain` |
| 6 | `base_yield_rate_from_buildings` | `m_aiBaseYieldRateFromBuildings` |
| 7 | `base_yield_rate_from_specialists` | `m_aiBaseYieldRateFromSpecialists` |
| 8 | `base_yield_rate_from_misc` | `m_aiBaseYieldRateFromMisc` |
| 9 | `base_yield_rate_from_religion` | `m_aiBaseYieldRateFromReligion` |
| 10 | `base_yield_rate_from_policies` | `m_aiBaseYieldRateFromPolicies` |
| 11 | `garrison_yield_bonus` | `m_aiGarrisonYieldBonus` |
| 12 | `yield_per_population_x100` | `m_aiYieldPerPop` |
| 13 | `yield_per_religion_x100` | `m_aiYieldPerReligion` |
| 14 | `yield_rate_modifier` | `m_aiYieldRateModifier` |
| 15 | `power_yield_rate_modifier` | `m_aiPowerYieldRateModifier` |
| 16 | `resource_yield_rate_modifier` | `m_aiResourceYieldRateModifier` |
| 17 | `extra_specialist_yield` | `m_aiExtraSpecialistYield` |
| 18 | `production_to_yield_modifier` | `m_aiProductionToYieldModifier` |

The raw and semantic `CvCity` records group these fields under
`yield_vectors`. The per-population and per-religion vectors use hundredths.
The rate and production-conversion vectors contain percentage modifiers.

## Confirmed CvCityCitizens specialist state

Four legacy length-prefixed specialist vectors and one improvement vector
appear after `CvCityBuildings`. Lekmod writes these as zero-filled compatibility
data, so they are consumed for alignment but are not exposed as city state.

The authoritative assignments are in the later version 1 `CvCityCitizens`
subobject. It starts with automation flags, citizen counts, the focus index,
37 worked-plot flags, 37 forced-worked-plot flags, and the default-specialist
counts. Five hashed integer arrays then follow:

| Array | Entries | Meaning |
|---|---:|---|
| Specialist counts | 7 | Currently assigned specialists |
| Great-person progress | 7 | Progress in hundredths |
| Building specialist counts | 268 | Assigned specialists by building |
| Forced building specialist counts | 268 | Forced assignments by building |
| Building great-person rate changes | 7 | Rate changes by specialist type |

The three specialist arrays use this saved hash order:

| Index | Specialist |
|---:|---|
| 0 | Citizen |
| 1 | Writer |
| 2 | Artist |
| 3 | Musician |
| 4 | Scientist |
| 5 | Merchant |
| 6 | Engineer |

The public API resolves each hash to a `GameType` and exposes this object as
`CvCity.citizens`. The citizen block has no separate authoritative maximum or
free-specialist vector.

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
The following building yield changes and Great Work assignments are skipped
but are not yet exposed.

## Confirmed city production queue

The decoder follows the remaining source-order containers after
`CvCityBuildings` to reach `m_orderQueue`: two hashed unit-production arrays,
four legacy specialist-count vectors, a legacy improvement free-specialist
vector, two unit-combat vectors, and a hashed free-promotion array. These
intervening containers are validated but are not exposed.

The queue begins with a four-byte entry count. Each entry then contains:

| Order | Field |
|---:|---|
| 1 | Four-byte `ProductionOrderType` value |
| 2 | Four-byte database type hash for the item |
| 3 | Four-byte secondary data value |
| 4 | One-byte save flag |
| 5 | One-byte rush flag |

The first entry is the city's current production. The remaining entries are
queued. `CvCity.production_queue` preserves this order, resolves known unit,
building, and project hashes, and retains unknown hashes with a `None` name.

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
- Its `CvPlayerPolicies` object starts at decompressed offset `0x428708`.
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
