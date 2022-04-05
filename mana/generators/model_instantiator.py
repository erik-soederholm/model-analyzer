import pprint
import sys
import meta_model as MM
from pathlib import Path
from mana.generators.model_reader import ModelReader
from mana.warnings_and_exceptions import *
    
def exactly_one(my_list : list):
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
        return code_name(name).lower()
    
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
        r4 = MM.Domain.R4(domain_i, 'Modeled Domain')
        modeled_domain_i = MM.Modeled_Domain.new(r4)
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
                
        r = 0
        
    def query_subsystem(self, modeled_domain_i, subsystem_name : str):
        r1 = MM.Modeled_Domain.R1(modeled_domain_i)
        subsystem_attr = MM.Subsystem.constraint({
            'Name' : subsystem_name})
        return exactly_one(MM.Subsystem.query(subsystem_attr & r1))
    
    def query_class(self, modeled_domain_i, class_name : str):
        domain_name = MM.Modeled_Domain.value(modeled_domain_i, 'Name')
        class_attr = MM.Class.constraint({
            'Name' : class_name,
            'Domain' : domain_name})
        return exactly_one(MM.Class.query(class_attr))
        
    def instantiate_subsystem(self, subsystem, modeled_domain_i):
        r1 = MM.Modeled_Domain.R1(modeled_domain_i)
        name = subsystem.name['subsys_name']
        alias = subsystem.name['abbr']
        subsystem_attr = MM.Subsystem.constraint(            
            {'Name' : name,
             'Alias' : name if alias is None else alias})
        subsystem_i = MM.Subsystem.new(subsystem_attr & r1)
        r3 = MM.Subsystem.R3(subsystem_i)
        # ToDo: add real values for 'Floor', 'Ceiling'    
        subsystem_numbering_range_attr = MM.Subsystem_Numbering_Range.constraint(            
            {'Floor' : 0,
             'Ceiling' : 100})
        subsystem_numbering_range_i = MM.Subsystem_Numbering_Range.new(
            subsystem_numbering_range_attr & r3)
        
    def instantiate_class(self, _class, subsystem_i, modeled_domain_i):
        r15 = MM.Modeled_Domain.R15(modeled_domain_i)
        element_attr = MM.Element.constraint({'Number' : ('C', _class['cnum'])})
        element_i = MM.Element.new(element_attr & r15)
        r16 = MM.Element.R16(element_i, 'Subsystem Element')
        r13 = MM.Subsystem.R13(subsystem_i)
        subsystem_element_i = MM.Subsystem_Element.new(r13 & r16)
        r14 = MM.Subsystem_Element.R14(subsystem_element_i, 'Class')
        class_attr = MM.Class.constraint(
            {'Name' : _class['name']})
        class_i = MM.Class.new(class_attr & r14)
        for attribute in _class['attributes']:
            self.instantiate_attribute(attribute, class_i)
        
        id_data = self.id(_class)
        for _id in id_data['defined']:
            self.instantiate_id(_id, id_data['inclusion'][_id], _class, class_i)
            
    
    def instantiate_attribute(self, attribute, class_i):
        r20 = MM.Class.R20(class_i)
        attribute_name = attribute['name']

        attribute_attr = MM.Attribute.constraint(
            {'Name' : attribute_name})

        variant = 'type' if 'type' in attribute else 'union_type'
        type_name = self.type_name(variant, attribute[variant])
        type_attr = MM.Type.constraint({'Name' : type_name})
        type_i = exactly_one(MM.Type.query(type_attr))
        r24 = MM.Type.R24(type_i)
        attribute_i = MM.Attribute.new(attribute_attr & r20 & r24)
        r25 = MM.Attribute.R25(attribute_i, 'Non Derived Attribute')
        MM.Non_Derived_Attribute.new(r25)
        
    def instantiate_id(self, _id, Attribute_list, _class, class_i):
        number = {'I' : 1, 'I2' : 2, 'I3' :3}[_id]
        identifier_attr = MM.Identifier.constraint(
            {'Number' : ('I', number)})
        r27 = MM.Class.R27(class_i)
        r31 = MM.Class.R31(class_i)
        r20 = MM.Class.R20(class_i)
        identifier_i = MM.Identifier.new(identifier_attr & r27)
        r30 = MM.Identifier.R30(identifier_i, 'Irreducible Identifier')
        r22_identifier = MM.Identifier.R22(identifier_i)
        MM.Irreducible_Identifier.new(r31 & r30)
        for attribute_name in Attribute_list:
            attribute_attr = MM.Attribute.constraint(
                {'Name' : attribute_name})
            attribute_i = exactly_one(MM.Attribute.query(attribute_attr & r20))
            r22_attribute = MM.Attribute.R22(attribute_i)
            MM.Identifier_Attribute.new(r22_identifier & r22_attribute)
        f = 0
        
    def instantiate_types(self):
        all_types = self.types()
        for variant, type_list in all_types.items():
            for _type in type_list:
                type_name = self.type_name(variant, _type)
                type_attr = MM.Type.constraint(
                    {'Name' : type_name})
                MM.Type.new(type_attr)

    def instantiate_rel(self, rel, subsystem_i, modeled_domain_i):
        r15 = MM.Modeled_Domain.R15(modeled_domain_i)
        rnum = rel['rnum']
        rnum_number = ('R', rnum[1:] if rnum[0] == 'R' else rnum[2:])
        element_attr = MM.Element.constraint({'Number' : rnum_number})
        element_i = MM.Element.new(element_attr & r15)
        r16 = MM.Element.R16(element_i, 'Subsystem Element')
        r13 = MM.Subsystem.R13(subsystem_i)
        subsystem_element_i = MM.Subsystem_Element.new(r13 & r16)
        r14 = MM.Subsystem_Element.R14(subsystem_element_i, 'Relationship')
        relationship_i = MM.Relationship.new(r14)
        r150_relationship = MM.Relationship.R150(relationship_i)
        
        if rnum[0] == 'O':
            """ Ordinal Relationship """
            raise ManaException() # ToDo 
        elif 't_side' in rel:
            r100 = MM.Relationship.R100(relationship_i, 'Association')
            association_i = MM.Association.new(r100)

            r119 = MM.Association.R119(association_i, 'Binary Association')
            binary_association_i = MM.Binary_Association.new(r119)
            r124 = MM.Binary_Association.R124(binary_association_i)
            r125 = MM.Binary_Association.R125(binary_association_i)
            r12_ = {'t_side' : r124, 'p_side' : r125}
            
            r155_formalizing_class_role = None
            r157 = None
            r15_ = None
            
            
            side_list = ['p_side', 't_side']
            create_formalizing_list = None
            
            if 'assoc_cname' in rel:
                create_formalizing_list = [False, False]
                class_i_association_class = self.query_class(modeled_domain_i, rel['assoc_cname'])
                r120_class = MM.Class.R120(class_i_association_class)
                r150_class = MM.Class.R150(class_i_association_class)
                formalizing_class_role_i = MM.Formalizing_Class_Role.new(r150_relationship & r150_class) 
                r151 = MM.Formalizing_Class_Role.R151(formalizing_class_role_i, 'Association Class')
                r155_formalizing_class_role = MM.Formalizing_Class_Role.R155(formalizing_class_role_i)
                
                r120_association = MM.Association.R120(association_i)
                association_class_i = MM.Association_Class.new(r120_class & r120_association & r151)
                r158 = MM.Association_Class.R158(association_class_i)
                r159 = MM.Association_Class.R159(association_class_i)
                r15_ = {'t_side' : r158, 'p_side' : r159}
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
                r110 = MM.Class.R110(class_i)
                side_letter = {'t_side' : 'T', 'p_side' : 'P'}[side]
                perspective_attr = MM.Perspective.constraint(
                    {'Side' : side_letter,
                     'Rnum' : rnum_number,
                     'Phrase' : perspective['phrase'],
                     'Conditional' : perspective['mult'][-1] == 'c',
                     'Multiplicity' : perspective['mult'][0]})
                perspective_i = MM.Perspective.new(perspective_attr & r110)
                r121 = MM.Perspective.R121(perspective_i, 'Asymmetric Perspective')
                asymmetric_perspective_i = MM.Asymmetric_Perspective.new(r121)
                r105 = MM.Asymmetric_Perspective.R105(
                    asymmetric_perspective_i, 
                    side_letter + ' Perspective')
                {'t_side' : MM.T_Perspective, 'p_side' : MM.P_Perspective}[side].new(r105 & r12_[side])
                if create_formalizing:
                    r150_class = MM.Class.R150(class_i)
                    formalizing_class_role_i = MM.Formalizing_Class_Role.new(r150_relationship & r150_class) 
                    r151 = MM.Formalizing_Class_Role.R151(formalizing_class_role_i, 'Referring Class')
                    r155_formalizing_class_role = MM.Formalizing_Class_Role.R155(formalizing_class_role_i)
                    referring_class_i = MM.Referring_Class.new(r151)
                    r157 = MM.Referring_Class.R157(referring_class_i)
                else:
                    if 'assoc_cname' in rel:
                        reference_letter = side_letter
                    else:
                        reference_letter = 'R'
                    r155_class = MM.Class.R155(class_i)
                    r154 = MM.Perspective.R154(perspective_i)
                    reference_i = self.instantiate_referential_attributes(modeled_domain_i, rnum, reference_letter, r155_class & r155_formalizing_class_role, side)
                    r152 = MM.Reference.R152(reference_i, 'Association Reference')
                    association_reference_i = MM.Association_Reference.new(r152 & r154)
                    if 'assoc_cname' in rel:
                        r176 = MM.Association_Reference.R176(association_reference_i, 'Association Class Reference')
                        association_class_reference_i = MM.Association_Class_Reference.new(r176)
                        R153 = MM.Association_Class_Reference.R153(
                            association_class_reference_i,
                            side_letter + ' Reference')
                        {'t_side' : MM.T_Reference, 'p_side' : MM.P_Reference}[side].new(R153 & r15_[side])
                    else:
                        r176 = MM.Association_Reference.R176(association_reference_i, 'Simple Association Reference')
                        MM.Simple_Association_Reference.new(r176 & r157)
                    
                    

        else:
            r100 = MM.Relationship.R100(relationship_i, 'Generalization')
            generalization_attr = MM.Generalization.constraint(
                {'Superclass' :  rel['superclass']})
            generalization_i = MM.Generalization.new(generalization_attr & r100)
            class_i_superclass = self.query_class(modeled_domain_i, rel['superclass'])
            r101_generalization = MM.Generalization.R101(generalization_i)
            r101_superclass = MM.Class.R101(class_i_superclass)
            r155_class = MM.Class.R155(class_i_superclass)
            facet_i = MM.Facet.new(r101_superclass & r101_generalization)
            r102 = MM.Facet.R102(facet_i, 'Superclass')
            superclass_i = MM.Superclass.new(r102)
            r103 = MM.Superclass.R103(superclass_i)
            r170 = MM.Superclass.R170(superclass_i)
            if len(generalization_i & r103) != 1:
                raise ManaException() # Check R103!
            for subclass_name in rel['subclasses']:
                class_i_subclass = self.query_class(modeled_domain_i, subclass_name)
                r150_class = MM.Class.R150(class_i_subclass)
                formalizing_class_role_i = MM.Formalizing_Class_Role.new(r150_relationship & r150_class) 
                r151 = MM.Formalizing_Class_Role.R151(formalizing_class_role_i, 'Subclass')
                r155_formalizing_class_role = MM.Formalizing_Class_Role.R155(formalizing_class_role_i)
                r101_subclass = MM.Class.R101(class_i_subclass)
                facet_i = MM.Facet.new(r101_subclass & r101_generalization)
                r102 = MM.Facet.R102(facet_i, 'Subclass')
                subclass_i = MM.Subclass.new(r102 & r151)
                r156 = MM.Subclass.R156(subclass_i)
                reference_i = self.instantiate_referential_attributes(modeled_domain_i, rnum, 'G', r155_class & r155_formalizing_class_role)
                r152 = MM.Reference.R152(reference_i, 'Generalization Reference')
                generalization_reference_i = MM.Generalization_Reference.new(r152 & r170 & r156)
            
    def instantiate_referential_attributes(self, modeled_domain_i, rnum, ref_letter : str, r155, side=None):
        reference_attr = MM.Reference.constraint({'Ref' : ref_letter})
        reference_i = MM.Reference.new(reference_attr & r155)
        r23 = MM.Reference.R23(reference_i)
        to_class_name = MM.Reference.value(reference_i, 'To class')
        class_i_to = self.query_class(modeled_domain_i, to_class_name)
        r20_to = MM.Class.R20(class_i_to)
        from_class_name = MM.Reference.value(reference_i, 'From class')
        class_i_from = self.query_class(modeled_domain_i, from_class_name)
        r20_from = MM.Class.R20(class_i_from)
        
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
        
        def attribute_by_name(r20, attribute_name):
            attribute_attr = MM.Attribute.constraint({'Name' : attribute_name})
            return exactly_one(MM.Attribute.query(attribute_attr & r20))
            
        number = {'I' : 1, 'I2' : 2, 'I3' :3}[ref_data['id']]
        identifier_attr = MM.Identifier_Attribute.constraint({'Identifier' : ('I', number)})
        for to_attribute, from_attribute in ref_data['ref_map'].items():
            attribute_i_to = attribute_by_name(r20_to, to_attribute)
            r22_attribute = MM.Attribute.R22(attribute_i_to)
            identifier_attribute_i = exactly_one(MM.Identifier_Attribute.query(identifier_attr & r22_attribute))
            r21_identifier_attribute = MM.Identifier_Attribute.R21(identifier_attribute_i)
            attribute_i_from = attribute_by_name(r20_from, from_attribute)
            r21_attribute = MM.Attribute.R21(attribute_i_from)
            MM.Attribute_Reference.new(r23 & r21_identifier_attribute & r21_attribute)

        return reference_i