"""Classes for modeling people associated with a course."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pyscope.pyscope_types import RosterType


class GSRole(Enum):
    """The different roles available through Gradescope."""

    STUDENT = 0
    INSTRUCTOR = 1
    TA = 2
    READER = 3

    @classmethod
    def from_str(cls, role: str) -> GSRole:
        """Return the GSRole corresponding to the string."""
        return cls(role)

    def to_str(self) -> str:
        """Return a string representation of the role."""
        return {
            GSRole.INSTRUCTOR: "Instructor",
            GSRole.STUDENT: "Student",
            GSRole.TA: "TA",
            GSRole.READER: "Reader",
        }[self]


@dataclass
class GSPerson(RosterType):
    """A person in a course - could be a student or instructor (or any role.)."""

    name: str
    data_id: str
    sid: str | None
    email: str
    role: GSRole = None

    def get_name(self) -> str:
        """Return the name of the person."""
        return self.name

    def get_unique_id(self) -> str:
        """Return the unique ID of the person."""
        return self.email

    def format(self, prefix: str = "\t") -> str:
        """Return a string representation of the person."""
        return f"{prefix}Name: {self.name}\n{prefix}Email: {self.email}\n{prefix}Role: {self.role.to_str()}"
