# Team API

`Civ5SaveDecoder.iter_teams` returns the unique teams referenced by player
slots marked `TAKEN` or `COMPUTER`:

```python
from savefile_reverse_engineer import Civ5SaveDecoder

for team in Civ5SaveDecoder("AutoSave.Civ5Save").iter_teams():
    print(team.team_index, team.city_count, team.total_population)
```

A successful complete iteration caches the semantic teams. Later calls return
fresh iterators over the same immutable objects without decoding them again.

The semantic `CvTeam` includes common population, land, victory, route,
diplomacy, and era state. It omits duplicate IDs, serialization metadata, and
the detailed hashed arrays intended for format research.

## Exact raw records

Use the raw decoder to retrieve all 64 serialized teams and every confirmed
field:

```python
from savefile_reverse_engineer.raw import decode_team_array_bytes

for team in decode_team_array_bytes(exact_team_array_bytes):
    print(team.team_id, team.byte_offset, team.technologies)
```

The input must contain exactly 64 records without leading or trailing bytes.
Raw results preserve technology records, hashed arrays, project art, yield
changes, revealed resources, offsets, lengths, and versions. Malformed data
raises `CvTeamDecodeError`.

The supported payload layout is Lekmod v34.11 `CvTeam` version 1 and
`CvTeamTechs` version 1. See the [team byte layout](team-information.md) for
exact fields and limits.
