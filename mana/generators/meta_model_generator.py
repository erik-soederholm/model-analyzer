import pprint
import sys
from pathlib import Path
from flatland.input.model_parser import ModelParser
from flatland.flatland_exceptions import ModelParseError
from jinja2 import Environment, FileSystemLoader

class ManaException(Exception):
    def output_str(self, input : str):
        rows = input.split('\n')
        return 'Model-Analysis: [' \
           + '\n                 '.join(rows) + ']'

class ManaParserException(ManaException):
    def __init__(self, file_path, _type, e):
        self.file_path = file_path
        self._type = _type
        self.e = e

    def __str__(self):
        text = f'Parse error in {self._type}: "{self.file_path}"\n{str(self.e)[:-1]}'
        return super().output_str(text)
    
class MetaModelGenerator:
    def __init__(self, xuml_meta_model_path: Path):
        self.xuml_meta_model_path = [('subsys', xuml_meta_model_path)]
        self.subsystems = []
        
    def parse(self): 
        for file_type, parse_file in self.xuml_meta_model_path:
            if file_type == 'subsys':
                parse_job= ModelParser(model_file_path=parse_file, debug=False)
                try:
                    self.subsystems.append(parse_job.parse())
                except ModelParseError as flatland_e:
                    sys.exit(ManaParserException(flatland_e.model_file, "class model", flatland_e.e))
            else:
                pass # Todo
        # Print parsed data to file
        with open("parse_data.txt", "w") as data_file:
            pp = pprint.PrettyPrinter(indent=2, stream=data_file)
            pp.pprint(dict(self.subsystems[0]._asdict()))
    
    def generate(self):
        
        def code_name(name : str):
            return '_'.join(name.split())
        
        def symb_name(name : str):
            return code_name(name).lower()
        
        def id (input : dict()):
            output = {'defined' : [], 'inclusion' : {'I' :[],'I2' :[],'I3' :[]}}
            if 'attributes' in input:
                defined_set = set()
                for attr in input['attributes']:
                    if 'id' in attr:
                        for id in attr['id']:
                            defined_set |= {id}
                            output['inclusion'][id].append(attr['name'])
                defined_list = list(defined_set)
                defined_list.sort()
                output['defined'] = defined_list
            if output['defined'] == []:
                output['defined'] = ['I'] # the implication of adding an 'I' without any attributes is that it will be an singleton
            return output
    
        relation_table = dict()
        class_table = dict()
        referential_table = dict()
        
        for subsys in self.subsystems:
            for rel in subsys.rels:
                if rel['rnum'] in relation_table:
                    raise ManaException() # no duplicates!
                relation_table[rel['rnum']] = rel
                
            for a_class in subsys.classes:
                if a_class['name'] in class_table:
                    raise ManaException() # no duplicates!
                a_class['cnum'] = len(class_table) + 1
                class_table[a_class['name']] = a_class
                referential_table[a_class['name']] = {'defined' : [], 'inclusion' : {}}
        
        pp = pprint.PrettyPrinter(indent=2)
        pp.pprint(class_table)
        
        ref_attr_candidate_table = dict()
        
        for rnum, rel in relation_table.items():
            def add(_class, rel, towards_class, side, phrase = None):
                if _class not in ref_attr_candidate_table:
                    ref_attr_candidate_table[_class] = set()
                entry = ref_attr_candidate_table[_class]
                entry.add((rel, towards_class, phrase, side))
                
            if 't_side' in rel:
                for side in ['p_side', 't_side']:
                    if 'assoc_cname' in rel:
                        add(rel['assoc_cname'], rnum, rel[side]['cname'], side, rel[side]['phrase'])
                    else:
                        other = {'p_side' : 't_side', 't_side' : 'p_side'}
                        add(rel[other[side]]['cname'], rnum, rel[side]['cname'], rel[side]['phrase'], side)
            elif 'superclass' in rel:
                superclass = rel['superclass']
                for subclass in rel['subclasses']:
                    add(subclass, rnum, superclass, 'superclass')
        
        
        def relation_navigation_fix(class_name, nav_data):
            selected_candidate_list = list()
            for candidate in ref_attr_candidate_table[class_name]:
                if 'rnum' in nav_data:
                    if candidate[0] != nav_data['rnum']:
                        continue
                if 'class' in nav_data:
                    if candidate[1] != nav_data['class']:
                        continue
                if 'phrase' in nav_data:
                    if candidate[2] != nav_data['phrase']:
                        continue
                selected_candidate_list.append(candidate)
            number_of_candidates = len(selected_candidate_list)
            if number_of_candidates != 1:
                if number_of_candidates == 0:
                    raise ManaException() # Bad Navigation, no valid solusion!
                else:
                    raise ManaException() # Bad Navigation, too many solusions?!?
            final_candidate = selected_candidate_list.pop()
            return_data = {'rnum': final_candidate[0], 'class': final_candidate[1], 'side' : final_candidate[3]}
            if final_candidate[2] is not None:
                return_data['phrase'] = final_candidate[2]
            if 'ref_name' in nav_data:
                return_data['attr_source'] = nav_data['ref_name']
            
            return return_data
        
        for class_name, _class in class_table.items():
            for attr in _class['attributes']:
                if 'nav_rnum' in attr:
                    attr['nav_rnum'] = [relation_navigation_fix(class_name, nav_item) 
                                        for nav_item in attr['nav_rnum']]

        def rel_other_end(rnum, my_end):
            rel = relation_table[rnum]
            table = None
            if 'assoc_cname' in rel:
                table = {rel['assoc_cname'] : 
                    {'p_side' : rel['p_side']['cname'],
                     't_side' : rel['t_side']['cname']}}
            elif 't_side' in rel:
                table = {rel['t_side']['cname'] : {'p_side' : rel['p_side']['cname']},
                         rel['p_side']['cname'] : {'t_side' : rel['t_side']['cname']}}
            elif 'superclass' in rel:
                table = dict()
                for subclass in rel['subclasses']:
                    table[subclass] = {'superclass' : rel['superclass']}
            if table is not None:
                if my_end not in table:
                    raise ManaException() # Bad data!
                return table[my_end]
            else:
                raise ManaException() # Bad data!

        def id_as_attr_ref(source_classes, ref_class, input_free_attr_refs, free_rename_attr):
            free_attr_refs = set()
            free_camal_table = dict()
            free_ref_has_id_attr = False
            for attr in input_free_attr_refs:
                if attr in free_rename_attr:
                    lower_attr = free_rename_attr[attr].lower()
                else:
                    lower_attr = attr.lower()
                free_attr_refs.add(lower_attr)
                free_camal_table[lower_attr] = attr
                # fixed named attributes
                if lower_attr == 'id':
                    free_ref_has_id_attr = True
                
            if len(input_free_attr_refs) != len(free_attr_refs):
                raise ManaException() # Bad naming
            
            
            all_attr_candidates = dict()
            side_to_class_table = dict()
            for _class, side, input_bound_attr_refs, bound_rename_attr in source_classes:
                bound_attr_refs = set()
                bound_camal_table = dict()
                bound_ref_has_id_attr = False
                for attr in input_bound_attr_refs:
                    if attr in bound_rename_attr:
                        lower_attr = bound_rename_attr[attr].lower()
                    else:
                        lower_attr = attr.lower()
                    bound_attr_refs.add(lower_attr)
                    bound_camal_table[lower_attr] = attr
                    if lower_attr == 'id':
                        bound_ref_has_id_attr = True
                        
                class_name = _class['name']
                side_to_class_table[side] = class_name
                convert_id = False
                if not free_ref_has_id_attr and not bound_ref_has_id_attr:
                    if class_name.lower() not in map((lambda d : d['name'].lower()), _class['attributes']):
                        convert_id = True
                
                id_def = id(_class)
                class_attr_candidates = dict()
                for _id in id_def['defined']:
                    attr_candidates = set()
                    unknown_attr = set()
                    unknown_table = dict()
                    trans_table = dict()
                    my_bound_attr_refs = set(bound_attr_refs)
                    for attr in id_def['inclusion'][_id]:
                        lower_attr = attr.lower()
                        
                        if convert_id and lower_attr == 'id':
                            lower_attr = class_name.lower()
                            
                        if lower_attr in my_bound_attr_refs:
                            my_bound_attr_refs.remove(lower_attr)
                            trans_table[attr] = bound_camal_table[lower_attr]
                        elif lower_attr in free_attr_refs:
                            attr_candidates.add(lower_attr)
                            trans_table[attr] = free_camal_table[lower_attr]
                        else:
                            unknown_attr.add(attr)
                        
                    rename_is_ok = True
                    if len(unknown_attr) == 1:
                        attr = unknown_attr.pop()
                        if len(my_bound_attr_refs) >= 1:
                            lower_attr = my_bound_attr_refs.pop()
                            attr_origin = bound_camal_table[lower_attr]
                            if attr_origin in bound_rename_attr:
                                # It is not okey to give an attribute with 
                                # named reference a new “random” name
                                rename_is_ok = False
                            trans_table[attr] = attr_origin
                        else:
                            lower_attr = attr.lower()
                            attr_candidates.add(lower_attr)
                            unknown_table[lower_attr] = attr
                    
                    if len(unknown_attr) == 0 and len(my_bound_attr_refs) == 0 and rename_is_ok:
                        class_attr_candidates[_id] = (attr_candidates, trans_table, unknown_table)
                if len(class_attr_candidates) == 0:
                    raise ManaException() # no solution found 
                all_attr_candidates[side] = class_attr_candidates
            
            first = True
            for key, value in all_attr_candidates.items():
                if first:
                    candidate_list = [[attr_data[0], {key : (_id, dict(attr_data[1]), attr_data[2])}] for _id, attr_data in value.items()]
                    first = False
                else:
                    candidate_list = [[prev_attr_candidates | attr_data[0], prev_data | {key : (_id, dict(attr_data[1]), attr_data[2])}] 
                                      for _id, attr_data in value.items()
                                      for prev_attr_candidates, prev_data in candidate_list]

            score_table = dict()
            
            for option in candidate_list:
                attr_sources = option[0]
                if len(attr_sources) == len(free_attr_refs):
                    remainder_set = free_attr_refs - attr_sources # If zero => all none nav ok!
                                                    # If none zero => all nav needs to be ok!
                    score = len(remainder_set)
                    if score <= 1:
                        option_is_ok = True
                        if score == 1:
                            remainder = remainder_set.pop()
                            attr_to_rename = (attr_sources - free_attr_refs).pop()
                            for _id, trans_table, unknown_table in option[1].values():
                                if len(unknown_table) == 1:
                                    
                            
                                    attr_origin = free_camal_table[remainder]
                                    if attr_origin in free_rename_attr:
                                        # It is not okey to give an attribute with 
                                        # named reference a new “random” name
                                        option_is_ok = False
                                    trans_table[unknown_table[attr_to_rename]] = attr_origin
                                elif len(unknown_table) > 1:
                                    raise ManaException() # Error
                                
                        if option_is_ok:
                            if score not in score_table:
                                score_table[score] = []
                            score_table[score].append(option[1])

            if len(score_table) > 0:
                best_score = min(score_table.keys())
                best_score_list = score_table[best_score]
                if len(best_score_list) > 1:
                    raise ManaException() # multipple attr sources
                class_data_dict = best_score_list[0]
                out = [{
                    'class_name' : side_to_class_table[side],
                    'side' : side,
                    'id' : _id,
                    'ref_source_to_attr_map' : trans_table }
                       for side, (_id, trans_table, unknown_table) in class_data_dict.items()]
            else:
                raise ManaException() # can not find attr source
            return out
          
        def referential(input : dict()):
            class_name = input['name']
            return referential_table[class_name]
        
        for class_name, _class in class_table.items():
            if 'attributes' in _class:
                defined_set = set()
                inclusion_table = dict()
                nav_table = dict()
                general_rename_table = dict()
                for attr in _class['attributes']:
                    # Add each attribute to the inclusion_table based on its relations
                    nav_rnum_set = set()
                    if 'nav_rnum' in attr:
                        nav_rnum_set = {nav_item['rnum'] for nav_item in attr['nav_rnum']}
                        if 'union_rnum' in attr:
                            # for now remove all 'union_rnum' attr
                            nav_rnum_set = all_nav_rnum_set - set(attr['union_rnum'])
                            
                    rnum_set = nav_rnum_set
                    if 'rnum' in attr:
                        rnum_set = (nav_rnum_set | set(attr['rnum']))
                        if 'union_rnum' in attr:
                            # for now remove all 'union_rnum' attr
                            rnum_set = rnum_set - set(attr['union_rnum'])
                            
                    
                    for rnum in rnum_set:
                        if rnum not in defined_set:
                            defined_set |= {rnum}
                            inclusion_table[rnum] = []
                            nav_table[rnum] = dict()
                            general_rename_table[rnum] = dict()
                        inclusion_table[rnum].append(attr['name'])
                        
                        if rnum in nav_rnum_set:
                            nav_entry = dict()
                            for nav_item in attr['nav_rnum']:
                                if nav_item['rnum'] == rnum:
                                    if nav_item['side'] in nav_entry:
                                        raise ManaException() # Error duplicate navigation!
                                    nav_entry[nav_item['side']] = nav_item
                            nav_table[rnum][attr['name']] = nav_entry
                    
                    if 'ref_name' in attr:
                        for rnum, ref_name in attr['ref_name']:
                            if rnum in general_rename_table:
                                if attr['name'] in general_rename_table[rnum]:
                                    raise ManaException() # Error redundent!
                                general_rename_table[rnum][attr['name']] = ref_name
                
                for rnum in defined_set:
                    source_table = rel_other_end(rnum, class_name)
                    bound_attr = dict()
                    bound_rename_table = dict()
                    free_attr = []
                    for side in source_table.keys():
                        bound_attr[side] = []
                        bound_rename_table[side] = dict()
                    for attr in inclusion_table[rnum]:
                        if attr in nav_table[rnum]:
                            for side, nav_data in nav_table[rnum][attr].items():
                                if side not in source_table.keys():
                                    raise ManaException() # Error!
                                if nav_data['class'] !=  source_table[side]:
                                    raise ManaException() # Error!
                                bound_attr[side].append(attr)
                                if 'attr_source' in nav_data:
                                    #attr_source_name = nav_data['attr_source'].lower()
                                    bound_rename_table[side][attr] = nav_data['attr_source']
                                    if rnum in general_rename_table:
                                        if attr in general_rename_table[rnum]:
                                            raise ManaException() # Error! duplicate!
                                else:
                                    if rnum in general_rename_table:
                                        if attr in general_rename_table[rnum]:
                                            bound_rename_table[side][attr] = general_rename_table[rnum][attr] 
                        else:
                            free_attr.append(attr)
                    
                    source_data = []
                    for side, source_class_name in source_table.items():
                        source_data.append([class_table[source_class_name], 
                                            side, bound_attr[side], 
                                            bound_rename_table[side]])
                        
                    ref_list = id_as_attr_ref(source_data, _class, free_attr, general_rename_table[rnum])
                    
                    has_variants = False
                    if ref_list[0]['side'] == 'superclass':
                        reference_type = 'superclass'
                        relationship_type = 'generalization'
                        has_variants = True
                    elif len(ref_list) == 2:
                        reference_type = 'associative'
                        if ref_list[0]['class_name'] == ref_list[1]['class_name']:
                            relationship_type = 'binary_reflexive'
                            has_variants = True
                        else:
                            relationship_type = 'binary'
                    else:
                        reference_type = 'to_one'
                        relationship_type = 'binary'
                    
                    for ref in ref_list:
                        ref_table_entry = referential_table[ref['class_name']]
                        if rnum not in ref_table_entry['defined']:
                            ref_table_entry['defined'].append(rnum)
                            ref_table_entry['defined'].sort()
                            ref_table_entry['inclusion'][rnum] = {
                                'reference_type' : reference_type,
                                'relationship_type' : relationship_type,
                                'has_variants' : has_variants}
                            if has_variants:
                                ref_table_entry['inclusion'][rnum]['variant_keys'] = []
                                ref_table_entry['inclusion'][rnum]['variant'] = dict()
                        
                        data = dict()
                        data['ref_map'] = ref['ref_source_to_attr_map']
                        data['ref_attributes'] = list(ref['ref_source_to_attr_map'].keys())
                        data['ref_attributes'].sort()
                        data['formalizing_class'] = _class
                        
                        if has_variants:
                            if relationship_type == 'generalization':
                                key = class_name
                            elif reference_type == 'associative' and relationship_type == 'binary_reflexive':
                                key = relation_table[rnum][ref['side']]['phrase']
                            ref_table_entry['inclusion'][rnum]['variant_keys'].append(key)
                            ref_table_entry['inclusion'][rnum]['variant_keys'].sort()
                            ref_table_entry['inclusion'][rnum]['variant'][key] = data
                        else:
                            ref_table_entry['inclusion'][rnum]['data'] = data
            
        
        #template_file_name = "templates/meta_model.py.jinja"
        #template_file = Path(__file__).parent.parent / template_file_name
        file_loader = FileSystemLoader( Path(__file__).parent.parent / 'templates')
        env = Environment(loader=file_loader, trim_blocks=True, lstrip_blocks= True, extensions=['jinja2.ext.do'])
        env.globals['code_name'] = code_name
        env.globals['symb_name'] = symb_name
        env.globals['id'] = id 
        env.globals['referential'] = referential

        template = env.get_template('meta_model.py.jinja')
        
        
        output = template.render({'subsystems':  self.subsystems, 
                                  'domain' : self.subsystems[0].name['domain_name']})
        with open("meta_model.py", "w") as text_file:
            text_file.write(output)
        
        #print(output)            
