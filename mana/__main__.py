
import sys
import json
from pathlib import Path
import time

from mana.generators.meta_model_generator import MetaModelGenerator
from mana.warnings_and_exceptions import ManaException


prev_time = 0.0

def start_time():
    global prev_time
    prev_time = time.time()

def print_time(message: str):
    global prev_time
    new_time = time.time()
    print(message, round(new_time - prev_time, 0), 'secs', end='\n')
    prev_time = new_time

def json_job(job_path: Path):
    with open(job_path) as job_file:
        data_in_file = json.load(job_file)
    
    path_at_file = job_path.resolve().parent
    if 'subsystems' not in data_in_file:
        raise ManaException()
    
    out = {
        'subsystems': [path_at_file / subsystem for subsystem in data_in_file['subsystems']],
        'statemodels': [path_at_file / subsystem for subsystem in data_in_file.get('statemodels', [])]}
       
    return out

def main():
    examples_path = Path(__file__).parent / "examples"
    
    meta_model_path = examples_path / "shlaer-mellor-metamodel.json"
    # my_model_path = meta_model_path
    my_model_path = examples_path / 'test-model.json'
    
    
    try:
        start_time()
        mmg = MetaModelGenerator(json_job(meta_model_path))  
        mmg.parse()
        mmg.interpret()
        mmg.generate()
        print_time('Generatening meta model')
        
        from mana.generators.model_instantiator import ModelInstantiator
        # By loading ModelInstantiator first now the latest genarated 
        # meta-model will be used 
        
        mi = ModelInstantiator(json_job(my_model_path))
        mi.parse()
        mi.interpret()
        mi.instantiate()
        print_time('Instantiate model')

    except ManaException as e:
        if e.exit():
            sys.exit(e)
        else:
            raise e

if __name__ == "__main__":
    main()