from __future__ import annotations

from dataclasses import dataclass

from pyscope.pyscope_types import Crop, QuestionType, RosterType


@dataclass
class GSQuestion(RosterType):
    """A question in a Gradescope assignment."""

    question_id: str
    title: str
    weight: float
    children: list[GSQuestion]
    type: QuestionType
    parent_id: str | None
    content: list[str]
    crop: Crop

    def get_name(self) -> str:
        """Return the title of the question."""
        return self.title

    def get_unique_id(self) -> str:
        """Return the unique ID of the question."""
        return self.question_id

    def format(self) -> str:
        """Return a string representation of the question."""
        return f"{self.question_id}: {self.title}"

    def serialize(self) -> dict:
        """Serialize the question to a JSON dictionary that Gradescope can interpret."""
        children = [child.serialize() for child in self.children]
        return {
            "id": self.question_id,
            "title": self.title,
            "weight": self.weight,
            "crop_rect_list": self.crop,
            "children": children,
            "content": self.content,
        }

    def find_id_recursive(self, question_id: str) -> GSQuestion | None:
        """Check the subtree rooted at this question for a question with the given id."""
        if self.question_id == question_id:
            return self
        for child in self.children:
            found = child.find_id_recursive(question_id)
            if found:
                return found
        return None

    def __hash__(self) -> int:
        return hash(self.question_id)

    @classmethod
    def create_root(cls, children: list[GSQuestion]) -> GSQuestion:
        """Return a root question with the given children.

        The root question is useful to avoid special cases, and is never sent to Gradescope.
        """
        return cls(
            question_id=None,
            title="__ROOT__",
            weight=None,
            children=children,
            type=None,
            parent_id=None,
            content=None,
            crop=None,
        )

    @staticmethod
    def default_crop() -> Crop:
        """Return a default crop rect list, corresponding to a 0x0 crop on the first page."""
        return [{"x1": 0, "x2": 0, "y1": 0, "y2": 0, "page_number": 1}]
