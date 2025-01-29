from dataclasses import dataclass

from pyscope.pyscope_types import QuestionType, RosterType, Crop


@dataclass
class GSQuestion(RosterType):
    question_id: str
    title: str
    weight: float
    children: list["GSQuestion"]
    type: QuestionType
    parent_id: str
    content: list[str]
    crop: Crop

    def get_name(self) -> str:
        return self.title

    def get_unique_id(self) -> str:
        return self.question_id

    def format(self) -> str:
        return f"{self.question_id}: {self.title}"

    def serialize(self) -> dict:
        children = [child.serialize() for child in self.children]
        output = {
            "id": self.question_id,
            "title": self.title,
            "weight": self.weight,
            "crop_rect_list": self.crop,
            "children": children,
            "content": self.content,
        }
        return output

    def find_id_recursive(self, id) -> "GSQuestion":
        if self.question_id == id:
            return self
        for child in self.children:
            found = child.find_id_recursive(id)
            if found:
                return found
        return None

    def __hash__(self) -> int:
        return hash(self.question_id)

    @classmethod
    def create_root(cls, children: list["GSQuestion"]) -> "GSQuestion":
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
        return [{"x1": 0, "x2": 0, "y1": 0, "y2": 0, "page_number": 1}]
