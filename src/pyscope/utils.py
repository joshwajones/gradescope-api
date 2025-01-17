from enum import Enum, IntFlag
from dataclasses import dataclass
from typing import Union
from bs4 import BeautifulSoup

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

