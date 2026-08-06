"""Decode the physical header of supported Civilization V save files."""

from enum import IntEnum
from typing import NoReturn, override
from uuid import UUID

from ._binary_reader import LittleEndianReader
from .civ5_header_types import (
    ArchiveGameMode,
    BaseInfo,
    Civ5SaveHeader,
    ClimateInfo,
    CompressedChunk,
    CustomOption,
    EnabledDlc,
    GameMapType,
    PlayerSlot,
    PreGameArchive,
    QuickGameMode,
    QuickHeader,
    SeaLevelInfo,
    SlotClaim,
    SlotHints,
    SlotStatus,
    TurnTimerInfo,
    UnknownHeaderSpan,
    WorldInfo,
)

_SIGNATURE = b"CIV5"
_OUTER_VERSION = 8
_BUILD = "403694"
_SLOT_HINT_VERSION = 3
_PREGAME_VERSION = 6
_WORLD_INFO_VERSION = 2
_PLAYER_COUNT = 64
_FORCE_CONTROL_COUNT = 7
_COMPRESSION_TYPE = 2


class Civ5SaveHeaderDecodeError(ValueError):
    """A malformed or unsupported value in a physical Civ V save header."""

    offset: int
    field: str

    def __init__(self, message: str, *, offset: int, field: str) -> None:
        self.offset = offset
        self.field = field
        super().__init__(f"{field} at physical byte offset 0x{offset:X}: {message}")


class _HeaderReader(LittleEndianReader):
    __slots__: tuple[str, ...] = ()

    @override
    def fail(
        self,
        message: str,
        *,
        offset: int | None = None,
        field: str | None = None,
    ) -> NoReturn:
        raise Civ5SaveHeaderDecodeError(
            message,
            offset=self.offset if offset is None else offset,
            field="header" if field is None else field,
        )


def _require_value(
    reader: _HeaderReader,
    value: int | str,
    expected: int | str,
    *,
    field: str,
    offset: int,
) -> None:
    if value != expected:
        reader.fail(
            f"unsupported value {value!r}; expected {expected!r}",
            offset=offset,
            field=field,
        )


def _enum_value[EnumType: IntEnum](
    reader: _HeaderReader,
    enum_type: type[EnumType],
    value: int,
    *,
    field: str,
    offset: int,
) -> EnumType:
    try:
        return enum_type(value)
    except ValueError:
        reader.fail(
            f"unsupported {enum_type.__name__} value {value}",
            offset=offset,
            field=field,
        )


def _read_count(
    reader: _HeaderReader,
    field: str,
    *,
    minimum_item_size: int,
    expected: int | None = None,
) -> int:
    count_offset = reader.offset
    count = reader.u32(f"{field}.count")
    reader.ensure_count_fits(
        count,
        item_size=minimum_item_size,
        reserved_bytes=0,
        field=f"{field}.count",
    )
    if expected is not None and count != expected:
        reader.fail(
            f"count is {count}, expected {expected}",
            offset=count_offset,
            field=f"{field}.count",
        )
    return count


def _read_i32_vector(
    reader: _HeaderReader, field: str, *, expected: int | None = None
) -> tuple[int, ...]:
    count = _read_count(reader, field, minimum_item_size=4, expected=expected)
    return tuple(reader.i32(f"{field}[{index}]") for index in range(count))


def _read_bool_vector(
    reader: _HeaderReader, field: str, *, expected: int | None = None
) -> tuple[bool, ...]:
    count = _read_count(reader, field, minimum_item_size=1, expected=expected)
    return tuple(reader.read_bool(f"{field}[{index}]") for index in range(count))


def _read_string_vector(
    reader: _HeaderReader, field: str, *, expected: int | None = None
) -> tuple[str, ...]:
    count = _read_count(reader, field, minimum_item_size=4, expected=expected)
    return tuple(reader.read_utf8(f"{field}[{index}]") for index in range(count))


