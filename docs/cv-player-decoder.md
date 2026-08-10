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
    print([policy.key for policy in player.policy_information.owned_policies])
    for branch in player.policy_information.branches:
        if branch.unlocked:
            print(
                branch.branch_type.key,
                [policy.key for policy in branch.owned_policies],
            )
    for city in player.cities:
        print(city.owner_player_index, city.city_id, city.name_key, city.population)
        if city.current_production is not None:
            print("producing", city.current_production.item_type.key)
            if city.current_production.production_x100 is not None:
                print(
                    "building progress",
                    city.current_production.production_x100 / 100,
                )
        for state in city.buildings:
            print(state.building_type.key)
    for unit in player.units:
        print(
            decoder.get_owner_display_name(unit),
            unit.unit_id,
            unit.unit_name,
            unit.x,
            unit.y,
        )
```

`iter_cities()` and `iter_units()` flatten the participant-owned nested
records. Every returned city and unit carries its `owner_player_index`.
Each city also provides the saved localization key through `city.name_key`,
for example `TXT_KEY_CITY_NAME_VENEZ`.

Each semantic `iter_*()` result is cached after its iterator is consumed
successfully. Later calls return fresh iterators over the same immutable
objects. A partially consumed or failed iteration is not cached.

`player_display_names` is a cached, read-only mapping from every participating
player index to the same resolved `display_name` exposed by `iter_players()`.
Its values can be `None` when the save does not contain enough information to
resolve a display name.

`get_owner_display_name(plot_or_city_or_unit)` resolves an owned semantic
object directly. Its first call decodes and caches all participating players
when they have not already been loaded. Later calls use the cached mapping.

Each unit provides the authoritative serialized database type hash through
`unit_hash` and its known Lekmod v34.11 `UNIT_*` key through `unit_name`.
Unknown hashes retain their integer value and use `None` for `unit_name`.

Each player provides its saved multiplayer nickname through
`player.display_name`. A computer-controlled major civilization uses its
`leader_key`. A computer-controlled city state uses its first saved city's
`name_key`, such as `TXT_KEY_CITYSTATE_GENEVA`. A defeated city state with no
remaining city uses `None`.

`player.policy_information.owned_policies` contains every saved policy whose
owned flag is set. This includes branch openers, selected policies,
automatically granted finishers, ideology tenets, and internal dummy policies.
It is an inventory, not a count of culture purchases. Known hashes resolve to
stable keys such as `POLICY_TRADITION`; unknown hashes retain their integer
value and use `None` for the key.

`player.policy_information.branches` contains all 12 policy branches. Each
entry exposes its stable branch key, confirmed `unlocked` state, and the owned
policies assigned to that branch by the pinned Lekmod v34.11 catalogue.

`player.player_type` is a `PlayerType` enum value: `PLAYER`, `COMPUTER`,
`CITY_STATE`, or `BARBARIAN`.

Semantic records omit byte locations, serialization versions, free-list slot
metadata, zero-hash building placeholders, and building types that are not
present in a city. `city.buildings` includes a state when its `real_count` or
`free_count` is positive. This can include active internal or dummy buildings.
City-wide building values are available through `city.building_stats`.

Use the raw city record's `buildings.entries` inventory for absent building
types and saved production toward buildings that are not yet present.

`city.production_queue` contains every saved production order in queue order.
Its entries use `ProductionOrderType` to distinguish units, buildings,
projects, specialists, and processes. `city.current_production` is the first
queue entry, or `None` when the queue is empty.

Every semantic production order has optional `production_x100` progress and
`production_inactive_turns` decay-counter fields. They contain integers for a
building order and are `None` for other order types whose progress is not yet
decoded. Divide `production_x100` by 100 to obtain ordinary production points.

`city.yield_vectors` exposes the 18 seven-value vectors serialized by
Lekmod v34.11. Every vector has named `food`, `production`, `gold`, `science`,
`culture`, `faith`, and `golden_age_points` fields. The named vectors cover
plot bonuses; base yields from terrain, buildings, specialists, miscellaneous
sources, religion, and policies; garrison bonuses; per-population and
per-religion yields; rate modifiers; extra specialist yields; and
production-to-yield conversion. Fields ending in `_x100` store hundredths.

For example, the saved building and ordinary-population science components are
available without reconstructing them from the building catalogue:

```python
for city in decoder.iter_cities():
    vectors = city.yield_vectors
    print(
        city.name_key,
        vectors.base_yield_rate_from_buildings.science,
        vectors.base_yield_rate_from_misc.science,
        vectors.yield_per_population_x100.science,
    )
```

These are saved intermediate values, not a precomputed final yield. Final city
science can also depend on city status, owner and area modifiers, active
garrison state, Great Works, production conversion, and trade routes.

## Exact raw records

Use the raw decoder when all 64 records or free-list metadata are required:

```python
from savefile_reverse_engineer.raw import decode_player_array_bytes

players = tuple(decode_player_array_bytes(exact_player_array_bytes))
print(players[0].byte_offset)
print(players[0].cities.slot_count)
print(players[0].cities.entries[0].buildings.version)
print(players[0].cities.entries[0].production_queue)
```

The input must contain exactly 64 player records and no leading or trailing
data. Raw results preserve live-slot order, deleted-slot metadata, exact record
boundaries, all 268 building inventory slots, and exact production queue
entries.

Malformed records raise `CvPlayerDecodeError` with `player_index`, `offset`,
and `field` context.

## Compatibility limits

The supported raw layout is Lekmod v34.11: `CvPlayer` version 16, `CvCity`
version 6, `CvUnit` version 9, and the pinned 8,192-slot free-list ID mask. The
decoder does not yet expose player AI subobjects, treasury, diplomacy, city
citizens, uncertain policy-branch arrays after the unlocked state, building
yield changes, Great Work assignments, unit promotions, unit missions, or army
entries.

See the [player, city, and unit byte layout](player-information.md) for exact
serialization details.
