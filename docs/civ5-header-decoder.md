# Save summary and settings API

`Civ5SaveDecoder` reads one complete physical `.CIV5SAVE` file and keeps one
stable in-memory snapshot. Header decoding is deferred until a header-backed
property is first accessed.

```python
from savefile_reverse_engineer import Civ5SaveDecoder

decoder = Civ5SaveDecoder("AutoSave.Civ5Save")

print(decoder.summary.turn)
print(decoder.summary.active_civilization_key)
print(decoder.settings.game_name)

for slot in decoder.player_slots:
    if slot.display_name is not None:
        print(slot.player_index, slot.display_name, slot.team_index)
```

## Semantic sections

`summary` contains browser-friendly metadata: game version and build, turn,
mode, civilization, difficulty, eras, speed, world size, map script, enabled
content, and player color. Database identifiers use the `_key` suffix.

`settings` contains common non-sensitive game settings. It intentionally omits
passwords, email addresses, SMTP configuration, network arrays, dummy fields,
and serialization versions.

`player_slots` contains all 64 saved slots with explicit `player_index`,
`team_index`, and `handicap_index` fields.

All three values are immutable and cached. Repeated property access returns the
same object.

Malformed headers raise `Civ5SaveHeaderDecodeError`. Invalid compressed data
raises `Civ5SavePayloadDecompressionError`. Invalid payload framing raises
`Civ5SavePayloadDecodeError`.