def _read_slot_claim_vector(reader: _HeaderReader, field: str) -> tuple[SlotClaim, ...]:
    count = _read_count(reader, field, minimum_item_size=4, expected=_PLAYER_COUNT)
    values: list[SlotClaim] = []
    for index in range(count):
        offset = reader.offset
        values.append(
            _enum_value(
                reader,
                SlotClaim,
                reader.i32(f"{field}[{index}]"),
                field=f"{field}[{index}]",
                offset=offset,
            )
        )
    return tuple(values)


def _read_slot_status_vector(
    reader: _HeaderReader, field: str
) -> tuple[SlotStatus, ...]:
    count = _read_count(reader, field, minimum_item_size=4, expected=_PLAYER_COUNT)
    values: list[SlotStatus] = []
    for index in range(count):
        offset = reader.offset
        values.append(
            _enum_value(
                reader,
                SlotStatus,
                reader.i32(f"{field}[{index}]"),
                field=f"{field}[{index}]",
                offset=offset,
            )
        )
    return tuple(values)


def _read_base_info(reader: _HeaderReader, field: str) -> BaseInfo:
    return BaseInfo(
        id=reader.i32(f"{field}.id"),
        civilopedia=reader.read_utf8(f"{field}.civilopedia"),
        description=reader.read_utf8(f"{field}.description"),
        help=reader.read_utf8(f"{field}.help"),
        disabled_help=reader.read_utf8(f"{field}.disabled_help"),
        strategy=reader.read_utf8(f"{field}.strategy"),
        type=reader.read_utf8(f"{field}.type"),
        text_key=reader.read_utf8(f"{field}.text_key"),
        text=reader.read_utf8(f"{field}.text"),
    )


def _read_climate_info(reader: _HeaderReader, field: str) -> ClimateInfo:
    base = _read_base_info(reader, field)
    return ClimateInfo(
        id=base["id"],
        civilopedia=base["civilopedia"],
        description=base["description"],
        help=base["help"],
        disabled_help=base["disabled_help"],
        strategy=base["strategy"],
        type=base["type"],
        text_key=base["text_key"],
        text=base["text"],
        desert_percent_change=reader.i32(f"{field}.desert_percent_change"),
        jungle_latitude=reader.i32(f"{field}.jungle_latitude"),
        hill_range=reader.i32(f"{field}.hill_range"),
        mountain_percent=reader.i32(f"{field}.mountain_percent"),
        snow_latitude_change=reader.f32(f"{field}.snow_latitude_change"),
        tundra_latitude_change=reader.f32(f"{field}.tundra_latitude_change"),
        grass_latitude_change=reader.f32(f"{field}.grass_latitude_change"),
        desert_bottom_latitude_change=reader.f32(
            f"{field}.desert_bottom_latitude_change"
        ),
        desert_top_latitude_change=reader.f32(f"{field}.desert_top_latitude_change"),
        ice_latitude=reader.f32(f"{field}.ice_latitude"),
        random_ice_latitude=reader.f32(f"{field}.random_ice_latitude"),
    )


def _read_sea_level_info(reader: _HeaderReader, field: str) -> SeaLevelInfo:
    base = _read_base_info(reader, field)
    return SeaLevelInfo(
        id=base["id"],
        civilopedia=base["civilopedia"],
        description=base["description"],
        help=base["help"],
        disabled_help=base["disabled_help"],
        strategy=base["strategy"],
        type=base["type"],
        text_key=base["text_key"],
        text=base["text"],
        sea_level_change=reader.i32(f"{field}.sea_level_change"),
    )


def _read_turn_timer_info(reader: _HeaderReader, field: str) -> TurnTimerInfo:
    base = _read_base_info(reader, field)
    return TurnTimerInfo(
        id=base["id"],
        civilopedia=base["civilopedia"],
        description=base["description"],
        help=base["help"],
        disabled_help=base["disabled_help"],
        strategy=base["strategy"],
        type=base["type"],
        text_key=base["text_key"],
        text=base["text"],
        base_time=reader.i32(f"{field}.base_time"),
        city_resource=reader.i32(f"{field}.city_resource"),
        unit_resource=reader.i32(f"{field}.unit_resource"),
        first_turn_multiplier=reader.i32(f"{field}.first_turn_multiplier"),
    )


