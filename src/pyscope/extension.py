from dataclasses import dataclass
from datetime import datetime

from pyscope.person import GSPerson

@dataclass
class GSExtension:
    student: GSPerson
    release_date: datetime = None
    due_date: datetime = None
    late_due_date: datetime = None
    time_limit_minutes: int = None
