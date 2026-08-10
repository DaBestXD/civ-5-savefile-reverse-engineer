from pathlib import Path

from savefile_reverse_engineer import Civ5SaveDecoder


def main() -> None:
    path = Path(__file__).parent / "example_save.Civ5Save"
    decoder = Civ5SaveDecoder(path)
    for c in decoder.iter_cities():
        if decoder.get_owner_display_name(c) == "PostiveMentalAttitude":
            print("-" * 100)
            print(c.name_key)
            print("-" * 100)
            if c.current_production:
                print(c.current_production.item_type)
            # for b in c.buildings:
            #     print(b)


if __name__ == "__main__":
    main()
