# CIV 5 Save File Reverse Engineer

The package provides a path-based `Civ5SaveDecoder` for the physical build
403694 save header, decompressed payload, and Lekmod v34.11 `CvPlot` array. See
`docs/civ5-header-decoder.md` and `docs/cv-plot-decoder.md` for their supported
layouts and APIs.

```python
from savefile_reverse_engineer import Civ5SaveDecoder

decoder = Civ5SaveDecoder("AutoSave.Civ5Save")
print(decoder.header.quick.turn)

for plot in decoder.iter_cv_plots():
    print(plot.x, plot.y, plot.terrain)
```

## Project Goals

- Should be able to read important game information from a Civ 5 save file
  - gold, culture, science, faith, etc.
  - unit information, what type and where
  - what tile are being worked(citizen management)
