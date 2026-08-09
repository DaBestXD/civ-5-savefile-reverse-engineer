# `CvPlayer` decoder API

`Civ5SaveDecoder.iter_cv_players` reads all 64 serialized player records from a
complete physical `.CIV5SAVE` file. It locates the array by decoding `CvMap`
and the complete `CvTeam[64]` array. It then returns confirmed `CvPlayer`
prefix fields and the live `CvCity` and `CvUnit` entries in each player's
serialized free lists.

The supported layout is limited to:

- Lekmod v34.11
- `CvPlayer` serialization version 16
- `CvCity` serialization version 6
- `CvUnit` serialization version 9
- 64 player records
- the pinned v34.11 free-list format and 8,192-slot ID mask

This is a partial field decoder. It bounds complete player, city, and unit
records, but it does not expose every field stored inside them.

## Input and iteration

Construct `Civ5SaveDecoder` with a save path and call `iter_cv_players`:

```python
from savefile_reverse_engineer import Civ5SaveDecoder

decoder = Civ5SaveDecoder("AutoSave.Civ5Save")
for player in decoder.iter_cv_players():
    print(player.player_index, player.faith, player.culture_times_100)
    for city in player.cities.entries:
        print("city", city.city_id, city.x, city.y, city.population)
        for state in city.buildings.entries:
            if (state.real_count or 0) > 0 or (state.free_count or 0) > 0:
                print("building", state.building.name)
    for unit in player.units.entries:
        print("unit", unit.unit_id, unit.x, unit.y)
```

The method returns a fresh lazy iterator. The decoder caches the decompressed
payload and the array location. It creates new result objects each time the
iterator is consumed.

Callers that already have the exact serialized player-array bytes can use:

```python
from savefile_reverse_engineer.cv_player import decode_cv_player_array_bytes

players = tuple(decode_cv_player_array_bytes(player_array_bytes))
```

The bytes-only input must contain exactly 64 player records and no leading or
trailing data.

## Results

Each `CvPlayer` contains:

- its array index, decompressed byte offset, and complete record length
- version, starting coordinate, population, and land counters
- confirmed culture, faith, and happiness prefix values
- `cities`, a `SerializedFreeList[CvCity]`
- `units`, a `SerializedFreeList[CvUnit]`

`SerializedFreeList` preserves the saved slot capacity, last occupied index,
free-chain head, free count, current ID generation, next-free indexes, byte
range, and live entries. `entries` are in serialized live-slot order. Deleted
slots do not produce entries.

Each city exposes its ID, coordinates, rally point, founding and acquisition
turns, population counters, early Great Person counters, early culture values,
and its `CvCityBuildings` inventory. The inventory contains all 268 serialized
building types. Each entry includes its hash and known Lekmod name, construction
progress and duration, original owner and year, and real and free counts. A
zero-hash placeholder has `None` values. Each unit exposes its ID, saved runtime
unit-type index, and coordinates.

The unit-type value is an integer runtime database index. The current record
prefix does not serialize a type hash, so the decoder does not assign a unit
name. Do not assume that the same index identifies the same unit under another
mod or database order.

## Structural boundaries

Every supported player contains three consecutive `FFreeListTrashArray`
objects: cities, units, and armies. The decoder validates all three headers and
uses them to bound each variable player record. Only the city and unit lists are
returned by the public result.

Complete-save decoding also compares every player's saved population and land
with the corresponding decoded team totals. The bytes-only decoder finds a
single 64-record path where every record contains exactly three validated free
lists and the calculated final record ends at input EOF.

See the [player, city, and unit byte layout](player-information.md) for the
free-list rules, confirmed record prefixes, and building-inventory boundary.

## Errors and validation

Malformed player data raises `CvPlayerDecodeError`. Its `player_index`,
`offset`, and `field` attributes identify the failing record, absolute byte
offset, and logical field. Bytes-only offsets are relative to the supplied
array. Complete-save offsets are relative to the decompressed payload.

The decoder rejects:

- unsupported player, city, or unit versions
- missing or extra player records
- missing or extra object free lists between player boundaries
- invalid free-list capacities, indexes, counts, IDs, or free-chain cycles
- a live-entry count that disagrees with occupied and deleted slots
- city or unit IDs that do not identify the expected live slot
- implausible player, city, or unit coordinates
- unsupported building versions, invalid building counts, mismatched building
  hashes, and malformed building flags
- player population or land that disagrees with the corresponding team
- a final player record outside the supplied bytes
- leading or trailing data in the bytes-only API

## Compatibility limits

The boundary parser depends on the v34.11 ordering of the city, unit, and army
free lists. It has not been validated for vanilla Civilization V, other mods,
or later Lekmod versions. It also does not yet expose player AI subobjects,
treasury, diplomacy, city citizens, building yield changes, building Great Work
assignments, unit promotions, unit missions, or the army entries.

The [byte-layout reference](player-information.md) also contains the pinned
source references.
