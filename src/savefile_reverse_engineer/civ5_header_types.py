"""Public result and enum types for the physical Civ V save header."""

from dataclasses import dataclass
from enum import IntEnum


class QuickGameMode(IntEnum):
    """Game mode stored in the quick-reference header."""

    SINGLE_PLAYER = 0
    MULTIPLAYER = 1
    HOTSEAT = 2


class ArchiveGameMode(IntEnum):
    """Game mode stored in the CvPreGame archive."""

    NONE = -1
    NORMAL = 0
    PITBOSS = 1


class GameMapType(IntEnum):
    """How the map was selected."""

    USER_PARAMETERS = 0
    SCENARIO = 1


class SlotClaim(IntEnum):
    """Reservation state for one player slot."""

    UNASSIGNED = 0
    RESERVED = 1
    ASSIGNED = 2


class SlotStatus(IntEnum):
    """Occupancy state for one player slot."""

    OPEN = 0
    COMPUTER = 1
    CLOSED = 2
    TAKEN = 3
    OBSERVER = 4


@dataclass(slots=True)
class UnknownHeaderSpan:
    """Header bytes whose framing is known but whose meaning is not."""

    label: str
    byte_offset: int
    byte_length: int
    data: bytes


@dataclass(slots=True)
class EnabledDlc:
    """One enabled-content entry in the quick header."""

    guid: str
    value: int
    name: str


@dataclass(slots=True)
class EnabledMod:
    """One formal mod entry in the quick header."""

    guid: str
    value: int
    name: str


@dataclass(slots=True)
class QuickHeader:
    """The quick-reference fields at the start of a physical save."""

    signature: str
    outer_version: int
    game_version: str
    build: str
    turn: int
    game_mode: QuickGameMode
    active_civilization: str
    difficulty: str
    starting_era: str
    current_era: str
    game_speed: str
    world_size: str
    map_script: str
    enabled_dlc: tuple[EnabledDlc, ...]
    enabled_mods: tuple[EnabledMod, ...]
    player_color: str


@dataclass(slots=True)
class PlayerSlot:
    """One of the 64 entries combined from the slot-hint arrays."""

    index: int
    civilization_index: int
    raw_nickname: str
    display_name: str | None
    steam_id: str | None
    status: SlotStatus
    claim: SlotClaim
    team: int
    handicap: int
    civilization_key: str
    leader_key: str


@dataclass(slots=True)
class SlotHints:
    """The compact pregame slot setup stored before the full archive."""

    version: int
    game_speed: int
    world_size: int
    map_script: str
    players: tuple[PlayerSlot, ...]


@dataclass(slots=True)
class BaseInfo:
    """Fields serialized by CvBaseInfo."""

    id: int
    civilopedia: str
    description: str
    help: str
    disabled_help: str
    strategy: str
    type: str
    text_key: str
    text: str


@dataclass(slots=True)
class ClimateInfo(BaseInfo):
    """Serialized climate database row."""

    desert_percent_change: int
    jungle_latitude: int
    hill_range: int
    mountain_percent: int
    snow_latitude_change: float
    tundra_latitude_change: float
    grass_latitude_change: float
    desert_bottom_latitude_change: float
    desert_top_latitude_change: float
    ice_latitude: float
    random_ice_latitude: float


@dataclass(slots=True)
class SeaLevelInfo(BaseInfo):
    """Serialized sea-level database row."""

    sea_level_change: int


@dataclass(slots=True)
class TurnTimerInfo(BaseInfo):
    """Serialized turn-timer database row."""

    base_time: int
    city_resource: int
    unit_resource: int
    first_turn_multiplier: int


@dataclass(slots=True)
class WorldInfo(BaseInfo):
    """Serialized version-2 world-size database row."""

    version: int
    default_players: int
    default_minor_civs: int
    fog_tiles_per_barbarian_camp: int
    num_natural_wonders: int
    unit_name_modifier: int
    target_num_cities: int
    num_free_building_resources: int
    building_class_prereq_modifier: int
    max_conscript_modifier: int
    grid_width: int
    grid_height: int
    max_active_religions: int
    terrain_grain_change: int
    feature_grain_change: int
    research_percent: int
    advanced_start_points_modifier: int
    num_cities_unhappiness_percent: int
    num_cities_policy_cost_modifier: int
    num_cities_tech_cost_modifier: int


