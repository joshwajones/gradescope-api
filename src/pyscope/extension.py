from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Union

from pyscope.person import GSPerson

@dataclass
class GSExtension:
    student: GSPerson
    release_date: datetime = None
    due_date: datetime = None
    late_due_date: datetime = None
    time_limit_minutes: int = None

    release_delta: timedelta = timedelta(days=0)
    due_delta: timedelta = timedelta(days=0)
    late_due_delta: timedelta = timedelta(days=0)
    limit_multipler: int = 1

    def get_extension_data(self, assignment: 'GSAssignment'):
        original_release_date = assignment.release_date
        original_due_date = assignment.due_date
        original_late_due_date = assignment.late_due_date
        original_time_limit_minutes = assignment.time_limit_minutes

        if self.release_date is None:
            self.release_date = original_release_date + self.release_delta
        if self.due_date is None:
            self.due_date = original_due_date + self.due_delta
        if self.late_due_date is None:
            self.late_due_date = original_late_due_date + self.late_due_delta
        if self.time_limit_minutes is None:
            self.time_limit_minutes = original_time_limit_minutes * self.limit_multipler

        data = {
            'release_date': self.release_date,
            'due_date': self.due_date,
            'late_due_date': self.late_due_date,
            'time_limit_minutes': self.time_limit_minutes
        }
        for k, v in data.items():
            if 'date' in k:
                data[k] = GSExtension.format_date(v)
        return data

    @staticmethod
    def format_date(dt: Union[str, datetime]) -> str:
        if isinstance(dt, str):
            time = dt
        elif isinstance(dt, datetime):
            time = dt.strftime('%Y-%m-%dT%H:%M')
        else:
            raise TypeError
        return {
            'type': 'absolute',
            'value': f'{time}'
        }