def _read_world_info(reader: _HeaderReader, field: str) -> WorldInfo:
    version_offset = reader.offset
    version = reader.i32(f"{field}.version")
    _require_value(
        reader,
        version,
        _WORLD_INFO_VERSION,
        field=f"{field}.version",
        offset=version_offset,
    )
    base = _read_base_info(reader, field)
    return WorldInfo(
        id=base["id"],
        civilopedia=base["civilopedia"],
        description=base["description"],
        help=base["help"],
        disabled_help=base["disabled_help"],
        strategy=base["strategy"],
        type=base["type"],
        text_key=base["text_key"],
        text=base["text"],
        version=version,
        default_players=reader.i32(f"{field}.default_players"),
        default_minor_civs=reader.i32(f"{field}.default_minor_civs"),
        fog_tiles_per_barbarian_camp=reader.i32(
            f"{field}.fog_tiles_per_barbarian_camp"
        ),
        num_natural_wonders=reader.i32(f"{field}.num_natural_wonders"),
        unit_name_modifier=reader.i32(f"{field}.unit_name_modifier"),
        target_num_cities=reader.i32(f"{field}.target_num_cities"),
        num_free_building_resources=reader.i32(f"{field}.num_free_building_resources"),
        building_class_prereq_modifier=reader.i32(
            f"{field}.building_class_prereq_modifier"
        ),
        max_conscript_modifier=reader.i32(f"{field}.max_conscript_modifier"),
        grid_width=reader.i32(f"{field}.grid_width"),
        grid_height=reader.i32(f"{field}.grid_height"),
        max_active_religions=reader.i32(f"{field}.max_active_religions"),
        terrain_grain_change=reader.i32(f"{field}.terrain_grain_change"),
        feature_grain_change=reader.i32(f"{field}.feature_grain_change"),
        research_percent=reader.i32(f"{field}.research_percent"),
        advanced_start_points_modifier=reader.i32(
            f"{field}.advanced_start_points_modifier"
        ),
        num_cities_unhappiness_percent=reader.i32(
            f"{field}.num_cities_unhappiness_percent"
        ),
        num_cities_policy_cost_modifier=reader.i32(
            f"{field}.num_cities_policy_cost_modifier"
        ),
        num_cities_tech_cost_modifier=reader.i32(
            f"{field}.num_cities_tech_cost_modifier"
        ),
    )


def _read_custom_options(reader: _HeaderReader, field: str) -> tuple[CustomOption, ...]:
    count = _read_count(reader, field, minimum_item_size=8)
    return tuple(
        CustomOption(
            name=reader.read_utf8(f"{field}[{index}].name"),
            value=reader.i32(f"{field}[{index}].value"),
        )
        for index in range(count)
    )


def _unknown_string_span(reader: _HeaderReader, label: str) -> UnknownHeaderSpan:
    start = reader.offset
    _ = reader.read_utf8(label)
    end = reader.offset
    return UnknownHeaderSpan(
        label=label,
        byte_offset=start,
        byte_length=end - start,
        data=reader.data[start:end],
    )


def _unknown_bytes_span(
    reader: _HeaderReader, label: str, length: int
) -> UnknownHeaderSpan:
    start = reader.offset
    data = reader.read_bytes(length, label)
    return UnknownHeaderSpan(
        label=label,
        byte_offset=start,
        byte_length=length,
        data=data,
    )


