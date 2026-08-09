# Civilization V save-file reverse engineer

This Python package reads selected structures from Civilization V save files.
It supports the supplied build 403694 saves and the Lekmod v34.11 payload
layout.

Current decoding includes:

- the physical save header and compressed container
- the complete decompressed payload as bytes
- every `CvPlot` and `CvTeam` record
- confirmed `CvPlayer` fields and nested city and unit records
- each decoded city's building inventory

Player, city, and unit decoding is partial. The decoder can bound their
complete records but does not expose every serialized field.

## Example

```python
from savefile_reverse_engineer import Civ5SaveDecoder

decoder = Civ5SaveDecoder("AutoSave.Civ5Save")

print(decoder.header.quick.turn)

for plot in decoder.iter_cv_plots():
    print(plot.x, plot.y, plot.terrain)

for team in decoder.iter_cv_teams():
    print(team.team_id, team.city_count, team.total_population)

for player in decoder.iter_cv_players():
    print(player.player_index, player.faith, len(player.cities.entries))
```

The decoder reads the file once. Header and payload results are cached, while
each `iter_*` method returns a fresh lazy iterator.

## Documentation

Start with the [documentation index](docs/README.md). It separates the public
Python API from the reverse-engineered byte layouts and records the supported
versions and known limits.

## Project direction

The project aims to expose useful game state such as yields, units, positions,
and citizen management while preserving unknown bytes and avoiding claims that
the available save evidence cannot prove.
