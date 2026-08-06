# CvPlot array decoder

The CvPlot decoder reads only the serialized plot array. It does not read a
physical `.CIV5SAVE` file, decompress save chunks, locate `CvMap`, or decode the
`CvArea`, `CvLandmass`, `CvPlayer`, or `CvTeam` sections.

The supported layout is:

- Lekmod v34.11
- `CvPlot` serialization version 7
- Little-endian integers
- 80 player and team slots embedded in each plot
- 22 no-settling flags embedded in each plot
- Seven yields
- No plot script data

## Input and iteration

Call `decode_cv_plot_array` with one `bytes` value containing every plot. The
first byte must be the start of plot `(0, 0)`. The final byte must be the end of
the final plot's `CvArchaeologyData`.

```python
from pathlib import Path

from savefile_reverse_engineer import decode_cv_plot_array

plot_array_bytes = Path("plot-array.bin").read_bytes()

for plot in decode_cv_plot_array(plot_array_bytes):
    print(plot["x"], plot["y"], plot["terrain"])
```

The function returns a lazy iterator. A record is parsed immediately before it
is yielded. Errors later in the byte sequence are therefore raised when the
iterator reaches those bytes. Consume the iterator fully when the whole array
must be validated.

The decoder infers map width when the coordinates move from the first row to
the second. It checks all later coordinates against row-major order and checks
that the final row is complete. A one-row array is also valid.

## Result

Each yielded `CvPlot` is a `TypedDict`. It contains every confirmed serialized
field, plus:

- `byte_offset`: the record's starting offset within the supplied bytes
- `byte_length`: the complete variable record length

The result includes the fixed 80-entry arrays stored inside each plot. These
arrays describe per-player or per-team state for that plot; they are not
separate `CvPlayer` or `CvTeam` records.

Plot type, terrain, route, and river flow are returned as `IntEnum` values.
They remain comparable to their serialized integers while also providing
readable names.

City and unit references are returned as dictionaries with `owner` and
`object_id`. A plot's `working_city` assigns it to a city's catchment; it does
not prove that a citizen is currently working the plot.

## Database hashes

Civ V stores features, resources, improvements, revealed improvements, and
build types as four-byte hashes instead of text names. Each hashed field has
this form:

```python
{"hash_value": 168372657, "name": "IMPROVEMENT_FARM"}
```

Names are resolved with the embedded Lekmod v34.11 catalogue. A zero or
unrecognized hash keeps its exact integer and uses `name=None`:

```python
{"hash_value": 0, "name": None}
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

Malformed input raises `CvPlotDecodeError`. The exception message and its
`plot_index` and `offset` attributes identify where decoding failed.

The decoder rejects:

- Empty input
- Plot versions other than 7
- Invalid Boolean bytes or enum values
- Unsupported build counts
- Counts that extend beyond the supplied bytes
- Plot script data, whose string framing is not confirmed
- Unsupported archaeology versions
- Truncated records or trailing non-plot bytes
- Coordinates that are not a complete row-major rectangle
