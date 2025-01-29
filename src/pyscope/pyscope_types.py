from __future__ import annotations
from enum import Enum, IntFlag
from abc import abstractmethod
from typing import List, Dict

UID = str
Crop = List[Dict[str, int]]


class ConnState(Enum):
    INIT = 0
    LOGGED_IN = 1


class CourseSplit(Enum):
    INSTRUCTOR = 0
    STUDENT = 1
    ALL = 2


class SubmissionType(Enum):
    IMAGE = 0
    PDF = 1

    def __str__(self):
        if self == SubmissionType.IMAGE:
            return "image"
        elif self == SubmissionType.PDF:
            return "pdf"


class CourseData(IntFlag):
    ASSIGNMENTS = 1
    ROSTER = 2


class RosterType:
    @abstractmethod
    def get_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_unique_id(self) -> UID:
        raise NotImplementedError

    @abstractmethod
    def format(self) -> str:
        raise NotImplementedError

    def __hash__(self):
        return hash(self.get_unique_id())


class QuestionType(Enum):
    FREE_RESPONSE = 0
    QUESTION_GROUP = 1

    @classmethod
    def str_to_enum(cls, s: str) -> "QuestionType":
        return {
            "FreeResponseQuestion": cls.FREE_RESPONSE,
            "QuestionGroup": cls.QUESTION_GROUP,
        }[s]

    @classmethod
    def enum_to_str(cls, e: QuestionType) -> str:
        return {
            cls.FREE_RESPONSE: "FreeResponseQuestion",
            cls.QUESTION_GROUP: "QuestionGroup",
        }[e]

    def __str__(self) -> str:
        return self.enum_to_str(self)