def _read_quick_header(
    reader: _HeaderReader,
) -> tuple[QuickHeader, tuple[UnknownHeaderSpan, ...]]:
    signature_offset = reader.offset
    signature_bytes = reader.read_bytes(4, "quick.signature")
    if signature_bytes != _SIGNATURE:
        reader.fail(
            f"signature is {signature_bytes!r}, expected {_SIGNATURE!r}",
            offset=signature_offset,
            field="quick.signature",
        )

    outer_version_offset = reader.offset
    outer_version = reader.u32("quick.outer_version")
    _require_value(
        reader,
        outer_version,
        _OUTER_VERSION,
        field="quick.outer_version",
        offset=outer_version_offset,
    )
    game_version = reader.read_utf8("quick.game_version")
    build_offset = reader.offset
    build = reader.read_utf8("quick.build")
    _require_value(reader, build, _BUILD, field="quick.build", offset=build_offset)
    turn = reader.u32("quick.turn")
    game_mode_offset = reader.offset
    game_mode = _enum_value(
        reader,
        QuickGameMode,
        reader.u8("quick.game_mode"),
        field="quick.game_mode",
        offset=game_mode_offset,
    )
    active_civilization = reader.read_utf8("quick.active_civilization")
    difficulty = reader.read_utf8("quick.difficulty")
    starting_era = reader.read_utf8("quick.starting_era")
    current_era = reader.read_utf8("quick.current_era")
    game_speed = reader.read_utf8("quick.game_speed")
    world_size = reader.read_utf8("quick.world_size")
    map_script = reader.read_utf8("quick.map_script")

    dlc_count = _read_count(reader, "quick.enabled_dlc", minimum_item_size=24)
    enabled_dlc: list[EnabledDlc] = []
    for index in range(dlc_count):
        guid = UUID(bytes_le=reader.read_bytes(16, f"quick.enabled_dlc[{index}].guid"))
        enabled_dlc.append(
            EnabledDlc(
                guid=str(guid),
                value=reader.u32(f"quick.enabled_dlc[{index}].value"),
                name=reader.read_utf8(f"quick.enabled_dlc[{index}].name"),
            )
        )

    mod_count_offset = reader.offset
    mod_count = reader.u32("quick.enabled_mods.count")
    if mod_count != 0:
        reader.fail(
            "nonempty formal enabled-mod arrays are unsupported for build 403694",
            offset=mod_count_offset,
            field="quick.enabled_mods.count",
        )

    unknown_spans: list[UnknownHeaderSpan] = [
        _unknown_string_span(reader, "quick.bridge.unknown_string_1"),
        _unknown_string_span(reader, "quick.bridge.unknown_string_2"),
    ]
    player_color = reader.read_utf8("quick.player_color")
    unknown_spans.append(_unknown_bytes_span(reader, "quick.bridge.metadata", 41))
    unknown_spans.append(_unknown_bytes_span(reader, "quick.bridge.trailing_value", 4))

    return (
        QuickHeader(
            signature="CIV5",
            outer_version=outer_version,
            game_version=game_version,
            build=build,
            turn=turn,
            game_mode=game_mode,
            active_civilization=active_civilization,
            difficulty=difficulty,
            starting_era=starting_era,
            current_era=current_era,
            game_speed=game_speed,
            world_size=world_size,
            map_script=map_script,
            enabled_dlc=tuple(enabled_dlc),
            enabled_mods=(),
            player_color=player_color,
        ),
        tuple(unknown_spans),
    )


def _split_nickname(nickname: str) -> tuple[str | None, str | None]:
    if not nickname:
        return None, None
    display_name, separator, suffix = nickname.rpartition("@")
    if separator and len(suffix) == 17 and suffix.isascii() and suffix.isdigit():
        return display_name, suffix
    return nickname, None


