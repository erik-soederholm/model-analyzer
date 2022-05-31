import pprint
import sys
from pathlib import Path
from typing import Any, Iterator
from collections import namedtuple
from flatland.input.model_parser import ModelParser, Subsystem
from flatland.input.statemodel_parser import StateModelParser, StateModel 
from flatland.input.statemodel_visitor import StateBlock as FlatlandStateBlock, EventSpec as FlatlandEventSpec
from flatland.flatland_exceptions import ModelParseError
from mana.warnings_and_exceptions import *

StateBlock = namedtuple('StateBlock', 'name type activity transitions')
StateTransition = namedtuple('StateTransition', 'origin type to event')
EventSpec = namedtuple('EventSpec', 'name type signature transitions')

class ModelReader:
    def __init__(self, jobs: dict):
        self.subsystems: list[Subsystem] = []
        self.input_statemodels: list[StateModel] = []
        self.jobs = jobs

    def parse(self):
        for parse_file in self.jobs['subsystems']:
            parse_job = ModelParser(model_file_path=parse_file, debug=False)
            try:
                self.subsystems.append(parse_job.parse())
            except ModelParseError as flatland_e:
                raise ManaParserException(
                    flatland_e.model_file, "class model", flatland_e.e)
                
        for parse_file in self.jobs['statemodels']:
            parse_job = StateModelParser(model_file_path=parse_file, debug=False)
            try:
                self.input_statemodels.append(parse_job.parse())
            except ModelParseError as flatland_e:
                raise ManaParserException(
                    flatland_e.model_file, "state model", flatland_e.e)

        # Print parsed data to file
        with open("parse_data.txt", "w") as data_file:
            pp = pprint.PrettyPrinter(indent=2, stream=data_file)
            if len(self.input_statemodels) > 0:
                pp.pprint(dict(self.input_statemodels[0]._asdict()))

    def id(self, input: dict):
        """ pure function """
        output: dict[str, Any]= {'defined': [], 'inclusion': {'I': [], 'I2': [], 'I3': []}}
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
            # the implication of adding an 'I' without any attributes is that it will be an singleton
            output['defined'] = ['I']
        return output

    def referential(self, input: dict):
        """ function using self.referential_table """
        class_name = input['name']
        return self.referential_table[class_name]
    
    def types(self):
        return self.type_table

    def interpret(self):
        # init values
        self.relation_table = dict()
        self.relation_to_subsys = dict()
        self.class_table = dict()
        self.class_to_subsys = dict()
        self.referential_table = dict()
        self.ordinal_table = dict()
        self.class_attribute_table = dict()
        self.type_table = {'type' : [], 'union_type' : []}
        self.statemodels = []
        
        # run interpret functions
        self.interpret_common()
        self.interpret_relation_navigation()
        self.interpret_referential()
        self.interpret_types()
        self.interpret_statemodels()

    def interpret_common(self):
        subsystem_table = dict()

        for subsys in self.subsystems:
            subsys_name = subsys.name['subsys_name']
            subsystem_table[subsys_name] = subsys
            for a_class in subsys.classes:
                class_name = a_class['name']
                if 'import' not in a_class:
                    if class_name in self.class_to_subsys:
                        raise ManaMultipleClassDeclarationException(
                            class_name,
                            self.class_to_subsys[class_name],
                            subsys_name)  # no duplicate classes!
                    self.class_to_subsys[class_name] = subsys_name

        new_subsystems = []
        for subsys in self.subsystems:
            subsys_name = subsys.name['subsys_name']
            new_subsys_class_list = []
            for rel in subsys.rels:
                rel_name = rel['rnum']
                if rel_name in self.relation_table:
                    raise ManaException()  # no duplicates!
                self.relation_table[rel_name] = rel
                self.relation_to_subsys[rel_name] = subsys_name

            for a_class in subsys.classes:
                class_name = a_class['name']
                if 'import' in a_class:
                    import_subsys_name = a_class['import']
                    if class_name in self.class_to_subsys:
                        if import_subsys_name.lower() == (self.class_to_subsys[class_name]).lower():
                            continue  # all is ok!
                        else:
                            raise ManaClassImportedFromWrongSubsystemException(
                                class_name,
                                import_subsys_name,  # from
                                subsys_name,  # into
                                self.class_to_subsys[class_name])  # but declared in
                    else:
                        if import_subsys_name in subsystem_table:
                            raise ManaClassMissingInSubsystemException(
                                class_name, import_subsys_name)  # class is missing!
                        else:
                            print(ManaClassImportFromMissingSubsystemWarning(
                                class_name, import_subsys_name))
                if class_name in self.class_table:
                    # this could only happen if more then one
                    # ManaClassImportFromMissingSubsystemWarning is
                    # issued (this is ok!)
                    continue

                if class_name not in self.class_to_subsys:
                    # self.class_to_subsys is used for error messages...
                    self.class_to_subsys[class_name] = subsys_name

                a_class['cnum'] = len(self.class_table) + 1
                self.class_table[class_name] = a_class
                for attr in a_class['attributes']:
                    self.class_attribute_table[(
                        a_class['name'], attr['name'])] = attr
                self.referential_table[class_name] = {
                    'defined': [], 'inclusion': {}}
                new_subsys_class_list.append(a_class)

            new_subsystems.append(subsys._replace(
                classes=new_subsys_class_list))
        self.subsystems = new_subsystems
        #pp = pprint.PrettyPrinter(indent=2)
        # pp.pprint(self.class_table)

    def interpret_relation_navigation(self):
        ref_attr_candidate_table = dict()

        class_name_set = {name.lower() for name in self.class_table.keys()}
        for rnum, rel in self.relation_table.items():
            def add(_class, rel, towards_class, side, phrase=None):
                if _class not in ref_attr_candidate_table:
                    ref_attr_candidate_table[_class] = set()
                entry = ref_attr_candidate_table[_class]
                entry.add((rel, towards_class, phrase, side))
            class_name_list = []
            if 't_side' in rel:
                if 'assoc_cname' in rel:
                    class_name_list.append(rel['assoc_cname'])
                for side in ['p_side', 't_side']:
                    class_name_list.append(rel[side]['cname'])
                    if 'assoc_cname' in rel:
                        add(rel['assoc_cname'], rnum, rel[side]
                            ['cname'], side, rel[side]['phrase'])
                    else:
                        other = {'p_side': 't_side', 't_side': 'p_side'}
                        add(rel[other[side]]['cname'], rnum, rel[side]
                            ['cname'], rel[side]['phrase'], side)
            elif 'superclass' in rel:
                superclass = rel['superclass']
                class_name_list.append(rel['superclass'])
                for subclass in rel['subclasses']:
                    class_name_list.append(subclass)
                    add(subclass, rnum, superclass, 'superclass')
            for class_name in class_name_list:
                if class_name.lower() not in class_name_set:
                    raise ManaUnknownClassInRelationshipException(
                        rnum, class_name, self.relation_to_subsys[rnum])

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
                    raise ManaException()  # Bad Navigation, no valid solusion!
                else:
                    raise ManaException()  # Bad Navigation, too many solusions?!?
            final_candidate = selected_candidate_list.pop()
            return_data = {
                'rnum': final_candidate[0], 'class': final_candidate[1], 'side': final_candidate[3]}
            if final_candidate[2] is not None:
                return_data['phrase'] = final_candidate[2]
            if 'ref_name' in nav_data:
                return_data['attr_source'] = nav_data['ref_name']

            return return_data

        for class_name, _class in self.class_table.items():
            for attr in _class['attributes']:
                if 'nav_rnum' in attr:
                    attr['nav_rnum'] = [relation_navigation_fix(class_name, nav_item)
                                        for nav_item in attr['nav_rnum']]

    def interpret_referential(self):

        for class_name, _class in self.class_table.items():
            if 'attributes' in _class:
                ordinal_rnum_set = set()
                defined_set = set()
                inclusion_table = dict()
                nav_table = dict()
                general_rename_table = dict()
                all_attributes = []
                for attribute_type in ['attributes', 'ignore attributes']:
                    if attribute_type in _class:
                        all_attributes += _class[attribute_type]

                for attr in all_attributes:
                    # Add each attribute to the inclusion_table based on its relations
                    nav_rnum_set = set()
                    if 'nav_rnum' in attr:
                        nav_rnum_set = {nav_item['rnum'] for nav_item in attr['nav_rnum']}
                        if 'union_rnum' in attr:
                            # for now remove all 'union_rnum' attr
                            nav_rnum_set = nav_rnum_set - set(attr['union_rnum'])

                    rnum_set = set(nav_rnum_set)
                    if 'rnum' in attr:
                        for rnum in attr['rnum']:
                            # for now remove all 'ORxxx'
                            if rnum[0] != 'O':
                                rnum_set.add(rnum)
                            else:
                                ordinal_rnum_set.add(rnum)
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
                                        raise ManaException()  # Error duplicate navigation!
                                    nav_entry[nav_item['side']] = nav_item
                            nav_table[rnum][attr['name']] = nav_entry

                    if 'ref_name' in attr:
                        for rnum, ref_name in attr['ref_name']:
                            if rnum in general_rename_table:
                                if attr['name'] in general_rename_table[rnum]:
                                    raise ManaException()  # Error redundent!
                                general_rename_table[rnum][attr['name']] = ref_name
                for rnum in ordinal_rnum_set:
                    self.interpret_ordinal_relationship(rnum, _class)
                
                for rnum in defined_set:
                    self.interpret_referential_attributes(rnum, _class, inclusion_table, nav_table, general_rename_table)

    def interpret_ordinal_relationship(self, rnum: str, _class: dict):
        ''' Check Ordinal Relationship '''
        class_name = _class['name']
        
        rel = self.relation_table[rnum]
        if class_name != rel['p_side']['cname'] or class_name != rel['t_side']['cname']:
            raise ManaException()
        attribute_list = [attr for attr in _class['attributes'] if rnum in attr.get('rnum', {})]
        id_info = self.id(_class)
        ordinal_id = ''
        for id_key in id_info['defined']:
            if set(id_info['inclusion'][id_key]) == {attr['name'] for attr in attribute_list}:
                if ordinal_id == '':
                    ordinal_id = id_key
                else:
                    raise ManaException()
        if ordinal_id == '':
            raise ManaException()
                
        ranking_attr = ''                    
        for attr in attribute_list:
            if rnum in attr.get('ranking_rnum', {}):
                if ranking_attr == '':
                    ranking_attr = attr['name']
                else:
                    raise ManaException()
        if ranking_attr == '':
            raise ManaException()
        
        self.ordinal_table[rnum] = {
            'class' : class_name, 
            'id' : ordinal_id, 
            'ranking_attribute' : ranking_attr,
            'ascending' : rel['t_side']['phrase'],
            'descending' : rel['p_side']['phrase']}

    def interpret_referential_attributes(self, rnum: str, _class: dict, inclusion_table: dict, nav_table: dict, general_rename_table: dict):                           
        
        def rel_other_end(rnum, my_end):
            if rnum not in self.relation_table:
                raise ManaUnknownReferentialAttributeException(
                    rnum, my_end, self.class_to_subsys[my_end])
            rel = self.relation_table[rnum]
            table = None
            if 'assoc_cname' in rel:
                table = {rel['assoc_cname']:
                         {'p_side': rel['p_side']['cname'],
                          't_side': rel['t_side']['cname']}}
            elif 't_side' in rel:
                table = {rel['t_side']['cname']: {'p_side': rel['p_side']['cname']},
                         rel['p_side']['cname']: {'t_side': rel['t_side']['cname']}}
            elif 'superclass' in rel:
                table = dict()
                for subclass in rel['subclasses']:
                    table[subclass] = {'superclass': rel['superclass']}
            if table is not None:
                if my_end not in table:
                    raise ManaInvalidReferentialAttributeException(
                        rnum, my_end, self.class_to_subsys[my_end])
                return table[my_end]
            else:
                raise ManaException()  # Bad data!

        def remove_ignored_attributes(attr_map: dict, _class):
            remove_list = []
            if 'ignore attributes' in _class:
                ignore_set = {attr['name']
                              for attr in _class['ignore attributes']}
                for source, ref in attr_map.items():
                    if ref in ignore_set:
                        remove_list.append(source)
            if len(remove_list) == 0:
                return attr_map
            else:
                out = dict(attr_map)
                for key in remove_list:
                    del out[key]
                return out
                
        def id_as_attr_ref(source_classes, ref_class, input_free_attr_refs, free_rename_attr, rnum):
            def ref_attributes():
                out = []
                for attr in ref_class['attributes']:
                    if 'rnum' in attr:
                        if rnum in attr['rnum']:
                            out.append(attr['name'])
                return out
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
                raise ManaException()  # Bad naming

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
                    if class_name.lower() not in map((lambda d: d['name'].lower()), _class['attributes']):
                        convert_id = True

                id_def = self.id(_class)
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
                        class_attr_candidates[_id] = (
                            attr_candidates, trans_table, unknown_table)
                if len(class_attr_candidates) == 0:
                    raise ManaRefAttrNotFoundException(
                        rnum, ref_class['name'], self.class_to_subsys[ref_class['name']], ref_attributes())  # no solution found
                all_attr_candidates[side] = class_attr_candidates

            first = True
            for key, value in all_attr_candidates.items():
                if first:
                    candidate_list = [[attr_data[0], {key: (
                        _id, dict(attr_data[1]), attr_data[2])}] for _id, attr_data in value.items()]
                    first = False
                else:
                    candidate_list = [[prev_attr_candidates | attr_data[0], prev_data | {key: (_id, dict(attr_data[1]), attr_data[2])}]
                                      for _id, attr_data in value.items()
                                      for prev_attr_candidates, prev_data in candidate_list]

            score_table = dict()

            for option in candidate_list:
                attr_sources = option[0]
                if len(attr_sources) == len(free_attr_refs):
                    remainder_set = free_attr_refs - attr_sources  # If zero => all none nav ok!
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
                                    raise ManaException()  # Error

                        if option_is_ok:
                            if score not in score_table:
                                score_table[score] = []
                            score_table[score].append(option[1])

            if len(score_table) > 0:
                best_score = min(score_table.keys())
                best_score_list = score_table[best_score]
                if len(best_score_list) > 1:
                    raise ManaRefAttrNotFoundException(
                        rnum, ref_class['name'], self.class_to_subsys[ref_class['name']], ref_attributes())  # multipple attr sources
                class_data_dict = best_score_list[0]
                out = [{
                    'class_name': side_to_class_table[side],
                    'side': side,
                    'id': _id,
                    'ref_source_to_attr_map': remove_ignored_attributes(trans_table, ref_class)}
                    for side, (_id, trans_table, unknown_table) in class_data_dict.items()]
            else:
                raise ManaRefAttrNotFoundException(
                    rnum, ref_class['name'], self.class_to_subsys[ref_class['name']], ref_attributes())  # can not find attr source
            return out

        ''' Check none Ordinal Relationship formelized by referential attributes'''    
        class_name = _class['name']
        
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
                        raise ManaException()  # Error!
                    if nav_data['class'] != source_table[side]:
                        raise ManaException()  # Error!
                    bound_attr[side].append(attr)
                    if 'attr_source' in nav_data:
                        #attr_source_name = nav_data['attr_source'].lower()
                        bound_rename_table[side][attr] = nav_data['attr_source']
                        if rnum in general_rename_table:
                            if attr in general_rename_table[rnum]:
                                raise ManaException()  # Error! duplicate!
                    else:
                        if rnum in general_rename_table:
                            if attr in general_rename_table[rnum]:
                                bound_rename_table[side][attr] = general_rename_table[rnum][attr]
            else:
                free_attr.append(attr)

        source_data = []
        for side, source_class_name in source_table.items():
            source_data.append([self.class_table[source_class_name],
                                side, bound_attr[side],
                                bound_rename_table[side]])

        ref_list = id_as_attr_ref(
            source_data, _class, free_attr, general_rename_table[rnum], rnum)

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
            ref_table_entry = self.referential_table[ref['class_name']]
            if rnum not in ref_table_entry['defined']:
                ref_table_entry['defined'].append(rnum)
                ref_table_entry['defined'].sort()
                ref_table_entry['inclusion'][rnum] = {
                    'reference_type': reference_type,
                    'relationship_type': relationship_type,
                    'has_variants': has_variants}
                if has_variants:
                    ref_table_entry['inclusion'][rnum]['variant_keys'] = []
                    ref_table_entry['inclusion'][rnum]['variant'] = dict()

            data = dict()
            data['ref_map'] = ref['ref_source_to_attr_map']
            data['ref_attributes'] = list(
                ref['ref_source_to_attr_map'].keys())
            data['ref_attributes'].sort()
            data['id'] = ref['id']
            data['side'] = ref['side']
            data['formalizing_class'] = _class

            if has_variants:
                if relationship_type == 'generalization':
                    key = class_name
                elif reference_type == 'associative' and relationship_type == 'binary_reflexive':
                    key = self.relation_table[rnum][ref['side']]['phrase']
                ref_table_entry['inclusion'][rnum]['variant_keys'].append(key)
                ref_table_entry['inclusion'][rnum]['variant_keys'].sort()
                ref_table_entry['inclusion'][rnum]['variant'][key] = data
            else:
                ref_table_entry['inclusion'][rnum]['data'] = data

    def interpret_types(self):

        def reference_data(input):
            return input['variant'].values() if input['has_variants'] else [input['data']]

        # craate attribute reference table

        union_table = dict()
        attribute_reference_table = dict()
        for class_attribute in self.class_attribute_table.keys():
            attribute_reference_table[class_attribute] = {class_attribute}

        for referring_class, ref_class_data in self.referential_table.items():
            for rnum, ref_rel_data in ref_class_data['inclusion'].items():
                for ref_data in reference_data(ref_rel_data):
                    formalizing_class = ref_data['formalizing_class']['name']
                    for referring_attr, formalizing_attr in ref_data['ref_map'].items():
                        referring_node = (referring_class, referring_attr)
                        formalizing_node = (
                            formalizing_class, formalizing_attr)
                        if rnum in self.class_attribute_table[referring_node].get('union_rnum', []):
                            union_table.setdefault(referring_node, dict()).setdefault(
                                rnum, set()).add(formalizing_node)
                        else:
                            node_set_1 = attribute_reference_table[referring_node]
                            node_set_2 = attribute_reference_table[formalizing_node]
                            small_set, big_set = sorted(
                                [node_set_1, node_set_2], key=len)
                            for node in small_set:
                                big_set.add(node)
                                attribute_reference_table[node] = big_set


        type_index_table = dict()
        index_node_table = dict()

        # Introducing an index used for each set of attributes sharing the
        # same type based on logic given by referential attribute dependencies.
        i = 0
        for class_attribute in self.class_attribute_table.keys():
            if class_attribute not in type_index_table:
                type_index = i
                i += 1
                index_node_table[type_index] = attribute_reference_table[class_attribute]
                for node in attribute_reference_table[class_attribute]:
                    type_index_table[node] = type_index

        # Introducing union_task_table as a refined version of union_table 
        # where the class, attribute tuple pair is replaced by the new index. 
        # This enables a fast lookup for determent if a index has an union 
        # type definition.
        union_task_table = dict()
        for union_type, rnum_type_part in union_table.items():
            task_list = union_task_table.setdefault(type_index_table[union_type], [])
            for rnum, type_part_list in rnum_type_part.items():
                task_list.append(type_part_list)

        # Walking through all attributes in an indexes and determent if 
        # there is an explicit type declaration.
        named_type_table = dict()
        for type_index, node_set in index_node_table.items():
            for node_at_index in node_set:
                new_type = self.class_attribute_table[node_at_index].get('type')
                if new_type is not None:
                    if new_type != named_type_table.setdefault(type_index, new_type):
                        raise ManaException()  # error multiple unequal type definitions  == BAD!
        
        # The type_at_index function is retrieving the type for an index. 
        # It will return the full expanded union type definition. 
        # Thus if an index both an union type definition and an explicit 
        # named type declaration only the union type definition is provided.
        cached_type_table = dict()
        def type_at_index(index) -> set:
            type_called = set()
            
            # Help function to the type_at_index function.
            def derive_inner_types(index: int) -> Iterator[set]:
                return_type = cached_type_table.get(index, set())
                if return_type:
                    yield return_type  # No need to run this again if there is a value
                elif index in type_called:
                    yield set()  # type loop, the original call will or will not get a valid value
                else:
                    if index in union_task_table:
                        type_called.add(index) # Add guard
                        for variant in union_task_table[index]:
                            return_type = set()
                            for part in variant:
                                for part_variant in derive_inner_types(type_index_table[part]):
                                    # Note that in the type_at_index function these part_variants 
                                    # is error handled if they are not equal. The thought is that 
                                    # if this recursive lookup is stopped by the type_called guard 
                                    # there is a chance that the result is still okay at the 
                                    # type_at_index function level. But it is likely that the guard 
                                    # might cause missing information further down in the call depth. 
                                    # Hence, a union is used as an alternative in the 
                                    # derive_inner_types helper function.
                                    return_type |= part_variant
                            yield return_type
                        type_called.remove(index) # Remove guard
                    elif index in named_type_table:
                        yield {named_type_table[index]}

            return_type: set = set()
            for type_variant in derive_inner_types(index):
                if not return_type:
                    return_type = type_variant
                elif type_variant != return_type:
                    raise ManaException()  # error multiple unequal type definitions  == BAD!
                else:
                    return_type = type_variant
                
            if not return_type:
                e_data = [(c, a, self.class_to_subsys[c]) for c, a in index_node_table[index]]
                raise ManaTypeNotDefiedException(e_data)
            
            cached_type_table[index] = return_type
            return return_type
        # Checking if there is an explicit named type declaration on the union type
        named_union_table = dict()
        for named_union in set(union_task_table.keys()) & set(named_type_table.keys()):
            key = frozenset(type_at_index(named_union))
            if key in named_union_table:
                # Multiple named unions with the same signature. This is probably not 
                # an real error but somthing needs to change if this corner case is real
                raise ManaException()
            named_union_table[key] = named_type_table[named_union]

        # Save the result
        unique_type = set()
        def add_type(_type, attribute_key, node_set):
            type_list = list(_type)
            result = type_list[0] if len(_type) == 1 else sorted(type_list)
            for node in node_set:
                self.class_attribute_table[node][attribute_key] = result
            if _type not in unique_type:
                unique_type.add(_type)
                self.type_table[attribute_key].append(result)
        
        for type_index, node_set in index_node_table.items():
            type_set = frozenset(type_at_index(type_index))
            if len(type_set) == 0:
                raise ManaException() 
            if len(type_set) > 1:
                add_type(type_set, 'union_type', node_set)
                if type_set in named_union_table:
                    add_type(frozenset({named_union_table[type_set]}), 'type', node_set)
            else:
                add_type(type_set, 'type', node_set)

                
                    
    def interpret_statemodels(self):
        self.statemodels = [self.interpret_statemodel(input_statemodel) for input_statemodel in self.input_statemodels]
                
                
    def interpret_statemodel(self, input : StateModel) -> StateModel:
        states=self.interpret_state(input.states, input.events.values())

        return StateModel(
            domain=input.domain, 
            lifecycle=input.lifecycle, 
            assigner=input.assigner,
            events=self.interpret_events(input.events.values(), states),
            states=states,
            metadata=input.metadata)
        
    def interpret_events(self, input: list[FlatlandEventSpec], states: list[StateBlock] ) -> list[EventSpec]:
        event2transitions: dict[str,list[StateTransition]] = dict()
        
        for s in states:
            for t in s.transitions:
                event2transitions.setdefault(t.event, []).append(t)
                
        return [EventSpec(name=ei.name, 
                          type=ei.type, 
                          signature=ei.signature, 
                          transitions=event2transitions[ei.name]
                          ) for ei in input]
        
    def interpret_state(self, input: list[FlatlandStateBlock], events: list[FlatlandEventSpec]) -> list[StateBlock]:
        initial_transitions = []
        output = []
        for input_stat_block in input:
            next_type = input_stat_block.type
            if next_type in ['creation']:
                next_type = 'normal'
                initial_transitions.append([input_stat_block.creation_event, input_stat_block.name])
                
            output.append(StateBlock(
                name=input_stat_block.name,
                type=next_type,
                activity=input_stat_block.activity,
                transitions=self.interpret_transitions(input_stat_block.name, input_stat_block.transitions, events)))
        if initial_transitions:
            ips_name = '#¥$@ Initial Pseudo State @$¥#'
            output.insert(0, StateBlock(
                name=ips_name, # using special characters to be unique
                type='creation',
                activity=None,
                transitions=self.interpret_transitions(ips_name, initial_transitions, events)))
            
        return output
    
    def interpret_transitions(self, origin: str, transitions: list, all_events: list[FlatlandEventSpec]) -> list[StateTransition]:
        output = []
        all_event_set = {e.name for e in all_events}
        explicit_event_set = set()
        for transition in transitions:
            event = transition[0]
            if len(transition) == 1:
                output.append(StateTransition(event=event, origin=origin, to=None, type="ignore"))
            else:
                output.append(StateTransition(event=event, origin=origin, to=transition[1], type="transition"))
            explicit_event_set.add(event)
            
        if explicit_event_set - all_event_set:
            raise ManaException() # Error, event not known!
        
        for illegal_event in all_event_set - explicit_event_set:
            output.append(StateTransition(event=illegal_event, origin=origin, to=None, type="canthappen"))
            
        return output



        
        