# Documentation

The documentation is split into public semantic API guides and contributor
byte-layout references. The byte-exact `_raw` package is private and may change
without notice.

Public models can be imported from the package root or from the matching
`game`, `map`, `player`, or `team` module. Public errors are also available
from the `errors` module.

## Suggested reading order

1. Read the guide for the data you need:
   - [Save summary and settings API](civ5-header-decoder.md)
   - [`CvPlot` API](cv-plot-decoder.md)
   - [`CvTeam` API](cv-team-decoder.md)
   - [Player, city, and unit API](cv-player-decoder.md)
2. For byte-level details, start with the
   [complete save and payload layout](byte-layout.md), then use the matching
   format reference:
   - [Physical header format](civ5-header-format.md)
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

## Remaining decoding gaps

Private parsers still consume confirmed fields that are not represented in raw
models. Every such production-path gap uses the exact `TODO(decoding):` prefix.
Run `rg "TODO\(decoding\)" src` for the authoritative inventory before adding
or changing raw fields. Padding, reserved bytes, validation rereads, and values
already represented elsewhere are not part of that inventory.
