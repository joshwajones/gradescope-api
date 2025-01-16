from abc import ABC, abstractmethod
from dataclasses import dataclass

UID = str

@dataclass
class RosterType(ABC):
    name: str

    @abstractmethod
    def unique_id(self) -> UID:
        raise NotImplementedError
    
    @abstractmethod
    def format(self) -> str:
        raise NotImplementedError