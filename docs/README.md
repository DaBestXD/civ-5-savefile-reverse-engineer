# Documentation

The documentation is split into API guides and byte-layout references. Use the
API guides when writing Python code. Use the format references when studying or
extending the save parser.

## Suggested reading order

1. [Complete save and payload layout](byte-layout.md) explains the physical
   container and the top-level decompressed structure.
2. [Physical header format](civ5-header-format.md) documents the uncompressed
   header and how the compressed-data boundary is found.
3. Read the guide for the decoder you need:
   - [Header and payload API](civ5-header-decoder.md)
   - [`CvPlot` API](cv-plot-decoder.md)
   - [`CvTeam` API](cv-team-decoder.md)
   - [`CvPlayer` API](cv-player-decoder.md)
4. For byte-level details, use the matching format reference:
   - [`CvMap` and `CvPlot` byte layout](map-information.md)
   - [`CvTeam` byte layout](team-information.md)
   - [`CvPlayer`, `CvCity`, and `CvUnit` byte layout](player-information.md)

## Scope

The physical-header parser supports Civilization V build 403694, outer save
version 8, slot-hint version 3, `CvPreGame` archive version 6, and
`CvWorldInfo` version 2.

The structured payload decoders support the examined Lekmod v34.11 layout.
They are not general parsers for vanilla Civilization V, other mods, or later
Lekmod versions. Each format reference distinguishes confirmed fields from
unknown or partly decoded regions.

Files under `tests/test_data` contain fixture-specific provenance. Their values
are test evidence, not universal format rules.
