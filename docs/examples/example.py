from itertools import islice
from pathlib import Path

from savefile_reverse_engineer import Civ5SaveDecoder


def main() -> None:
    path = Path(__file__).parent / "example_save.Civ5Save"
    decoder = Civ5SaveDecoder(path)
    for p in islice(decoder.iter_players(), 3):
        print("-" * 100)
        print(p.display_name)
        for c in p.cities:
            print(c.yield_vectors.yield_rate_modifier)


if __name__ == "__main__":
    main()
