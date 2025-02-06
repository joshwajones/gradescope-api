from pyscope.pyscope_types import UID, RosterType


class Roster:
    """A generic roster of entities.

    Each entity subclasses RosterType and thus has both a name (not necessarily unique) and a unique identifier.
    A Roster can store students, assignments, etc.
    """

    def __init__(self) -> None:
        """Initialize the roster."""
        self._name_to_entity: dict[str, RosterType] = {}
        self._uid_to_entity: dict[UID, RosterType] = {}

    def add(self, entity: RosterType) -> None:
        """Add an entity to the roster."""
        if entity.get_unique_id() in self._uid_to_entity:
            msg = f"UID {entity.get_unique_id()} already in roster"
            raise ValueError(msg)
        if entity.get_name() not in self._name_to_entity:
            self._name_to_entity[entity.get_name()] = []
        self._name_to_entity[entity.get_name()].append(entity)
        self._uid_to_entity[entity.get_unique_id()] = entity

    def _access_with_name(
        self,
        name: str,
        raise_error: bool = True,
    ) -> RosterType | None:
        if name not in self._name_to_entity:
            if raise_error:
                msg = "Name not in roster"
                raise ValueError(msg)
            return None
        named_entities = self._name_to_entity[name]
        if len(named_entities) > 1:
            if raise_error:
                msg = f"Ambiguous access - multiple entities with name {name}. \
                    Try again with an unambiguous identifier."
                raise ValueError(
                    msg,
                )
            return None
        return named_entities[0]

    def _access_with_uid(
        self,
        uid: UID,
        raise_error: bool = True,
    ) -> RosterType | None:
        if uid not in self._uid_to_entity:
            if raise_error:
                msg = "UID not in roster"
                raise ValueError(msg)
            return None
        return self._uid_to_entity[uid]

    def _access(
        self,
        *,
        name: str | None = None,
        uid: UID = None,
        entity: RosterType = None,
        raise_error: bool = True,
    ) -> RosterType | None:
        num_provided_fields = bool(name) + bool(uid) + bool(entity)
        if num_provided_fields != 1:
            if raise_error:
                msg = "Must provide exactly one of name, uid, or entity"
                raise ValueError(msg)
            return None
        if name:
            entity = self._access_with_name(name, raise_error)
        elif uid:
            entity = self._access_with_uid(uid, raise_error)
        return entity

    def remove_entity(
        self,
        *,
        name: str | None = None,
        uid: UID = None,
        entity: RosterType = None,
        raise_error: bool = True,
    ) -> bool:
        """Remove an entity from the roster.

        Uses the same access semantics as `get_entity`.

        Args:
            name (str | None): The name/nickname of the entity. If provided, must be a unique name.
            uid (UID): The unique identifier of the entity. This is always unambiguous.
            entity (RosterType): The entity to find. This is always unambiguous.
            raise_error (bool): If true, raise an error if the entity cannot be found. Otherwise,
                return None.

        Returns:
            bool: True if the entity was found and removed, False otherwise.

        """
        entity = self._access(name=name, uid=uid, entity=entity, raise_error=raise_error)
        if not entity:
            return False
        del self._uid_to_entity[entity.get_unique_id()]
        if len(self._name_to_entity[entity.get_name()]) == 1:
            del self._name_to_entity[entity.get_name()]
        else:
            self._name_to_entity[entity.get_name()].remove(entity)
        return True

    def get_entity(
        self,
        *,
        name: str | None = None,
        uid: UID = None,
        entity: RosterType = None,
        raise_error: bool = True,
    ) -> RosterType | None:
        """Return a given entity in the roster, or None if not found.

        Access can be specified with a name/nickname, a unique identifier, or with the entity itself.

        Args:
            name (str | None): The name/nickname of the entity. If provided, must be a unique name.
            uid (UID): The unique identifier of the entity. This is always unambiguous.
            entity (RosterType): The entity to find. This is always unambiguous.
            raise_error (bool): If true, raise an error if the entity cannot be found. Otherwise,
                return None.

        Returns:
            RosterType | None: The entity if found, or None.

        """
        return self._access(name=name, uid=uid, entity=entity, raise_error=raise_error)

    def get_all(self) -> list[RosterType]:
        """Return a list of all entities in the roster."""
        return list(self._uid_to_entity.values())

    def __len__(self) -> int:
        return len(self._uid_to_entity)

    def clear(self) -> None:
        """Clear the roster."""
        self._name_to_entity = {}
        self._uid_to_entity = {}
