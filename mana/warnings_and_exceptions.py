





def output_str(input : str):
    rows = input.split('\n')
    return 'Model-Analysis: [' \
       + '\n                 '.join(rows) + ']'


class ManaClassImportFromMissingSubsystemWarning():
    def __init__(self, _class : str, subsys : str):
        self._class = _class
        self.subsys = subsys
    
    def __str__(self):
        part1 = f'Warning, Class: "{self._class}"'
        part2 = f' is imported from none existent Subsystem "{self.subsys}"'
        text = part1 + part2
        return output_str(text)

class ManaException(Exception):
    def __init__(self, exit = False):
        self._exit = exit
    def exit(self) -> bool:
        return self._exit if hasattr(self, '_exit') else True

class ManaParserException(ManaException):
    def __init__(self, file_path, _type, e):
        self.file_path = file_path
        self._type = _type
        self.e = e

    def __str__(self):
        text = f'Parse error in {self._type}: "{self.file_path}"\n{str(self.e)[:-1]}'
        return output_str(text)
    
class ManaRefAttrNotFoundException(ManaException):
    def __init__(self, rnum : str, _class : str, subsys : str, attributes : list):
        self.rnum = rnum
        self._class = _class
        self.subsys = subsys
        self.attributes = attributes
        
    def __str__(self):
        part1 = f'Can not find referred attributes for Relationship: "{self.rnum}"'
        part2 = f',\nat class: "{self._class}"'
        part3 = f' declared in Subsystem: "{self.subsys}"'
        part4 = f',\nrepresented by formalized attributes: '
        part5 = '"' + '", "'.join(self.attributes) + '"'
        text = part1 + part2 + part3 + part4 + part5
        return output_str(text)

class ManaTypeNotDefiedException(ManaException):
    def __init__(self, attributes : list):
        self.attributes = attributes
        
    def __str__(self):
        text = 'Type not defined for the following list of attributes:'
        for _class, attr, subsys in self.attributes:
            part1 = f'\n* at Class: "{_class}"'
            part2 = f', Attribute: "{attr}"'
            part3 = f' in Subsystem: "{subsys}"'
            text += part1 + part2 + part3 
        return output_str(text)
    
class ManaMultipleClassDeclarationException(ManaException):
    def __init__(self, _class : str, subsys1 : str, subsys2 : str):
        self._class = _class
        self.subsys1 = subsys1
        self.subsys2 = subsys2
        
    def __str__(self):
        part1 = f'Class: "{self._class}"'
        part2 = f' is defined multiple times both in Subsystem: "{self.subsys1}"'
        part3 = f' and in Subsystem: "{self.subsys2}"'
        text = part1 + part2 + part3
        return output_str(text)
    
class ManaClassImportedFromWrongSubsystemException(ManaException):
    def __init__(self, _class : str, from_subsys : str, into_subsys : str, declared_subsys : str):
        self._class = _class
        self.from_subsys = from_subsys
        self.into_subsys = into_subsys
        self.declared_subsys = declared_subsys
        
    def __str__(self):
        part1 = f'Class: "{self._class}"'
        part2 = f' imported form Subsystem: "{self.from_subsys}"'
        part3 = f'\ninto Subsystem: "{self.into_subsys}"'
        part4 = f' but was declared in Subsystem: "{self.declared_subsys}"'
        text = part1 + part2 + part3 + part4
        return output_str(text)
    

class ManaClassMissingInSubsystemException(ManaException):
    def __init__(self, _class : str, subsys : str):
        self._class = _class
        self.subsys = subsys
        
    def __str__(self):
        part1 = f'Class: "{self._class}"'
        part2 = f' is missing in Subsystem: "{self.subsys}"'
        text = part1 + part2
        return output_str(text)
    
    
    
class ManaUnknownClassInRelationshipException(ManaException):
    def __init__(self, rnum : str, _class : str, subsys : str):
        self.rnum = rnum
        self._class = _class
        self.subsys = subsys
        
    def __str__(self):
        part1 = f'Unknown Class Name: "{self._class}"'
        part2 = f' in specification for Relationship: "{self.rnum}"'
        part3 = f'\nwhich is declared in Subsystem: "{self.subsys}"'
        text = part1 + part2 + part3
        return output_str(text)
    
class ManaUnknownReferentialAttributeException(ManaException):
    def __init__(self, rnum : str, _class : str, subsys : str):
        self.rnum = rnum
        self._class = _class
        self.subsys = subsys
        
    def __str__(self):
        part1 = f'Class: "{self._class}"'
        part2 = f' in Subsystem: "{self.subsys}"'
        part3 = f'\nhas a referential attribute over an unknown Relationship: "{self.rnum}"'
        text = part1 + part2 + part3
        return output_str(text)
    
class ManaInvalidReferentialAttributeException(ManaException):
    def __init__(self, rnum : str, _class : str, subsys : str):
        self.rnum = rnum
        self._class = _class
        self.subsys = subsys
        
    def __str__(self):
        part1 = f'Relationship: "{self.rnum}"'
        part2 = f' has an invalid referential attribute at Class: "{self._class}"'
        part3 = f' in Subsystem: "{self.subsys}"'
        text = part1 + part2 + part3
        return output_str(text)
