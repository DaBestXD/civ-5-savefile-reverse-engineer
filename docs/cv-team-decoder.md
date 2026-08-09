# `CvTeam` decoder API

`Civ5SaveDecoder.iter_cv_teams` reads the 64 serialized team records from a
complete physical `.CIV5SAVE` file. It decompresses the payload, locates
`CvMap`, parses the declared plot array, structurally skips the `CvArea` and
`CvLandmass` free lists, and starts decoding immediately after the AI map hints
field. It does not locate teams by scanning for a byte signature or by assuming
a fixed map-tail length.

The supported layout is:

- Lekmod v34.11
- `CvTeam` serialization version 1
- `CvTeamTechs` serialization version 1
- 64 team records and relationship slots
- 81 technologies
- Seven yields
- The pinned v34.11 database catalogue sizes

Later v34.14 and v35 team layouts are not supported.

## Input and iteration

Construct `Civ5SaveDecoder` with a save path and call `iter_cv_teams`:

```python
from savefile_reverse_engineer import Civ5SaveDecoder

decoder = Civ5SaveDecoder("AutoSave.Civ5Save")
for team in decoder.iter_cv_teams():
    print(team.team_id, team.city_count, team.total_population)
```

The method returns a fresh lazy iterator. Locating the array requires parsing
the earlier plots and map free lists. That location is cached after the first
call. Each `CvTeam` record is then parsed immediately before it is yielded, so
team-data errors can be raised while the iterator is consumed.

Callers that already have the exact serialized team-array bytes can use the
bytes-only decoder:

```python
from savefile_reverse_engineer.cv_team import decode_cv_team_array_bytes

for team in decode_cv_team_array_bytes(team_array_bytes):
    print(team.team_id)
```

The bytes-only input must contain exactly 64 records and no leading or trailing
data.

## Result

Each yielded `CvTeam` is a data class containing every confirmed serialized
field. Important fields include:

- `team_index` and serialized `team_id`
- `byte_offset` and complete variable `byte_length`
- Member, city, population, land, trade, movement, and victory counters
- Eight flags in `TeamFlags`
- Fixed diplomacy and relationship tuples
- Hashed victory, route, build, project, unit, building, and terrain arrays
- Project art choices
- Technologies and research progress
- General, fresh-water, and no-fresh-water improvement yield changes
- Revealed resources

The decoder validates that the serialized team ID matches its position in the
array. `best_possible_route` is returned as `RouteType`; other identifiers that
are not serialized as hashes remain integers.

## Database hashes

Hashed arrays return `HashedValue` entries. Their `type` is a `HashedType` with
the exact unsigned hash and, when known, its pinned Lekmod v34.11 name:

```python
HashedValue(
    type=HashedType(hash_value=..., name="UNITCLASS_WORKER"),
    value=7,
)
```

A zero slot has `hash_value=0`, `name=None`, and `value=None`. An unrecognized
nonzero hash preserves the integer and also uses `name=None`. This keeps modded
data visible without treating it as a supported catalogue entry.

## Technologies and yields

`technologies` contains 81 `TeamTechnology` records in saved slot order. Each
record combines its hash with ownership, acquisition source, trade restriction,
research progress, and repeat-acquisition count. Research progress remains in
the game's serialized hundredths.

`last_technology_index` preserves the serialized index. `last_technology`
resolves that index to the corresponding `HashedType`, or is `None` when the
saved index is `-1`.

Each nonempty improvement slot contains a `TeamYieldChanges` value with food,
production, gold, science, culture, faith, and Golden Age Points. The three
improvement arrays are kept separate because they apply under different fresh
water conditions.

## Variable sections

Project art is decoded using the saved project hashes and project counts. Each
project returns its complete tuple of art-type integers.

The revealed-resource vector uses its serialized count and can change a team's
record length. `byte_length` is therefore calculated from parsed fields instead
of being fixed at the `0x3424` length observed in the supplied saves.

## Errors and validation

Malformed team data raises `CvTeamDecodeError`. Its `team_index` and `offset`
attributes identify the failing record and absolute byte offset. Bytes-only
decoding uses offsets relative to the supplied array; complete-save decoding
uses offsets in the decompressed payload.

Malformed embedded SQLite, `CvMap`, `CvArea`, or `CvLandmass` framing raises
`Civ5SavePayloadDecodeError` before the team iterator is returned.

The decoder rejects:

- Team or technology versions other than 1
- A team ID that does not match its array index
- Invalid Boolean bytes or route values
- Catalogue counts that differ from the pinned Lekmod v34.11 layout
- Technology indexes outside the saved technology array
- Project art hashes that do not match saved project counts
- Revealed-resource counts larger than the supported resource catalogue
- Counts or records that extend beyond the supplied bytes
- Missing or trailing bytes in a bytes-only team array

See the [`CvTeam` byte layout](team-information.md) for offsets and pinned
source references.
