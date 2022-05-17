import pprint
import sys
from pathlib import Path
from mana.generators.model_reader import ModelReader 
from jinja2 import Environment, FileSystemLoader
    
class MetaModelGenerator(ModelReader):
    def __init__(self, jobs: dict):
        ModelReader.__init__(self, jobs)
    
    def code_name(self, name : str):
        """ pure function """
        return '_'.join(name.split())
        
    def symb_name(self, name : str):
        """ pure function """
        return self.code_name(name).lower()
        
    def generate(self):
        
        #template_file_name = "templates/meta_model.py.jinja"
        #template_file = Path(__file__).parent.parent / template_file_name
        file_loader = FileSystemLoader( Path(__file__).parent.parent / 'templates')
        env = Environment(loader=file_loader, trim_blocks=True, lstrip_blocks= True, extensions=['jinja2.ext.do'])
        env.globals['code_name'] = lambda name : self.code_name(name)
        env.globals['symb_name'] = lambda name : self.symb_name(name)
        env.globals['id'] = lambda _class : self.id(_class)
        env.globals['referential'] = lambda _class : self.referential(_class)

        template = env.get_template('meta_model.py.jinja')
        
        
        output = template.render({'subsystems':  self.subsystems, 
                                  'domain' : self.subsystems[0].name['domain_name']})
        with open("meta_model.py", "w") as text_file:
            text_file.write(output)
        