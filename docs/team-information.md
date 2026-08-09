<!-- markdownlint-disable -->
# CvTeam Information

This document describes the `CvTeam` objects found in the examined Lekmod
v34.11 saves. It describes the bytes that are actually present in those saves.
For the public Python API, see the [CvTeam array decoder](cv-team-decoder.md).

Each save contains 64 consecutive `CvTeam` objects immediately after `CvMap`.
Each examined object is `0x3424` bytes.

```text
CvTeam[i]   = CvMap_end + (i * 0x3424)
CvPlayer[0] = CvMap_end + 0xD0900
```

The size is specific to the examined ruleset and saved catalogue counts. A
different mod or version can produce a different size.

## Simple structure

`CvTeam` [`0x3424` bytes]<br>
├─ fixed team counters and identifiers [`+0x0000..+0x0093`]<br>
├─ team, war, diplomacy, and movement arrays [`+0x0094..+0x083B`]<br>
├─ hashed victory, route, build, project, unit, building, and terrain arrays [`+0x083C..+0x1D0F`]<br>
├─ turn-met array [`+0x1D10..+0x1E0B`]<br>
├─ `CvTeamTechs` [`+0x1E0C..+0x2327`]<br>
├─ improvement yield changes [`+0x2328..+0x28CF`]<br>
├─ no-fresh-water improvement yield changes [`+0x28D0..+0x2E77`]<br>
├─ fresh-water improvement yield changes [`+0x2E78..+0x341F`]<br>
└─ revealed-resource vector [`+0x3420..+0x3423`]

## Fixed fields

All fields in this section are four bytes unless marked otherwise.

| Offset | Field |
|---:|---|
| `+0x0000` | Serialization version, currently `1` |
| `+0x0004` | Number of team members |
| `+0x0008` | Alive-member count |
| `+0x000C` | Ever-alive-member count |
| `+0x0010` | Number of cities |
| `+0x0014` | Total population |
| `+0x0018` | Total land |
| `+0x001C` | Nuclear interception modifier |
| `+0x0020` | Extra water visibility count |
| `+0x0024` | Map-trading count |
| `+0x0028` | Technology-trading count |
| `+0x002C` | Gold-trading count |
| `+0x0030` | Embassy-trading count |
| `+0x0034` | Open-border-trading count |
| `+0x0038` | Defensive-pact-trading count |
| `+0x003C` | Research-agreement-trading count |
| `+0x0040` | Trade-agreement-trading count |
| `+0x0044` | Permanent-alliance-trading count |
| `+0x0048` | Bridge-building count |
| `+0x004C` | Water-working count |
| `+0x0050` | River-trading count |
| `+0x0054` | Border-obstacle count |
| `+0x0058` | Victory points |
| `+0x005C` | Extra embarked movement |
| `+0x0060` | Extra embarked sight added by Lekmod |
| `+0x0064` | Can-embark count |
| `+0x0068` | Defensive-embark count |
| `+0x006C` | All-water-passage count |
| `+0x0070` | Natural wonders discovered |
| `+0x0074` | Best possible route |
| `+0x0078` | Number of minor civilizations attacked |
| `+0x007C` | Eight one-byte team flags |
| `+0x0084` | Team ID |
| `+0x0088` | Current era |
| `+0x008C` | Team that liberated this team |
| `+0x0090` | Team that killed this team |

The flags begin at `+0x007C`, not `+0x0078`:

| Offset | Flag |
|---:|---|
| `+0x007C` | Map centering |
| `+0x007D` | Has broken a peace treaty |
| `+0x007E` | Home of the United Nations |
| `+0x007F` | Has technology for the World Congress |
| `+0x0080` | Broken military promise |
| `+0x0081` | Broken expansion promise |
| `+0x0082` | Broken border promise |
| `+0x0083` | Broken city-state promise |

## Team and diplomacy arrays

| Range | Field |
|---:|---|
| `+0x0094..+0x0193` | Technology-sharing count for each of 64 teams |
| `+0x0194..+0x0293` | Turns at war with each team |
| `+0x0294..+0x0393` | Turns locked into war with each team |
| `+0x0394..+0x03A7` | Extra movement for five domains |
| `+0x03A8..+0x03BB` | Hashed vote-source eligibility |
| `+0x03BC..+0x04BB` | Turn peace was made with each team |
| `+0x04BC..+0x05BB` | Ignore-warning count for each team |
| `+0x05BC..+0x05FB` | Has met each team |
| `+0x05FC..+0x063B` | Has found each team's territory |
| `+0x063C..+0x067B` | Is at war with each team |
| `+0x067C..+0x06BB` | Permanent war or peace |
| `+0x06BC..+0x06FB` | Has embassy |
| `+0x06FC..+0x073B` | Has open borders |
| `+0x073C..+0x077B` | Has defensive pact |
| `+0x077C..+0x07BB` | Has research agreement |
| `+0x07BC..+0x07FB` | Has trade agreement |
| `+0x07FC..+0x083B` | Force-peace state |