def _read_slot_hints(reader: _HeaderReader) -> SlotHints:
    version_offset = reader.offset
    version = reader.u32("slot_hints.version")
    _require_value(
        reader,
        version,
        _SLOT_HINT_VERSION,
        field="slot_hints.version",
        offset=version_offset,
    )
    game_speed = reader.i32("slot_hints.game_speed")
    world_size = reader.i32("slot_hints.world_size")
    map_script = reader.read_utf8("slot_hints.map_script")
    civilization_indices = _read_i32_vector(
        reader, "slot_hints.civilization_indices", expected=_PLAYER_COUNT
    )
    nicknames = _read_string_vector(
        reader, "slot_hints.nicknames", expected=_PLAYER_COUNT
    )
    statuses = _read_slot_status_vector(reader, "slot_hints.statuses")
    claims = _read_slot_claim_vector(reader, "slot_hints.claims")
    teams = _read_i32_vector(reader, "slot_hints.teams", expected=_PLAYER_COUNT)
    handicaps = _read_i32_vector(reader, "slot_hints.handicaps", expected=_PLAYER_COUNT)
    civilization_keys = _read_string_vector(
        reader, "slot_hints.civilization_keys", expected=_PLAYER_COUNT
    )
    leader_keys = _read_string_vector(
        reader, "slot_hints.leader_keys", expected=_PLAYER_COUNT
    )

    players: list[PlayerSlot] = []
    for index in range(_PLAYER_COUNT):
        display_name, steam_id = _split_nickname(nicknames[index])
        players.append(
            PlayerSlot(
                index=index,
                civilization_index=civilization_indices[index],
                raw_nickname=nicknames[index],
                display_name=display_name,
                steam_id=steam_id,
                status=statuses[index],
                claim=claims[index],
                team=teams[index],
                handicap=handicaps[index],
                civilization_key=civilization_keys[index],
                leader_key=leader_keys[index],
            )
        )
    return SlotHints(
        version=version,
        game_speed=game_speed,
        world_size=world_size,
        map_script=map_script,
        players=tuple(players),
    )


