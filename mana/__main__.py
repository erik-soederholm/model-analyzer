
import sys
import json
from pathlib import Path

from mana.generators.meta_model_generator import MetaModelGenerator, ManaException

def main():
    examples_path = Path(__file__).parent / "examples"
    manifest_path = examples_path / "shlaer-mellor-metamodel.json"
    with open(manifest_path) as manifest_file:
        manifest = json.load(manifest_file)
        
    job = {'subsystems': []}
    if 'subsystems' in manifest:
        for subsystem in manifest['subsystems']:
            job['subsystems'].append(examples_path / subsystem)
    mmg = MetaModelGenerator(job)
    
    
    try:
        mmg.parse()
        mmg.generate()
    except ManaException as e:
        if e.exit():
            sys.exit(e)
        else:
            raise e

if __name__ == "__main__":
    main()