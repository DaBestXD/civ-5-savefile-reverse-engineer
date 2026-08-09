# Plot API

`Civ5SaveDecoder.iter_plots` returns a fresh lazy iterator over every map plot:

```python
from savefile_reverse_engineer import Civ5SaveDecoder

for plot in Civ5SaveDecoder("AutoSave.Civ5Save").iter_plots():
    print(plot.x, plot.y, plot.owner_player_index, plot.terrain)
    print(plot.feature.key, plot.resource.key, plot.yields.food)
```

The semantic `CvPlot` contains common confirmed game state. Database hashes are
represented by `GameType(hash_value, key)`. Unknown keys remain `None`; exact
hashes are never discarded. Object references use `owner_player_index` and
`object_id`.

The iterator validates map dimensions and row-major coordinates. Errors later
in the payload are raised when iteration reaches them. Consume the iterator
fully when the entire plot array must be validated. A successful complete
iteration caches the semantic plots; later calls iterate over the same
immutable objects without decoding them again.

## Exact raw records

Use the raw decoder for byte offsets, record lengths, serialization versions,
fixed per-player arrays, build progress, and archaeology data:

```python
from savefile_reverse_engineer.raw import decode_plot_array_bytes

plots = tuple(decode_plot_array_bytes(exact_plot_array_bytes))
print(plots[0].byte_offset, plots[0].version)
```

The bytes must start at plot `(0, 0)`, contain complete rows, and end after the
last plot. Malformed data raises `CvPlotDecodeError`.

The supported payload layout is Lekmod v34.11 `CvPlot` version 7. See the
[map and plot byte layout](map-information.md) for exact fields and limits.
