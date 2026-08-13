from pathlib import Path

from savefile_reverse_engineer import Civ5SaveDecoder, PlayerType


def main() -> None:
    path = Path(__file__).parent / "example_save_turn_75.Civ5Save"
    decoder = Civ5SaveDecoder(path)
    for p in decoder.players:
        if p.player_type is not PlayerType.PLAYER:
            continue
        print("-" * 100)
        print(p.display_name)
        for city in p.cities:
            print(city.name_key)
            for specialist in city.citizens.specialists:
                print(specialist.specialist_type, specialist.assigned_count)


if __name__ == "__main__":
    main()
