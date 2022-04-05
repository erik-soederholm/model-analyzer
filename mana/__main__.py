
import sys
import json
from pathlib import Path

from mana.generators.meta_model_generator import MetaModelGenerator
from mana.warnings_and_exceptions import ManaException

def main():
    examples_path = Path(__file__).parent / "examples"
    manifest_path = examples_path / "shlaer-mellor-metamodel.json"
    with open(manifest_path) as manifest_file:
        manifest = json.load(manifest_file)
        
    job = {'subsystems': []}
    ex = {'subsystems': []}
    if 'subsystems' in manifest:
        first = True
        for subsystem in manifest['subsystems']:
            if first:
                ex['subsystems'].append(examples_path / subsystem)
                
            job['subsystems'].append(examples_path / subsystem)
            first = False
    mmg = MetaModelGenerator(job)   
    
    
    try:
        mmg.parse()
        mmg.interpret()
        mmg.generate()
        
        from mana.generators.model_instantiator import ModelInstantiator
        mi = ModelInstantiator(job)
        mi.parse()
        mi.interpret()
        mi.instantiate()
    except ManaException as e:
        if e.exit():
            sys.exit(e)
        else:
            raise e

if __name__ == "__main__":
    main()