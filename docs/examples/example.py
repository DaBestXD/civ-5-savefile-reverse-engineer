from pathlib import Path

from savefile_reverse_engineer import Civ5SaveDecoder, PlayerType


def main() -> None:
    path = Path(__file__).parent / "example_save.Civ5Save"
    decoder = Civ5SaveDecoder(path)
    for p in decoder.iter_players():
        if p.player_type is PlayerType.PLAYER:
            print(p.display_name)
            for c in p.cities:
                print(c.name_key)


if __name__ == "__main__":
    main()
