# Player, city, and unit API

`Civ5SaveDecoder.iter_players` returns semantic records for player slots marked
`TAKEN` or `COMPUTER`. This includes defeated participants whose city and unit
tuples may be empty. The decoder does not infer alive status.

```python
from savefile_reverse_engineer import Civ5SaveDecoder

decoder = Civ5SaveDecoder("AutoSave.Civ5Save")
print(decoder.player_display_names[0])

for player in decoder.iter_players():
    print(
        player.player_index,
        player.player_type,
        player.display_name,
        player.faith,
        player.culture_x100,
    )
    for city in player.cities:
        print(city.owner_player_index, city.city_id, city.name_key, city.population)
        for state in city.buildings:
            if state.real_count > 0 or state.free_count > 0:
                print(state.building_type.key)
    for unit in player.units:
        print(unit.owner_player_index, unit.unit_id, unit.unit_name, unit.x, unit.y)
```

`iter_cities()` and `iter_units()` flatten the participant-owned nested
records. Every returned city and unit carries its `owner_player_index`.
Each city also provides the saved localization key through `city.name_key`,
for example `TXT_KEY_CITY_NAME_VENEZ`.

`player_display_names` is a cached, read-only mapping from every participating
player index to the same resolved `display_name` exposed by `iter_players()`.
Its values can be `None` when the save does not contain enough information to
resolve a display name.

Each unit provides the authoritative serialized database type hash through
`unit_hash` and its known Lekmod v34.11 `UNIT_*` key through `unit_name`.
Unknown hashes retain their integer value and use `None` for `unit_name`.

Each player provides its saved multiplayer nickname through
`player.display_name`. A computer-controlled major civilization uses its
`leader_key`. A computer-controlled city state uses its first saved city's
`name_key`, such as `TXT_KEY_CITYSTATE_GENEVA`. A defeated city state with no
remaining city uses `None`.

`player.player_type` is a `PlayerType` enum value: `PLAYER`, `COMPUTER`,
`CITY_STATE`, or `BARBARIAN`.

Semantic records omit byte locations, serialization versions, free-list slot
metadata, and zero-hash building placeholders. City-wide building values are
available through `city.building_stats`.

## Exact raw records

Use the raw decoder when all 64 records or free-list metadata are required:

```python
from savefile_reverse_engineer.raw import decode_player_array_bytes

players = tuple(decode_player_array_bytes(exact_player_array_bytes))
print(players[0].byte_offset)
print(players[0].cities.slot_count)
print(players[0].cities.entries[0].buildings.version)
```

The input must contain exactly 64 player records and no leading or trailing
data. Raw results preserve live-slot order, deleted-slot metadata, exact record
boundaries, and all 268 building inventory slots.

Malformed records raise `CvPlayerDecodeError` with `player_index`, `offset`,
and `field` context.

## Compatibility limits

The supported raw layout is Lekmod v34.11: `CvPlayer` version 16, `CvCity`
version 6, `CvUnit` version 9, and the pinned 8,192-slot free-list ID mask. The
decoder does not yet expose player AI subobjects, treasury, diplomacy, city
citizens, building yield changes, Great Work assignments, unit promotions,
unit missions, or army entries.

See the [player, city, and unit byte layout](player-information.md) for exact
serialization details.
