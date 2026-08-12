# Civilization V save-file reverse engineer

This Python package reads selected game state from Civilization V save files.
It supports the supplied build 403694 saves and the Lekmod v34.11 payload
layout.

The package root provides the common public API of immutable semantic
game-state records. The public `game`, `map`, `player`, `team`, and `errors`
modules provide focused imports for their domains. Byte-exact parsing remains
a private implementation detail.

Player, city, and unit decoding remains partial. The raw decoders bound their
complete records but do not expose every serialized field.

## Semantic API

```python
from savefile_reverse_engineer import Civ5SaveDecoder

decoder = Civ5SaveDecoder("AutoSave.Civ5Save")

print(decoder.summary.turn)
print(decoder.settings.game_name)

for player in decoder.players:
    print(
        player.player_index,
        player.player_type,
        player.display_name,
        player.faith,
        len(player.cities),
    )

for city in decoder.cities:
    print(city.owner_player_index, city.city_id, city.name_key, city.population)

for plot in decoder.plots:
    print(plot.x, plot.y, plot.terrain)
```

`players` contains slots marked `TAKEN` or `COMPUTER`, including defeated
players with empty records. `teams` contains the unique teams used by those
slots.

The decoder reads the file once. Summary, settings, slots, display names, and
all five collection properties are cached. `players`, `teams`, `plots`,
`cities`, and `units` are immutable tuples. A failed property access is not
cached and can be retried.

## Documentation

Start with the [documentation index](docs/README.md). It separates the
semantic Python API from contributor-only byte-layout references and records
the supported versions and known limits.
