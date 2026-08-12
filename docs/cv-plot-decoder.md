# Plot API

`Civ5SaveDecoder.plots` returns every map plot as a cached tuple:

```python
from savefile_reverse_engineer import Civ5SaveDecoder

decoder = Civ5SaveDecoder("AutoSave.Civ5Save")
for plot in decoder.plots:
    print(plot.x, plot.y, plot.owner_player_index, plot.terrain)
    print(decoder.get_owner_display_name(plot))
    print(plot.feature.key, plot.resource.key, plot.yields.food)
```

The first `get_owner_display_name()` call decodes and caches participating
players if needed. Unowned plots and unresolved player names return `None`.

The semantic `CvPlot` contains common confirmed game state. Database hashes are
represented by `GameType(hash_value, key)`. Unknown keys remain `None`; exact
hashes are never discarded. Object references use `owner_player_index` and
`object_id`.

Access validates the complete plot array before caching it. Malformed data
raises `CvPlotDecodeError`; failed results are not cached.

The supported payload layout is Lekmod v34.11 `CvPlot` version 7. See the
[map and plot byte layout](map-information.md) for exact fields and limits.