def _read_pregame_archive(reader: _HeaderReader) -> PreGameArchive:
    field = "pregame"
    version_offset = reader.offset
    version = reader.u32(f"{field}.version")
    _require_value(
        reader,
        version,
        _PREGAME_VERSION,
        field=f"{field}.version",
        offset=version_offset,
    )
    active_player = reader.i32(f"{field}.active_player")
    admin_password = reader.read_utf8(f"{field}.admin_password")
    advanced_start_points = reader.i32(f"{field}.advanced_start_points")
    alias = reader.read_utf8(f"{field}.alias")
    art_styles = _read_i32_vector(reader, f"{field}.art_styles", expected=_PLAYER_COUNT)
    autorun = reader.read_bool(f"{field}.autorun")
    autorun_turn_delay = reader.f32(f"{field}.autorun_turn_delay")
    autorun_turn_limit = reader.i32(f"{field}.autorun_turn_limit")
    bandwidth = reader.i32(f"{field}.bandwidth")
    calendar = reader.i32(f"{field}.calendar")
    calendar_info = _read_base_info(reader, f"{field}.calendar_info")
    civilization_adjectives = _read_string_vector(
        reader, f"{field}.civilization_adjectives", expected=_PLAYER_COUNT
    )
    civilization_descriptions = _read_string_vector(
        reader, f"{field}.civilization_descriptions", expected=_PLAYER_COUNT
    )
    civilization_passwords = _read_string_vector(
        reader, f"{field}.civilization_passwords", expected=_PLAYER_COUNT
    )
    civilization_short_descriptions = _read_string_vector(
        reader,
        f"{field}.civilization_short_descriptions",
        expected=_PLAYER_COUNT,
    )
    climate = reader.i32(f"{field}.climate")
    climate_info = _read_climate_info(reader, f"{field}.climate_info")
    era = reader.i32(f"{field}.era")
    email_addresses = _read_string_vector(
        reader, f"{field}.email_addresses", expected=_PLAYER_COUNT
    )
    end_turn_timer_length = reader.f32(f"{field}.end_turn_timer_length")
    flag_decals = _read_string_vector(
        reader, f"{field}.flag_decals", expected=_PLAYER_COUNT
    )
    deprecated_force_controls = _read_bool_vector(
        reader,
        f"{field}.deprecated_force_controls",
        expected=_FORCE_CONTROL_COUNT,
    )
    game_mode_offset = reader.offset
    game_mode = _enum_value(
        reader,
        ArchiveGameMode,
        reader.i32(f"{field}.game_mode"),
        field=f"{field}.game_mode",
        offset=game_mode_offset,
    )
    game_name = reader.read_utf8(f"{field}.game_name")
    game_speed = reader.i32(f"{field}.game_speed")
    game_started = reader.read_bool(f"{field}.game_started")
    game_turn = reader.i32(f"{field}.game_turn")
    game_type = reader.i32(f"{field}.game_type")
    game_map_type_offset = reader.offset
    game_map_type = _enum_value(
        reader,
        GameMapType,
        reader.u8(f"{field}.game_map_type"),
        field=f"{field}.game_map_type",
        offset=game_map_type_offset,
    )
    game_update_time = reader.i32(f"{field}.game_update_time")
    handicaps = _read_i32_vector(reader, f"{field}.handicaps", expected=_PLAYER_COUNT)
    last_human_handicaps = _read_i32_vector(
        reader, f"{field}.last_human_handicaps", expected=_PLAYER_COUNT
    )
    is_earth_map = reader.read_bool(f"{field}.is_earth_map")
    is_internet_game = reader.read_bool(f"{field}.is_internet_game")
    leader_names = _read_string_vector(
        reader, f"{field}.leader_names", expected=_PLAYER_COUNT
    )
    load_file_name = reader.read_utf8(f"{field}.load_file_name")
    local_player_email_address = reader.read_utf8(f"{field}.local_player_email_address")
    map_has_no_players = reader.read_bool(f"{field}.map_has_no_players")
    map_random_seed = reader.u32(f"{field}.map_random_seed")
    load_world_builder_scenario = reader.read_bool(
        f"{field}.load_world_builder_scenario"
    )
    override_scenario_handicap = reader.read_bool(f"{field}.override_scenario_handicap")
    map_script_name = reader.read_utf8(f"{field}.map_script_name")
    max_city_elimination = reader.i32(f"{field}.max_city_elimination")
    max_turns = reader.i32(f"{field}.max_turns")
    num_minor_civs = reader.i32(f"{field}.num_minor_civs")
    minor_civ_types = _read_string_vector(
        reader, f"{field}.minor_civ_types", expected=_PLAYER_COUNT
    )
    minor_nation_civs = _read_bool_vector(
        reader, f"{field}.minor_nation_civs", expected=_PLAYER_COUNT
    )
    dummy_value = reader.read_bool(f"{field}.dummy_value")
    multiplayer_options = _read_bool_vector(reader, f"{field}.multiplayer_options")
    network_ids = _read_i32_vector(
        reader, f"{field}.network_ids", expected=_PLAYER_COUNT
    )
    nicknames = _read_string_vector(
        reader, f"{field}.nicknames", expected=_PLAYER_COUNT
    )
    num_victory_infos = reader.i32(f"{field}.num_victory_infos")
    pit_boss_turn_time = reader.i32(f"{field}.pit_boss_turn_time")
    playable_civs = _read_bool_vector(
        reader, f"{field}.playable_civs", expected=_PLAYER_COUNT
    )
    player_colors = _read_string_vector(
        reader, f"{field}.player_colors", expected=_PLAYER_COUNT
    )
    private_game = reader.read_bool(f"{field}.private_game")
    quick_combat = reader.read_bool(f"{field}.quick_combat")
    quick_combat_default = reader.read_bool(f"{field}.quick_combat_default")
    quick_handicap = reader.i32(f"{field}.quick_handicap")
    quickstart = reader.read_bool(f"{field}.quickstart")
    random_world_size = reader.read_bool(f"{field}.random_world_size")
    random_map_script = reader.read_bool(f"{field}.random_map_script")
    ready_players = _read_bool_vector(
        reader, f"{field}.ready_players", expected=_PLAYER_COUNT
    )
    sea_level = reader.i32(f"{field}.sea_level")
    sea_level_info = _read_sea_level_info(reader, f"{field}.sea_level_info")
    dummy_value_2 = reader.read_bool(f"{field}.dummy_value_2")
    slot_claims = _read_slot_claim_vector(reader, f"{field}.slot_claims")
    slot_statuses = _read_slot_status_vector(reader, f"{field}.slot_statuses")
    smtp_host = reader.read_utf8(f"{field}.smtp_host")
    sync_random_seed = reader.u32(f"{field}.sync_random_seed")
    target_score = reader.i32(f"{field}.target_score")
    team_types = _read_i32_vector(reader, f"{field}.team_types", expected=_PLAYER_COUNT)
    transferred_map = reader.read_bool(f"{field}.transferred_map")
    turn_timer = _read_turn_timer_info(reader, f"{field}.turn_timer")
    turn_timer_type = reader.i32(f"{field}.turn_timer_type")
    city_screen_blocked = reader.read_bool(f"{field}.city_screen_blocked")
    victories = _read_bool_vector(reader, f"{field}.victories")
    if len(victories) != num_victory_infos:
        reader.fail(
            f"count is {len(victories)}, expected num_victory_infos {num_victory_infos}",
            field=f"{field}.victories.count",
        )
    white_flags = _read_bool_vector(
        reader, f"{field}.white_flags", expected=_PLAYER_COUNT
    )
    world_info = _read_world_info(reader, f"{field}.world_info")
    world_size = reader.i32(f"{field}.world_size")
    game_options = _read_custom_options(reader, f"{field}.game_options")
    map_options = _read_custom_options(reader, f"{field}.map_options")
    version_string = reader.read_utf8(f"{field}.version_string")
    turn_notify_steam_invite = _read_bool_vector(
        reader, f"{field}.turn_notify_steam_invite", expected=_PLAYER_COUNT
    )
    turn_notify_email = _read_bool_vector(
        reader, f"{field}.turn_notify_email", expected=_PLAYER_COUNT
    )
    turn_notify_email_addresses = _read_string_vector(
        reader,
        f"{field}.turn_notify_email_addresses",
        expected=_PLAYER_COUNT,
    )

    return PreGameArchive(
        version=version,
        active_player=active_player,
        admin_password=admin_password,
        advanced_start_points=advanced_start_points,
        alias=alias,
        art_styles=art_styles,
        autorun=autorun,
        autorun_turn_delay=autorun_turn_delay,
        autorun_turn_limit=autorun_turn_limit,
        bandwidth=bandwidth,
        calendar=calendar,
        calendar_info=calendar_info,
        civilization_adjectives=civilization_adjectives,
        civilization_descriptions=civilization_descriptions,
        civilization_passwords=civilization_passwords,
        civilization_short_descriptions=civilization_short_descriptions,
        climate=climate,
        climate_info=climate_info,
        era=era,
        email_addresses=email_addresses,
        end_turn_timer_length=end_turn_timer_length,
        flag_decals=flag_decals,
        deprecated_force_controls=deprecated_force_controls,
        game_mode=game_mode,
        game_name=game_name,
        game_speed=game_speed,
        game_started=game_started,
        game_turn=game_turn,
        game_type=game_type,
        game_map_type=game_map_type,
        game_update_time=game_update_time,
        handicaps=handicaps,
        last_human_handicaps=last_human_handicaps,
        is_earth_map=is_earth_map,
        is_internet_game=is_internet_game,
        leader_names=leader_names,
        load_file_name=load_file_name,
        local_player_email_address=local_player_email_address,
        map_has_no_players=map_has_no_players,
        map_random_seed=map_random_seed,
        load_world_builder_scenario=load_world_builder_scenario,
        override_scenario_handicap=override_scenario_handicap,
        map_script_name=map_script_name,
        max_city_elimination=max_city_elimination,
        max_turns=max_turns,
        num_minor_civs=num_minor_civs,
        minor_civ_types=minor_civ_types,
        minor_nation_civs=minor_nation_civs,
        dummy_value=dummy_value,
        multiplayer_options=multiplayer_options,
        network_ids=network_ids,
        nicknames=nicknames,
        num_victory_infos=num_victory_infos,
        pit_boss_turn_time=pit_boss_turn_time,
        playable_civs=playable_civs,
        player_colors=player_colors,
        private_game=private_game,
        quick_combat=quick_combat,
        quick_combat_default=quick_combat_default,
        quick_handicap=quick_handicap,
        quickstart=quickstart,
        random_world_size=random_world_size,
        random_map_script=random_map_script,
        ready_players=ready_players,
        sea_level=sea_level,
        sea_level_info=sea_level_info,
        dummy_value_2=dummy_value_2,
        slot_claims=slot_claims,
        slot_statuses=slot_statuses,
        smtp_host=smtp_host,
        sync_random_seed=sync_random_seed,
        target_score=target_score,
        team_types=team_types,
        transferred_map=transferred_map,
        turn_timer=turn_timer,
        turn_timer_type=turn_timer_type,
        city_screen_blocked=city_screen_blocked,
        victories=victories,
        white_flags=white_flags,
        world_info=world_info,
        world_size=world_size,
        game_options=game_options,
        map_options=map_options,
        version_string=version_string,
        turn_notify_steam_invite=turn_notify_steam_invite,
        turn_notify_email=turn_notify_email,
        turn_notify_email_addresses=turn_notify_email_addresses,
    )


