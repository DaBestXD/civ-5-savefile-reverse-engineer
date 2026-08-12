# Team API

`Civ5SaveDecoder.teams` returns the unique teams referenced by player
slots marked `TAKEN` or `COMPUTER`:

```python
from savefile_reverse_engineer import Civ5SaveDecoder

for team in Civ5SaveDecoder("AutoSave.Civ5Save").teams:
    print(team.team_index, team.city_count, team.total_population)
    unlocked = [
        technology.technology.key
        for technology in team.technologies
        if technology.unlocked
    ]
    print(unlocked)
```

The immutable tuple is cached only after complete decoding succeeds.

The semantic `CvTeam` includes common population, land, victory, route,
diplomacy, era, and technology state. Each technology includes its resolved
type, unlocked state, source flags, trade restriction, research progress, and
acquisition count. It omits duplicate IDs, serialization metadata, and the
other detailed hashed arrays intended for format research.

Malformed data raises `CvTeamDecodeError`.

The supported payload layout is Lekmod v34.11 `CvTeam` version 1 and
`CvTeamTechs` version 1. See the [team byte layout](team-information.md) for
exact fields and limits.
