from typing import Dict
from pyscope.pyscope_types import RosterType, UID

class Roster:
    """
    A generic roster of entities, where each entity subclasses RosterType and thus has both a name (not necessarily unique) and a unique identifier.
    Can be a roster of students, of assignments, etc.
    """
    def __init__(self):
        self._name_to_entity: Dict[str, RosterType] = {}
        self._uid_to_entity: Dict[UID, RosterType] = {}

    def add(self, entity: RosterType):
        if entity.get_unique_id() in self._uid_to_entity:
            raise ValueError(f"UID {entity.get_unique_id()} already in roster")
        if entity.get_name() not in self._name_to_entity:
            self._name_to_entity[entity.get_name()] = []
        self._name_to_entity[entity.get_name()].append(entity)
        self._uid_to_entity[entity.get_unique_id()] = entity
    
    def _access(self, *, name: str = None, uid: UID = None, entity: RosterType = None, raise_error: bool = True):
        num_provided_fields = bool(name) + bool(uid) + bool(entity)
        if num_provided_fields != 1:
            if raise_error:
                raise ValueError("Must provide exactly one of name, uid, or entity")
            return None
        if name:
            if name not in self._name_to_entity:
                if raise_error:
                    raise ValueError("Name not in roster")
                return None
            named_entities = self._name_to_entity[name]
            if len(named_entities) > 1:
                if raise_error:
                    raise ValueError(f"Ambiguous access - multiple entities with name {name}. Try again with an unambiguous identifier.")
                return None
            entity = named_entities[0]
        elif uid:
            if uid not in self._uid_to_entity:
                if raise_error:
                    raise ValueError("UID not in roster")
                return None
            entity = self._uid_to_entity[uid]
        return entity
    
    def remove_entity(self, *, name: str = None, uid: UID = None, entity: RosterType = None, raise_error: bool = True):
        entity = self._access(name=name, uid=uid, entity=entity, raise_error=raise_error)
        if not entity:
            return False
        del self._uid_to_entity[entity.get_unique_id()]
        if len(self._name_to_entity[entity.get_name()]) == 1:
            del self._name_to_entity[entity.get_name()]
        else:
            self._name_to_entity[entity.get_name()].remove(entity)
        return True
    
    def get_entity(self, *, name: str = None, uid: UID = None, entity: RosterType = None, raise_error: bool = True):
        return self._access(name=name, uid=uid, entity=entity, raise_error=raise_error)

    def get_all(self):
        return list(self._uid_to_entity.values())

    def __len__(self):
        return len(self._uid_to_entity)
    
    def clear(self):
        self._name_to_entity = {}
        self._uid_to_entity = {}

