from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyscope.assignment import GSAssignment

fieldtype = datetime | int | float | timedelta
numeric = float | int


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
    """A class modeling an extension to an assignment."""

    fields: dict[str, fieldtype] = field(default_factory=dict)

    def _translate_key(self, key: str) -> str:
        if key == "hard_due_date":
            return "late_due_date"
        return key

    def get_extension_data(self, assignment: GSAssignment) -> dict[str, str]:
        """Parse the extension data into the format expected by the Gradescope.

        Args:
            assignment (GSAssignment): The assignment to which the extension is applied.

        Returns:
            dict: The extension data in the format expected by the Gradescope.

        """
        data = {
            "release_date": assignment.release_date,
            "due_date": assignment.due_date,
            "hard_due_date": assignment.hard_due_date if assignment.hard_due_date else assignment.due_date,
            "time_limit_minutes": assignment.time_limit,
        }

        for key, value in data.items():
            data[key] = self.fields.get(self._translate_key(key), value)

        if "release_delta" in self.fields:
            data["release_date"] += self.fields["release_delta"]
        if "due_delta" in self.fields:
            data["due_date"] += self.fields["due_delta"]
        if "late_due_delta" in self.fields:
            data["hard_due_date"] += self.fields["late_due_delta"]
        if "limit_multipler" in self.fields:
            data["time_limit_minutes"] = (
                self.fields["limit_multipler"] * data["time_limit_minutes"] if data["time_limit_minutes"] else None
            )

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

    def get_timedelta(self) -> timedelta:
        """Get the total timedelta for the extension."""
        return max(
            self.fields.get("late_due_delta", timedelta(days=0)),
            self.fields.get("due_delta", timedelta(days=0)),
        )

    @classmethod
    def create(cls, **fields: dict[str, fieldtype]) -> GSExtension:
        """Create a new extension from the given fields, and performs type validation."""

        def _validate_kwargs() -> None:
            if not set(fields) <= set(EXTENSION_TYPES):
                msg = f"Invalid extension fields: {set(fields) - set(EXTENSION_TYPES)}"
                raise ValueError(msg)
            invalid_types = []
            for k, v in fields.items():
                if not isinstance(v, EXTENSION_TYPES[k]):
                    invalid_types.append(f"Invalid type for {k}: {type(v)}")
            if invalid_types:
                msg = "Invalid types found:" + "\n\t".join(invalid_types)
                raise TypeError(msg)

        _validate_kwargs()
        return cls(fields=fields)

    @staticmethod
    def format_date(date: str | datetime) -> str:
        """Return a string representation of a date."""
        if isinstance(date, str):
            time = date
        elif isinstance(date, datetime):
            time = date.strftime("%Y-%m-%dT%H:%M")
        else:
            raise TypeError
        return {"type": "absolute", "value": f"{time}"}
