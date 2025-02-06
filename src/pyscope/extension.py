from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Union, TYPE_CHECKING

fieldtype = Union[datetime, int, float, timedelta]
numeric = Union[float, int]

if TYPE_CHECKING:
    from pyscope.assignment import GSAssignment

EXTENSION_TYPES = {
    "release_date": datetime,
    "due_date": datetime,
    "late_due_date": datetime,
    "time_limit_minutes": numeric,
    "release_delta": timedelta,
    "due_delta": timedelta,
    "late_due_delta": timedelta,
    "limit_multipler": numeric,
}


@dataclass
class GSExtension:
    fields: dict[str, fieldtype] = field(default_factory=dict)

    def get_extension_data(self, assignment: GSAssignment):
        release_date = assignment.release_date
        due_date = assignment.due_date
        late_due_date = (
            assignment.hard_due_date if assignment.hard_due_date else assignment.due_date
        )
        time_limit_minutes = assignment.time_limit

        if "release_date" in self.fields:
            release_date = self.fields["release_date"]
        if "due_date" in self.fields:
            due_date = self.fields["due_date"]
        if "late_due_date" in self.fields:
            late_due_date = self.fields["late_due_date"]
        if "time_limit_minutes" in self.fields:
            time_limit_minutes = self.fields["time_limit_minutes"]

        if "release_delta" in self.fields:
            release_date += self.fields["release_delta"]
        if "due_delta" in self.fields:
            due_date += self.fields["due_delta"]
        if "late_due_delta" in self.fields:
            late_due_date += self.fields["late_due_delta"]
        if "limit_multipler" in self.fields:
            time_limit_minutes = (
                self.fields["limit_multipler"] * time_limit_minutes if time_limit_minutes else None
            )

        data = {
            "release_date": release_date,
            "due_date": due_date,
            "hard_due_date": late_due_date,
            "time_limit_minutes": time_limit_minutes,
        }
        formatted_data = {}
        for k, v in data.items():
            assignment_key = k if k != "time_limit_minutes" else "time_limit"
            if v == getattr(assignment, assignment_key):
                continue
            if "date" in k:
                formatted_data[k] = GSExtension.format_date(v)
            else:
                formatted_data[k] = v

        return formatted_data

    @classmethod
    def create(cls, **kwargs):
        def _validate_kwargs():
            if not set(kwargs) <= set(EXTENSION_TYPES):
                raise ValueError(f"Invalid extension fields: {set(kwargs) - set(EXTENSION_TYPES)}")
            invalid_types = []
            for k, v in kwargs.items():
                if not isinstance(v, EXTENSION_TYPES[k]):
                    invalid_types.append(f"Invalid type for {k}: {type(v)}")
            if invalid_types:
                raise TypeError("\n".join(invalid_types))

        _validate_kwargs()
        return cls(fields=kwargs)

    @staticmethod
    def format_date(dt: Union[str, datetime]) -> str:
        if isinstance(dt, str):
            time = dt
        elif isinstance(dt, datetime):
            time = dt.strftime("%Y-%m-%dT%H:%M")
        else:
            raise TypeError
        return {"type": "absolute", "value": f"{time}"}
