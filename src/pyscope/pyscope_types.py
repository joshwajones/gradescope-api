"""An assortment of various types used throughout the library."""

from __future__ import annotations

from abc import abstractmethod
from enum import Enum, IntFlag
from typing import TYPE_CHECKING, Any

UID = str
Crop = list[dict[str, int]]

if TYPE_CHECKING:
    from pyscope.course import GSCourse

    CourseInfo = dict[str, GSCourse | bool]
else:
    CourseInfo = Any


class ConnState(Enum):
    """The state of a connection to Gradescope."""

    INIT = 0
    LOGGED_IN = 1


class CourseSplit(Enum):
    """Which courses to load when logging in."""

    INSTRUCTOR = 0
    STUDENT = 1
    ALL = 2


class SubmissionType(Enum):
    """The type of a submission, specified during creation."""

    IMAGE = 0
    PDF = 1

    def __str__(self) -> str:
        return self.name.lower()


class CourseData(IntFlag):
    """Models the data that a course needs - assignments and students."""

    ASSIGNMENTS = 1
    ROSTER = 2


class RosterType:
    """A generic entity that can be added to a roster."""

    @abstractmethod
    def get_name(self) -> str:
        """Return the name/nickname of the entity; this need not be unique."""
        raise NotImplementedError

    @abstractmethod
    def get_unique_id(self) -> UID:
        """Return the unique ID of the entity."""
        raise NotImplementedError

    @abstractmethod
    def format(self) -> str:
        """Return a string representation of the entity."""
        raise NotImplementedError

    def __hash__(self) -> int:
        """Return the hash of roster entity; the ID is unique, so it can be used."""
        return hash(self.get_unique_id())


class QuestionType(Enum):
    """The type of a question on Gradescope."""

    FREE_RESPONSE = 0
    QUESTION_GROUP = 1

    @classmethod
    def str_to_enum(cls, s: str) -> QuestionType:
        """Return the enum corresponding to the string."""
        return {
            "FreeResponseQuestion": cls.FREE_RESPONSE,
            "QuestionGroup": cls.QUESTION_GROUP,
        }[s]

    @classmethod
    def enum_to_str(cls, e: QuestionType) -> str:
        """Return the string representation of the enum."""
        return {
            cls.FREE_RESPONSE: "FreeResponseQuestion",
            cls.QUESTION_GROUP: "QuestionGroup",
        }[e]

    def __str__(self) -> str:
        return self.enum_to_str(self)
