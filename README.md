# Civilization V save-file reverse engineer

This Python package reads selected game state from Civilization V save files.
It supports the supplied build 403694 saves and the Lekmod v34.11 payload
layout.

The package has two supported API layers:

- The package root provides immutable semantic game-state records.
- `savefile_reverse_engineer.raw` provides exact serialization records and
  bytes-only decoders for format research.

Player, city, and unit decoding remains partial. The raw decoders bound their
complete records but do not expose every serialized field.

## Semantic API

```python
from savefile_reverse_engineer import Civ5SaveDecoder

decoder = Civ5SaveDecoder("AutoSave.Civ5Save")

print(decoder.summary.turn)
print(decoder.settings.game_name)

for player in decoder.iter_players():
    print(
        player.player_index,
        player.player_type,
        player.display_name,
        player.faith,
        len(player.cities),
    )

for city in decoder.iter_cities():
    print(city.owner_player_index, city.city_id, city.name_key, city.population)

for plot in decoder.iter_plots():
    print(plot.x, plot.y, plot.terrain)
```

`iter_players()` returns slots marked `TAKEN` or `COMPUTER`, including defeated
players with empty records. `iter_teams()` returns the unique teams used by
those slots. The raw player and team array decoders return all 64 serialized
records.

The decoder reads the file once. Its summary, settings, player slots, raw
header, and decompressed `payload_bytes` are cached. Each `iter_*` method
returns a fresh lazy iterator.

## Raw API

```python
from savefile_reverse_engineer.raw import (
    decode_header_bytes,
    decode_plot_array_bytes,
    decompress_payload_bytes,
)

save_bytes = open("AutoSave.Civ5Save", "rb").read()
header = decode_header_bytes(save_bytes)
payload = decompress_payload_bytes(save_bytes, header)

for plot in decode_plot_array_bytes(exact_plot_array_bytes):
    print(plot.byte_offset, plot.version, plot.x, plot.y)
```

The raw namespace preserves offsets, lengths, serialization versions,
free-list metadata, compressed chunks, unknown header spans, and placeholder
array slots.

## Documentation

Start with the [documentation index](docs/README.md). It separates the
semantic Python API from the raw byte-layout references and records the
supported versions and known limits.