def _validate_zlib_header(reader: _HeaderReader, data: bytes, offset: int) -> None:
    if len(data) < 2:
        reader.fail(
            "first compressed chunk is too short for an RFC 1950 header",
            offset=offset,
            field="compressed_chunks[0].data",
        )
    cmf = data[0]
    flags = data[1]
    if (cmf & 0x0F) != 8 or (cmf >> 4) > 7 or ((cmf << 8) + flags) % 31 != 0:
        reader.fail(
            f"invalid RFC 1950 header {data[:2].hex(' ')}",
            offset=offset,
            field="compressed_chunks[0].data",
        )
    if flags & 0x20:
        reader.fail(
            "preset-dictionary zlib streams are unsupported",
            offset=offset + 1,
            field="compressed_chunks[0].data",
        )


def _read_compressed_chunks(
    reader: _HeaderReader,
) -> tuple[CompressedChunk, ...]:
    chunks: list[CompressedChunk] = []
    while reader.remaining > 0:
        index = len(chunks)
        length_offset = reader.offset
        length = reader.u32(f"compressed_chunks[{index}].length")
        if length == 0:
            reader.fail(
                "compressed chunk length is zero",
                offset=length_offset,
                field=f"compressed_chunks[{index}].length",
            )
        data_offset = reader.offset
        body = reader.read_bytes(length, f"compressed_chunks[{index}].data")
        if index == 0:
            _validate_zlib_header(reader, body, data_offset)
        chunks.append(
            CompressedChunk(
                length_offset=length_offset,
                data_offset=data_offset,
                length=length,
            )
        )
    if not chunks:
        reader.fail("the save contains no compressed chunks", field="compressed_chunks")
    return tuple(chunks)


