# CIV 5 Save File Reverse Engineer

The package currently includes bytes-only decoders for the physical build
403694 save header and for Lekmod v34.11 `CvPlot` arrays. See
`docs/civ5-header-decoder.md` and `docs/cv-plot-decoder.md` for their supported
layouts and APIs.

## Project Goals

- Should be able to read important game information from a Civ 5 save file
  - gold, culture, science, faith, etc.
  - unit information, what type and where
  - what tile are being worked(citizen management)
