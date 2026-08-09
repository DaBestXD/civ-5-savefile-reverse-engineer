# `CvPlot` decoder API

`Civ5SaveDecoder.iter_cv_plots` reads the serialized plot array from a complete
physical `.CIV5SAVE` file. It decompresses the payload, locates the embedded
SQLite database and `CvMap`, reads the map dimensions and resource arrays, and
then decodes exactly `width × height` plots. It does not decode the `CvArea`,
`CvLandmass`, `CvPlayer`, or `CvTeam` sections.

The supported layout is:

- Lekmod v34.11
- `CvPlot` serialization version 7
- Little-endian integers
- 80 player and team slots embedded in each plot
- 22 no-settling flags embedded in each plot
- Seven yields
- No plot script data

## Input and iteration

Construct `Civ5SaveDecoder` with a save path and call `iter_cv_plots`:

```python
from savefile_reverse_engineer import Civ5SaveDecoder

decoder = Civ5SaveDecoder("AutoSave.Civ5Save")
for plot in decoder.iter_cv_plots():
    print(plot.x, plot.y, plot.terrain)
```

The method returns a lazy iterator. A record is parsed immediately before it
is yielded. Errors later in the byte sequence are therefore raised when the
iterator reaches those bytes. Consume the iterator fully when the whole array
must be validated.

The decoder reads width and height from `CvMap`. It validates every coordinate
against row-major order and stops after the declared number of plots. Calling
the method again returns a fresh iterator and reuses the cached payload.

Callers that already have an exact serialized plot-array byte sequence can use
the bytes-only decoder:

```python
from savefile_reverse_engineer.cv_plot import decode_cv_plot_array_bytes

plots = tuple(decode_cv_plot_array_bytes(plot_array_bytes))
```

The input must start with plot `(0, 0)`, contain complete rows in coordinate
order, and end immediately after the final plot.

## Result

Each yielded `CvPlot` is a data class. It contains every confirmed serialized
field, plus:

- `byte_offset`: the record's absolute starting offset in the decompressed
  payload
- `byte_length`: the complete variable record length

The result includes the fixed 80-entry arrays stored inside each plot. These
arrays describe per-player or per-team state for that plot; they are not
separate `CvPlayer` or `CvTeam` records.

Plot type, terrain, route, and river flow are returned as `IntEnum` values.
They remain comparable to their serialized integers while also providing
readable names.

City and unit references are returned as data classes with `owner` and
`object_id` attributes. A plot's `working_city` assigns it to a city's
catchment; it does not prove that a citizen is currently working the plot.
Plot unit references do not contain unit types.

## Database hashes

Civ V stores features, resources, improvements, revealed improvements, and
build types as four-byte hashes instead of text names. Each hashed field has
this form:

```python
HashedType(hash_value=168372657, name="IMPROVEMENT_FARM")
```

Names are resolved with the embedded Lekmod v34.11 catalogue. A zero or
unrecognized hash keeps its exact integer and uses `name=None`:

```python
HashedType(hash_value=0, name=None)
```

This preserves modded or otherwise unknown values without requiring another
function argument.

## Variable sections

Build progress contains its outer count, inner count, and entries in serialized
slot order. A nonzero build hash is followed by a signed 16-bit progress value.
Missing build slots have a zero hash and return `progress=None`.

Unit references follow the fixed invisible-visibility array. Every unit adds an
eight-byte owner and object-ID pair.

Archaeology versions 1 and 2 are supported. Version 1 does not serialize a work
field and returns `work=None`.

## Errors and validation

Malformed plot data raises `CvPlotDecodeError`. The exception message and its
`plot_index` and `offset` attributes identify where decoding failed. The offset
is absolute within the decompressed payload.

Missing or invalid embedded SQLite and `CvMap` framing raises
`Civ5SavePayloadDecodeError` before plot iteration begins.

The decoder rejects:

- Plot versions other than 7
- Invalid Boolean bytes or enum values
- Unsupported build counts
- Counts that extend beyond the supplied bytes
- Plot script data, whose string framing is not confirmed
- Unsupported archaeology versions
- Truncated records
- Coordinates that do not match the declared row-major map dimensions