@dataclass(slots=True)
class CustomOption:
    """One named game or map option."""

    name: str
    value: int


@dataclass(slots=True)
class PreGameArchive:
    """Every field written by build 403694 CvPreGame archive version 6."""

    version: int
    active_player: int
    admin_password: str
    advanced_start_points: int
    alias: str
    art_styles: tuple[int, ...]
    autorun: bool
    autorun_turn_delay: float
    autorun_turn_limit: int
    bandwidth: int
    calendar: int
    calendar_info: BaseInfo
    civilization_adjectives: tuple[str, ...]
    civilization_descriptions: tuple[str, ...]
    civilization_passwords: tuple[str, ...]
    civilization_short_descriptions: tuple[str, ...]
    climate: int
    climate_info: ClimateInfo
    era: int
    email_addresses: tuple[str, ...]
    end_turn_timer_length: float
    flag_decals: tuple[str, ...]
    deprecated_force_controls: tuple[bool, ...]
    game_mode: ArchiveGameMode
    game_name: str
    game_speed: int
    game_started: bool
    game_turn: int
    game_type: int
    game_map_type: GameMapType
    game_update_time: int
    handicaps: tuple[int, ...]
    last_human_handicaps: tuple[int, ...]
    is_earth_map: bool
    is_internet_game: bool
    leader_names: tuple[str, ...]
    load_file_name: str
    local_player_email_address: str
    map_has_no_players: bool
    map_random_seed: int
    load_world_builder_scenario: bool
    override_scenario_handicap: bool
    map_script_name: str
    max_city_elimination: int
    max_turns: int
    num_minor_civs: int
    minor_civ_types: tuple[str, ...]
    minor_nation_civs: tuple[bool, ...]
    dummy_value: bool
    multiplayer_options: tuple[bool, ...]
    network_ids: tuple[int, ...]
    nicknames: tuple[str, ...]
    num_victory_infos: int
    pit_boss_turn_time: int
    playable_civs: tuple[bool, ...]
    player_colors: tuple[str, ...]
    private_game: bool
    quick_combat: bool
    quick_combat_default: bool
    quick_handicap: int
    quickstart: bool
    random_world_size: bool
    random_map_script: bool
    ready_players: tuple[bool, ...]
    sea_level: int
    sea_level_info: SeaLevelInfo
    dummy_value_2: bool
    slot_claims: tuple[SlotClaim, ...]
    slot_statuses: tuple[SlotStatus, ...]
    smtp_host: str
    sync_random_seed: int
    target_score: int
    team_types: tuple[int, ...]
    transferred_map: bool
    turn_timer: TurnTimerInfo
    turn_timer_type: int
    city_screen_blocked: bool
    victories: tuple[bool, ...]
    white_flags: tuple[bool, ...]
    world_info: WorldInfo
    world_size: int
    game_options: tuple[CustomOption, ...]
    map_options: tuple[CustomOption, ...]
    version_string: str
    turn_notify_steam_invite: tuple[bool, ...]
    turn_notify_email: tuple[bool, ...]
    turn_notify_email_addresses: tuple[str, ...]


@dataclass(slots=True)
class CompressedChunk:
    """Physical location of one compressed payload chunk."""

    length_offset: int
    data_offset: int
    length: int


@dataclass(slots=True)
class Civ5SaveHeader:
    """Decoded physical save header and validated payload-container metadata."""

    header_length: int
    first_chunk_length_offset: int
    zlib_offset: int
    compression_type: int
    quick: QuickHeader
    slot_hints: SlotHints
    pregame: PreGameArchive
    unknown_spans: tuple[UnknownHeaderSpan, ...]
    compressed_chunks: tuple[CompressedChunk, ...]
