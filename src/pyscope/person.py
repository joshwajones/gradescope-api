from enum import Enum
from dataclasses import dataclass

from pyscope.pyscope_types import RosterType
from pyscope.exceptions import GSRoleException

class GSRole(Enum):
    STUDENT = 0
    INSTRUCTOR = 1
    TA = 2
    READER = 3
    
    def from_str(val):
        if isinstance(val, GSRole):
            return val
        strings = {
            'Instructor': GSRole.INSTRUCTOR,
            'Student': GSRole.STUDENT,
            'TA': GSRole.TA,
            'Reader': GSRole.READER
        }
        role =  strings.get(val)
        if role is not None:
            return role
        else:
            raise GSRoleException("Not a valid role string: " + role)  

    def to_str(val):
        strings = {
            GSRole.INSTRUCTOR : 'Instructor',
            GSRole.STUDENT : 'Student',
            GSRole.TA : 'TA',
            GSRole.READER : 'Reader'
        }
        return strings[val]
        

@dataclass
class GSPerson(RosterType):
    name: str
    data_id: str
    sid: str
    email: str
    role: GSRole = None
    
    def unique_id(self):
        return self.email
    
    def format(self, prefix='\t'):
        return f"{prefix}Name: {self.name}\n{prefix}Email: {self.email}\n{prefix}Role: {self.role_str}"
 
    