
import sys
from pathlib import Path

from mana.generators.meta_model_generator import MetaModelGenerator


def main():

    test_model = Path(__file__).parent / "examples/road_subsystem_class_model.xmm"
    mmg = MetaModelGenerator(test_model)
    mmg.parse()
    mmg.generate()

if __name__ == "__main__":
    main()