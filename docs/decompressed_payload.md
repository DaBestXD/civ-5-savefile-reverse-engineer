# Decompressed payload structure

Decompressed payload
│
├── CvGame
│   └── Variable game-level data
│
├── Embedded SQLite database
│   ├── u32 database length
│   └── SQLite database bytes
│
├── CvMap
│   ├── Map header and resource arrays
│   ├── CvPlot(map width × map height)
│   │   ├── CvPlot (0, 0)
│   │   ├── CvPlot (1, 0)
│   │   ├── …
│   │   └── Final CvPlot
│   ├── CvArea free-list
│   ├── CvLandmass free-list
│   └── AI map hints
│
├── CvTeam(64)
│
├── CvPlayer(0)
│
└── Remaining variable data
    ├── Other players
    ├── Cities
    ├── Units
    ├── AI state
    ├── Diplomacy
    ├── Treasury
    └── Other game objects
