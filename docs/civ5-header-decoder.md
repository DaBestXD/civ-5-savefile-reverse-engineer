# Save summary, settings, and payload API

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
and serialization versions. Those exact values remain available from
`raw_header`.

`player_slots` contains all 64 saved slots with explicit `player_index`,
`team_index`, and `handicap_index` fields.

All three values are immutable and cached. Repeated property access returns the
same object.

## Payload and exact header

`payload_bytes` returns the cached complete decompressed payload:

```python
payload = decoder.payload_bytes
```

Use `raw_header` when physical offsets, compressed chunk framing, unknown
spans, the exact quick header, or the complete `CvPreGame` archive are needed:

```python
header = decoder.raw_header
print(header.quick.outer_version)
print(header.pregame.version_string)
print(header.compressed_chunks[0].data_offset)
```

The raw header can contain passwords and email addresses. Do not log it without
considering those values.

Callers that already hold complete save bytes can use the raw functions:

```python
from savefile_reverse_engineer.raw import (
    decode_header_bytes,
    decompress_payload_bytes,
)

header = decode_header_bytes(save_bytes)
payload = decompress_payload_bytes(save_bytes, header)
```

Malformed headers raise `Civ5SaveHeaderDecodeError`. Invalid compressed data
raises `Civ5SavePayloadDecompressionError`. Invalid payload framing raises
`Civ5SavePayloadDecodeError`.