Each relationship Boolean array contains 64 one-byte values.

## Hashed gameplay arrays

These arrays serialize database type hashes. A zero hash has no following
value.

| Range | Field |
|---:|---|
| `+0x083C..+0x085D` | Can launch each victory |
| `+0x085E..+0x087F` | Victory achieved |
| `+0x0880..+0x0883` | Small awards; zero slots in these saves |
| `+0x0884..+0x0897` | Route changes |
| `+0x0898..+0x0AC3` | Build-time changes |
| `+0x0AC4..+0x0AF7` | Project counts |
| `+0x0AF8..+0x0B2B` | Default project art |
| `+0x0B2C..+0x0B47` | Project-art section |
| `+0x0B48..+0x0B7B` | Projects being constructed |
| `+0x0B7C..+0x0EB7` | Unit-class counts |
| `+0x0EB8..+0x143B` | Building-class counts |
| `+0x143C..+0x1C8F` | Obsolete-building counts |
| `+0x1C90..+0x1CDB` | Terrain-trade counts |
| `+0x1CDC..+0x1D0F` | Victory countdowns |
| `+0x1D10..+0x1E0B` | Turn each of 63 civil teams was met |

For a hashed array with `C` saved slots, `V` nonzero hashes, and a value width
of `w` bytes:

```text
size = 4 + (4 * C) + (w * V)
```

## CvTeamTechs

`CvTeamTechs` starts at `+0x1E0C` and is `0x51C` bytes in these saves.

| Offset | Field |
|---:|---|
| `+0x1E0C` | Version, currently `1` |
| `+0x1E10` | Last technology acquired, stored as an index |
| `+0x1E14` | Technology count, currently `81` |
| `+0x1E18` | 81 technology hashes |
| `+0x1F5C` | 81 has-technology Booleans |
| `+0x1FAD` | 81 obtained-by-human Booleans |
| `+0x1FFE` | 81 obtained-for-league Booleans |
| `+0x204F` | 81 cannot-trade-technology Booleans |
| `+0x20A0` | 81 research-progress values |
| `+0x21E4` | 81 repeat-technology acquisition counts |
| `+0x2328` | End of `CvTeamTechs` |

Research progress is an `i32` stored in hundredths.

For `N` technologies:

```text
CvTeamTechs size = 12 + (16 * N)
```

Technology identity must be obtained from the serialized hashes. The last-tech
field is an index into the same technology list.

## Improvement yield arrays

Three hashed improvement arrays follow `CvTeamTechs`:

| Range | Field |
|---:|---|
| `+0x2328..+0x28CF` | General improvement yield changes |
| `+0x28D0..+0x2E77` | Improvement yields without fresh water |
| `+0x2E78..+0x341F` | Improvement yields with fresh water |

Lekmod v34.11 has seven yields:

1. Food
2. Production
3. Gold
4. Science
5. Culture
6. Faith
7. Golden Age Points

Each array contains 46 improvement slots and 45 valid hashes:

```text
4 + (46 * 4) + (45 * 7 * 4) = 0x5A8
```

## Final field

At `+0x3420` is the revealed-resource vector count. It is zero in every
examined record, so the record ends four bytes later at `+0x3424`.

In general:

```text
revealed_resource_vector_size = 4 + (4 * resource_count)
```

## Decoder cautions

- The examined saves omit three route-cost integers that are enabled in the
  pinned v34.11 source. Follow the confirmed save offsets for these files.
- Serialization version `1` is not enough to select a layout because
  incompatible mod layouts use the same version.
- Database catalogue changes alter hashed-array sizes.
- Project art and the revealed-resource vector can make the record variable.
- Lekmod v34.14 adds a 64-byte peace-lock array after revealed resources.
- Later v35 work adds Tourism as another yield. Neither change belongs in a
  v34.11 decoder.

## Source references

- [Lekmod v34.11 commit](https://github.com/EnormousApplePie/Lekmod/commit/f4b96af9200470ab8fe50dee3dad0dce89c16975)
- [`CvTeam::Read/Write`](https://github.com/EnormousApplePie/Lekmod/blob/f4b96af9200470ab8fe50dee3dad0dce89c16975/LEKMOD_DLL/CvGameCoreDLL_Expansion2/CvTeam.cpp#L7715-L8022)
- [`CvTeamTechs::Read/Write`](https://github.com/EnormousApplePie/Lekmod/blob/f4b96af9200470ab8fe50dee3dad0dce89c16975/LEKMOD_DLL/CvGameCoreDLL_Expansion2/CvTechClasses.cpp#L1969-L2083)
- [Lekmod database catalogue](https://github.com/EnormousApplePie/Lekmod/blob/f4b96af9200470ab8fe50dee3dad0dce89c16975/LEKMOD/Override/CIV5Units.xml)