def decode_civ5_save_header(save_bytes: bytes) -> Civ5SaveHeader:
    """Decode a supported physical ``.CIV5SAVE`` header from complete file bytes.

    The returned pregame archive can contain passwords and email addresses.
    Callers should not log the complete result without considering that data.
    The compressed payload is framed and validated but is not decompressed.
    """
    reader = _HeaderReader(save_bytes)
    quick, unknown_spans = _read_quick_header(reader)
    slot_hints = _read_slot_hints(reader)
    pregame = _read_pregame_archive(reader)
    compression_type_offset = reader.offset
    compression_type = reader.u32("compression_type")
    _require_value(
        reader,
        compression_type,
        _COMPRESSION_TYPE,
        field="compression_type",
        offset=compression_type_offset,
    )
    first_chunk_length_offset = reader.offset
    compressed_chunks = _read_compressed_chunks(reader)
    zlib_offset = compressed_chunks[0]["data_offset"]
    return Civ5SaveHeader(
        header_length=first_chunk_length_offset,
        first_chunk_length_offset=first_chunk_length_offset,
        zlib_offset=zlib_offset,
        compression_type=compression_type,
        quick=quick,
        slot_hints=slot_hints,
        pregame=pregame,
        unknown_spans=unknown_spans,
        compressed_chunks=compressed_chunks,
    )
