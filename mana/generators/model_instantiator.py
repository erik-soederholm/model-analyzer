import pprint
import sys
import meta_model as MM
from typing import TypeVar
from pathlib import Path
from mana.generators.model_reader import ModelReader
from mana.warnings_and_exceptions import *

T = TypeVar('T')

def exactly_one(my_list : list[T]) -> T:
    if len(my_list) != 1:
        raise ManaException()
    return my_list[0]
    
class ModelInstantiator(ModelReader):
    def __init__(self, jobs: dict):
        ModelReader.__init__(self, jobs)
    
    def code_name(self, name : str):
        """ pure function """
        return '_'.join(name.split())
        
    def symb_name(self, name : str):
        """ pure function """
        return self.code_name(name).lower()
    
    def type_name(self, variant, _type):
        if variant == 'type':
            return _type
        elif variant == 'union_type':
            return 'Union(' + ', '.join(_type) + ')'
        else:
            raise ManaException()
    
    def instantiate(self):
        domains = dict()
        
        self.instantiate_types()
        
        for subsystem in self.subsystems:
            domain = subsystem.name['domain_name']
            if domain not in domains:
                domains[domain] = []
            domains[domain].append(subsystem)
        
        for domain, subsystems in domains.items():
            self.instantiate_domain(domain, subsystems)
                
    def instantiate_domain(self, domain_name : str, subsystem_list : list):
        domain_attr = MM.Domain.constraint(
            {'Name' : domain_name, 
             'Alias' : domain_name})  #ToDo: fix alias to domain
        domain_i = MM.Domain.new(domain_attr)
        modeled_domain_i = MM.Modeled_Domain.new(domain_i.R4('Modeled Domain'))
        for subsystem in subsystem_list:
            self.instantiate_subsystem(subsystem, modeled_domain_i)
        
        for subsystem in subsystem_list:
            subsystem_i = self.query_subsystem(
                modeled_domain_i, subsystem.name['subsys_name'])
            for _class in subsystem.classes:
                self.instantiate_class(_class, subsystem_i, modeled_domain_i)
        
        for subsystem in subsystem_list:
            subsystem_i = self.query_subsystem(
                modeled_domain_i, subsystem.name['subsys_name'])
            for rel in subsystem.rels:
                self.instantiate_rel(rel, subsystem_i, modeled_domain_i)
                
        
    def query_subsystem(self, modeled_domain_i: MM.Modeled_Domain.constraint, subsystem_name : str) -> MM.Subsystem.constraint:
        domain_partition_i_set = MM.Domain_Partition.query(modeled_domain_i.R3())
        subsystem_attr = MM.Subsystem.constraint({
            'Name' : subsystem_name})
        for domain_partition_i in MM.Domain_Partition.query(modeled_domain_i.R3()):
            subsystem_i_set = MM.Subsystem.query(subsystem_attr & domain_partition_i.R1())
            if len(subsystem_i_set) == 1:
                return exactly_one(subsystem_i_set)
        raise ManaException()
    
    def query_class(self, modeled_domain_i: MM.Modeled_Domain.constraint, class_name : str) -> MM.Class.constraint:
        domain_name = MM.Modeled_Domain.value(modeled_domain_i, 'Name')
        class_attr = MM.Class.constraint({
            'Name' : class_name,
            'Domain' : domain_name})
        return exactly_one(MM.Class.query(class_attr))
        
    def instantiate_subsystem(self, subsystem, modeled_domain_i: MM.Modeled_Domain.constraint):
        
        min_num = min([int(''.join([ d for d in rel['rnum'] if d.isdigit()])) for rel in subsystem.rels ])        
        domain_partition_attr = MM.Domain_Partition.constraint(
            {'Number' : min_num})
        
        domain_partition_i = MM.Domain_Partition.new(domain_partition_attr & modeled_domain_i.R3())

        name = subsystem.name['subsys_name']
        alias = subsystem.name['abbr']
        subsystem_attr = MM.Subsystem.constraint(            
            {'Name' : name,
             'Alias' : name if alias is None else alias})
        subsystem_i = MM.Subsystem.new(subsystem_attr & domain_partition_i.R1())
        
    def instantiate_class(self, _class: dict, subsystem_i: MM.Subsystem.constraint, modeled_domain_i: MM.Modeled_Domain.constraint):
        
        element_attr = MM.Element.constraint({'Number' : ('C', _class['cnum'])})
        element_i = MM.Element.new(element_attr & modeled_domain_i.R15())

        subsystem_element_i = MM.Subsystem_Element.new(subsystem_i.R13() & element_i.R16('Subsystem Element'))
        
        class_attr = MM.Class.constraint(
            {'Name' : _class['name']})
        class_i = MM.Class.new(class_attr & subsystem_element_i.R14('Class'))
        for attribute in _class['attributes']:
            self.instantiate_attribute(attribute, class_i)
        
        id_data = self.id(_class)
        for _id in id_data['defined']:
            self.instantiate_id(_id, id_data['inclusion'][_id], class_i)
            
    
    def instantiate_attribute(self, attribute: dict, class_i: MM.Class.constraint):

        variant = 'type' if 'type' in attribute else 'union_type'
        type_name = self.type_name(variant, attribute[variant])
        type_attr = MM.Type.constraint({'Name' : type_name})
        type_i = exactly_one(MM.Type.query(type_attr))
        
        attribute_attr = MM.Attribute.constraint(
            {'Name' : attribute['name']})
        attribute_i = MM.Attribute.new(attribute_attr & class_i.R20() & type_i.R24())
        
        MM.Non_Derived_Attribute.new(attribute_i.R25('Non Derived Attribute'))
        
    def instantiate_id(self, _id: str, Attribute_list: list, class_i: MM.Class.constraint):
        number = {'I' : 1, 'I2' : 2, 'I3' :3}[_id]
        identifier_attr = MM.Identifier.constraint(
            {'Number' : ('I', number)})
        identifier_i = MM.Identifier.new(identifier_attr & class_i.R27())
        
        MM.Irreducible_Identifier.new(class_i.R31() & identifier_i.R30('Irreducible Identifier'))
        for attribute_name in Attribute_list:
            
            attribute_attr = MM.Attribute.constraint(
                {'Name' : attribute_name})
            attribute_i = exactly_one(MM.Attribute.query(attribute_attr & class_i.R20()))
            
            MM.Identifier_Attribute.new(identifier_i.R22() & attribute_i.R22())
        
    def instantiate_types(self):
        all_types = self.types()
        for variant, type_list in all_types.items():
            for _type in type_list:
                type_name = self.type_name(variant, _type)
                type_attr = MM.Type.constraint(
                    {'Name' : type_name})
                MM.Type.new(type_attr)

    def instantiate_rel(self, rel: dict, subsystem_i: MM.Subsystem.constraint, modeled_domain_i: MM.Modeled_Domain.constraint):
        rnum = rel['rnum']
        rnum_number = ('R', rnum[1:] if rnum[0] == 'R' else rnum[2:])
        element_attr = MM.Element.constraint({'Number' : rnum_number})
        element_i = MM.Element.new(element_attr & modeled_domain_i.R15())

        subsystem_element_i = MM.Subsystem_Element.new(subsystem_i.R13() & element_i.R16('Subsystem Element'))
        relationship_i = MM.Relationship.new(subsystem_element_i.R14('Relationship'))
        
        if rnum[0] == 'O':
            """ Ordinal Relationship """
            
            ordinal_data = self.ordinal_table[rnum]
            
            class_i = self.query_class(modeled_domain_i, ordinal_data['class'])

            number = {'I' : 1, 'I2' : 2, 'I3' :3}[ordinal_data['id']]
            identifier_attr = MM.Identifier.constraint(
                {'Number' : ('I', number)})
            
            identifier_i = exactly_one(MM.Identifier.query(identifier_attr & class_i.R27()))
            
            attribute_attr = MM.Attribute.constraint(
                {'Name' : ordinal_data['ranking_attribute']})
            attribute_i = exactly_one(MM.Attribute.query(attribute_attr & class_i.R20()))
            
            identifier_attribute_i = exactly_one(
                MM.Identifier_Attribute.query(identifier_i.R22() & attribute_i.R22()))
            
            ordinal_relationship_attr = MM.Ordinal_Relationship.constraint(
                {'Ascending perspective' : ordinal_data['ascending'],
                 'Descending perspective' : ordinal_data['descending']}
            )
            
            MM.Ordinal_Relationship.new(
                ordinal_relationship_attr & 
                relationship_i.R100('Ordinal Relationship') & 
                class_i.R104() & 
                identifier_i.R107() & 
                identifier_attribute_i.R106())
            
        elif 't_side' in rel:
            association_i = MM.Association.new(relationship_i.R100('Association'))

            binary_association_i = MM.Binary_Association.new(association_i.R119('Binary Association'))

            side_list = ['p_side', 't_side']
            create_formalizing_list = None
            
            if 'assoc_cname' in rel:
                create_formalizing_list = [False, False]
                class_i_association_class = self.query_class(modeled_domain_i, rel['assoc_cname'])
                formalizing_class_role_i = MM.Formalizing_Class_Role.new(relationship_i.R150() & class_i_association_class.R150()) 
                association_class_i = MM.Association_Class.new(class_i_association_class.R120() & association_i.R120() & formalizing_class_role_i.R151('Association Class'))
            else:
                create_formalizing_list = [True, False]
                # Check formalizing class
                if rel['rnum'] not in self.referential_table[rel['t_side']['cname']]['defined']:
                    # then t_side is the formalizing side
                    # ..reverse order on side_list to put t_side first
                    side_list.reverse()
            
            for side, create_formalizing in zip(side_list, create_formalizing_list):
                perspective = rel[side]
                class_i = self.query_class(modeled_domain_i, perspective['cname'])
                
                side_letter = {'t_side' : 'T', 'p_side' : 'P'}[side]
                perspective_attr = MM.Perspective.constraint(
                    {'Side' : side_letter,
                     'Rnum' : rnum_number,
                     'Phrase' : perspective['phrase'],
                     'Conditional' : perspective['mult'][-1] == 'c',
                     'Multiplicity' : perspective['mult'][0]})
                perspective_i = MM.Perspective.new(perspective_attr & class_i.R110())
                asymmetric_perspective_i = MM.Asymmetric_Perspective.new(perspective_i.R121('Asymmetric Perspective'))

                if side == 't_side':
                    MM.T_Perspective.new(asymmetric_perspective_i.R105('T Perspective') & binary_association_i.R124())
                else:
                    MM.P_Perspective.new(asymmetric_perspective_i.R105('P Perspective') & binary_association_i.R125())
                    
                if create_formalizing:
                    formalizing_class_role_i = MM.Formalizing_Class_Role.new(relationship_i.R150() & class_i.R150()) 
                    referring_class_i = MM.Referring_Class.new(formalizing_class_role_i.R151('Referring Class'))
                else:
                    if 'assoc_cname' in rel:
                        reference_letter = side_letter
                    else:
                        reference_letter = 'R'
                    reference_i = self.instantiate_referential_attributes(
                        modeled_domain_i, rnum, reference_letter, class_i.R155() & formalizing_class_role_i.R155(), side)
                    association_reference_i = MM.Association_Reference.new(
                        reference_i.R152('Association Reference') & perspective_i.R154())
                    if 'assoc_cname' in rel:
                        association_class_reference_i = MM.Association_Class_Reference.new(
                            association_reference_i.R176('Association Class Reference'))
                        
                        if side == 't_side':
                            MM.T_Reference.new(association_class_reference_i.R153('T Reference') & association_class_i.R158())
                        else:
                            MM.P_Reference.new(association_class_reference_i.R153('P Reference') & association_class_i.R159())
                            
                    else:
                        MM.Simple_Association_Reference.new(
                            association_reference_i.R176('Simple Association Reference') & 
                            referring_class_i.R157())
                    
        else:
            generalization_attr = MM.Generalization.constraint(
                {'Superclass' :  rel['superclass']})
            generalization_i = MM.Generalization.new(generalization_attr & relationship_i.R100('Generalization'))
            class_i_superclass = self.query_class(modeled_domain_i, rel['superclass'])

            facet_i = MM.Facet.new(class_i_superclass.R101() & generalization_i.R101())

            superclass_i = MM.Superclass.new(facet_i.R102('Superclass'))
            if len(MM.Generalization.query(generalization_i & superclass_i.R103())) != 1:
                raise ManaException() # Check R103!
            for subclass_name in rel['subclasses']:
                class_i_subclass = self.query_class(modeled_domain_i, subclass_name)
                formalizing_class_role_i = MM.Formalizing_Class_Role.new(relationship_i.R150() & class_i_subclass.R150()) 

                facet_i = MM.Facet.new(class_i_subclass.R101() & generalization_i.R101())
                subclass_i = MM.Subclass.new(facet_i.R102('Subclass') & formalizing_class_role_i.R151('Subclass'))
                
                reference_i = self.instantiate_referential_attributes(
                    modeled_domain_i, rnum, 'G', class_i_superclass.R155() & formalizing_class_role_i.R155())

                generalization_reference_i = MM.Generalization_Reference.new(
                    reference_i.R152('Generalization Reference') & superclass_i.R170() & subclass_i.R156())
            
    def instantiate_referential_attributes(self, modeled_domain_i, rnum, ref_letter : str, r155, side=None):
        reference_attr = MM.Reference.constraint({'Ref' : ref_letter})
        reference_i = MM.Reference.new(reference_attr & r155)
        
        to_class_name = MM.Reference.value(reference_i, 'To class')
        class_i_to = self.query_class(modeled_domain_i, to_class_name)
        
        from_class_name = MM.Reference.value(reference_i, 'From class')
        class_i_from = self.query_class(modeled_domain_i, from_class_name)
        
        ref_data_origin = self.referential_table[to_class_name]['inclusion'][rnum]
        if ref_data_origin['has_variants']:
            for data in ref_data_origin['variant'].values():
                if data['formalizing_class']['name'] == from_class_name:
                    if side is None or side == data['side']:
                        ref_data = data
                        break
        else:
            ref_data = ref_data_origin['data']
        
        # From class {I, I2, /R21/Attribute.Class, R23}
        # To class {I, /R21c/Identifier Attribute.Class, R23}
        
        def attribute_by_name(class_i: MM.Class.constraint, attribute_name: str) -> MM.Attribute.constraint:
            attribute_attr = MM.Attribute.constraint({'Name' : attribute_name})
            return exactly_one(MM.Attribute.query(attribute_attr & class_i.R20()))
            
        number = {'I' : 1, 'I2' : 2, 'I3' :3}[ref_data['id']]
        identifier_attr = MM.Identifier_Attribute.constraint({'Identifier' : ('I', number)})
        for to_attribute, from_attribute in ref_data['ref_map'].items():
            attribute_i_to = attribute_by_name(class_i_to, to_attribute)
            identifier_attribute_i = exactly_one(MM.Identifier_Attribute.query(identifier_attr & attribute_i_to.R22()))

            attribute_i_from = attribute_by_name(class_i_from, from_attribute)

            MM.Attribute_Reference.new(reference_i.R23() & identifier_attribute_i.R21() & attribute_i_from.R21())

        return reference_i
