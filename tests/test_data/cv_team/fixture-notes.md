# CvTeam fixture

`turn_76_team_array.bin` contains only the complete 64-record `CvTeam[]` byte
sequence from `AutoSave_Post_0076 AD-0040.Civ5Save`.

- Lekmod: v34.11
- Team count: 64
- Decompressed source range: `0x35483D..0x42513D`
- Fixture length: `0xD0900` bytes (854,272 bytes)
- SHA-256: `ff117a07791523b72ca33d596a36d1a96bcdfd37b59c021f3da29c111d5019a5`

The fixture does not contain the physical save header, compressed chunks,
`CvMap`, or the `CvPlayer` records that follow the team array.
