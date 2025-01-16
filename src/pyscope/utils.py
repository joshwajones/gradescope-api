from enum import Enum, IntFlag
from dataclasses import dataclass
from typing import Union

class ConnState(Enum):
    INIT = 0
    LOGGED_IN = 1


class CourseSplit(Enum):
    INSTRUCTOR = 0
    STUDENT = 1
    ALL = 2


class CourseData(IntFlag):
    ASSIGNMENTS = 1
    ROSTER = 2


