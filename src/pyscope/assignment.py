from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from pyscope.exceptions import StudentNotFoundError
from pyscope.extension import GSExtension
from pyscope.pyscope_types import QuestionType, RosterType
from pyscope.question import GSQuestion
from pyscope.roster import Roster
from pyscope.utils import get_csrf_token, stream_file

if TYPE_CHECKING:
    from datetime import datetime

    from pyscope.course import GSCourse


@dataclass
class GSAssignment(RosterType):
    """An object that represents an assignment.

    Attributes:
        name (str): The name of the assignment.
        assignment_id (str): The ID of the assignment.
        points (int): The total points for the assignment.
        percent_graded (float): The percentage of the assignment that is graded.
        submissions (int): The number of submissions for the assignment.
        regrades_on (bool): Whether regrades are on for the assignment.
        release_date (datetime): The date the assignment is released.
        due_date (datetime): The date the assignment is due.
        hard_due_date (datetime): The hard due date.
        time_limit (int): The time limit for the assignment.

    """

    name: str
    assignment_id: str
    points: int
    percent_graded: float
    submissions: int
    regrades_on: bool
    release_date: datetime
    due_date: datetime
    hard_due_date: datetime
    time_limit: int

    session: requests.Session
    course: GSCourse

    def __post_init__(self) -> None:
        self.questions = Roster()
        self._loaded_questions = False

    def get_name(self) -> str:
        """Get the name of the assignment."""
        return self.name

    def get_unique_id(self) -> str:
        """Get the unique ID of the assignment."""
        return self.assignment_id

    @property
    def url(self) -> str:
        """Get the URL of the assignment."""
        return f"{self.course.url}/assignments/{self.assignment_id}"

    def serialize_questions(self) -> dict:
        """Serialize the questions to a dictionary."""
        return self.root.serialize()

    def _find_question_parent(self, parent_id: str) -> GSQuestion | None:
        self._load_questions_if_needed()

        def _find_recursive(curr_q: GSQuestion, parent_id: str) -> GSQuestion | None:
            if curr_q.question_id == parent_id:
                return curr_q
            if curr_q.children:
                for child in curr_q.children:
                    found = _find_recursive(child, parent_id)
                    if found:
                        return found
            return None

        return _find_recursive(self.root, parent_id)

    def get_question(
        self,
        *,
        question_id: str | None = None,
        title: str | None = None,
        question: GSQuestion = None,
    ) -> GSQuestion:
        """Get a question from the assignment.

        Supports a number of different ways to specify the question.

        Args:
            question_id (str | None): The ID of the question.
            title (str | None): The title of the question.
            question (GSQuestion | None): The question object.

        """
        self._load_questions_if_needed()
        return self.questions.get_entity(uid=question_id, name=title, entity=question)

    def add_question(
        self,
        title: str,
        weight: int,
        crop: dict | None = None,
        content: list | None = None,
        parent_id: str | None = None,
    ) -> None:
        """Add a new question to the assignment.

        Args:
            title (str): The title of the question.
            weight (int): The weight of the question.
            crop (dict | None): The crop of the question.
            content (list | None): The content of the question.
            parent_id (str | None): The ID of the parent question.

        """
        if content is None:
            content = []
        self._load_questions_if_needed()

        new_crop = crop if crop else GSQuestion.default_crop()

        parent = self._find_question_parent(parent_id)
        if not parent:
            msg = f"Could not find parent question with id {parent_id}"
            raise ValueError(msg)
        if not parent.children:
            parent.children = []

        new_question = GSQuestion(
            question_id=None,
            title=title,
            weight=weight,
            children=[],
            type=None,
            parent_id=parent_id,
            crop=new_crop,
            content=content,
        )
        parent.children.append(new_question)
        self.questions.add(new_question)

        root = self.serialize_questions()
        new_patch = {
            "assignment": {"identification_regions": {"name": None, "sid": None}},
            "question_data": root["children"],
        }

        authenticity_token = get_csrf_token(self.course)

        self.session.patch(
            f"{self.url}/outline/",
            headers={
                "x-csrf-token": authenticity_token,
                "Content-Type": "application/json",
            },
            data=json.dumps(new_patch, separators=(",", ":")),
        )

        # Wastful, but response does not include the new question ID
        self._loaded_questions = False

    def remove_question(
        self,
        *,
        question_id: str | None = None,
        title: str | None = None,
        question: GSQuestion | None = None,
    ) -> None:
        """Remove a question from the assignment.

        Supports a number of different ways to specify the question to remove.

        Args:
            question_id (str | None): The ID of the question.
            title (str | None): The title of the question.
            question (GSQuestion | None): The question object.

        """
        self._load_questions_if_needed()
        question = self.get_question(question_id=question_id, title=title, question=question)

        parent = self._find_question_parent(question.parent_id)
        if not parent:
            msg = f"Could not find parent question with id {question.parent_id}"
            raise ValueError(msg)
        parent.children = [q for q in parent.children if q.question_id != question.question_id]
        root = self.serialize_questions()

        new_patch = {
            "assignment": {"identification_regions": {"name": None, "sid": None}},
            "question_data": root["children"],
        }

        authenticity_token = get_csrf_token(self.course)
        self.session.patch(
            f"{self.url}/outline/",
            headers={
                "x-csrf-token": authenticity_token,
                "Content-Type": "application/json",
            },
            data=json.dumps(new_patch, separators=(",", ":")),
        )

        self.questions.remove_entity(entity=question)

    def _match_questions_regex(
        self,
        *,
        question_ids: list[str] | None = None,
        question_titles: list[str] | None = None,
    ) -> list[GSQuestion]:
        def _check_match(
            question: GSQuestion,
            question_id: str | None = None,
            question_title: str | None = None,
        ) -> bool:
            is_match = False
            if question_id:
                is_match = is_match or bool(re.match(question_id, question.question_id))
            if question_title:
                is_match = is_match or bool(re.match(question_title, question.title))
            return is_match

        matched_questions = []
        if question_ids is None:
            question_ids = []
        if question_titles is None:
            question_titles = []

        identifiers = [{"question_id": question_id} for question_id in question_ids] + [
            {"question_title": question_title} for question_title in question_titles
        ]

        all_questions = self.questions.get_all()
        matched_questions = {
            question for question in all_questions for identifier in identifiers if _check_match(question, **identifier)
        }
        return list(matched_questions)

    def remove_questions(
        self,
        *,
        question_ids: list[str] | None = None,
        question_titles: list[str] | None = None,
        questions: list[GSQuestion] | None = None,
    ) -> None:
        """Remove questions from the assignment.

        Supports a number of different ways to specify the questions to remove.

        Args:
            question_ids (list[str] | None): A list of question IDs.
            question_titles (list[str] | None): A list of question titles. If provided, must be unique.
            questions (list[GSQuestion] | None): A list of questions.

        """
        self._load_questions_if_needed()
        if questions is None:
            questions = []
        matched_questions = set(
            self._match_questions_regex(question_ids=question_ids, question_titles=question_titles),
        )
        matched_questions |= set(questions)
        for question in matched_questions:
            self.remove_question(question=question)

    def add_instructor_submission(self, fname: str | Path) -> None:
        """Upload a PDF submission."""
        file = Path(fname)
        authenticity_token = get_csrf_token(self.course)

        submission_files = {"file": file.open("rb")}

        self.session.post(
            f"{self.url}/submission_batches",
            files=submission_files,
            headers={"x-csrf-token": authenticity_token},
        )

    def add_student_submission(self, fname: str | Path, student_email: str) -> None:
        """Add a student submission for the assignment.

        Args:
            fname (str or Path): The path to the submission file.
            student_email (str): The email of the student.

        """
        file = Path(fname)
        roster_resp = self.session.get(
            f"{self.url}/submission_batches",
            headers={"x-csrf-token": get_csrf_token(self.course)},
        )
        roster = json.loads(roster_resp.text)["roster"]
        email_to_id = {person["email"]: person["id"] for person in roster}

        with file.open("rb") as f:
            fdata = f.read()
        file_data = {"pdf_attachment": ("pdf_attachment.pdf", fdata, "application/pdf")}
        data = {
            "owner_id": email_to_id[student_email],
        }
        self.session.post(
            f"{self.url}/submissions",
            data=data,
            files=file_data,
            headers={"x-csrf-token": get_csrf_token(self.course)},
        )

    def _change_publish_status(self, published: bool) -> None:
        authenticity_token = get_csrf_token(self.course)
        data = {"assignment[published]": "true" if published else "false"}
        self.session.patch(self.url, data=data, headers={"x-csrf-token": authenticity_token})

    def publish_grades(self) -> None:
        """Publish the assignment grades."""
        self._change_publish_status(published=True)

    def unpublish_grades(self) -> None:
        """Unpublish the assignment grades."""
        self._change_publish_status(published=False)

    def export_evaluations(self, fname: str | Path | None = None) -> bytes:
        """Download the raw evaluations as a CSV file to fname, and returns the contents."""
        data = self.session.get(f"{self.url}/export_evaluations").content
        if fname:
            fname = Path(fname)
            if not fname.endswith(".csv"):
                fname += ".csv"
            with fname.open("wb") as f:
                f.write(data)
        return data

    def download_grades(self, fname: str | Path | None = None) -> str:
        """Download the grades as a CSV file to fname, and return the contents."""
        fname = Path(fname)
        response = self.session.get(f"{self.url}/scores.csv")
        if fname:
            if not fname.endswith(".csv"):
                fname += ".csv"
            with fname.open("w") as file:
                file.write(response.text)
        return response.text

    def download_submissions(
        self,
        fname: str | Path | None = None,
        unzip: bool = True,
        timeout: float = float("inf"),
        sleep_time: float = 1,
        chunk_size: int = 8192,
        show_bar: bool = True,
    ) -> None:
        """Export the submissions to a zip file, and then download them.

        This is done in a chunked fashion for speed and responsiveness.

        Args:
            fname (str or Path, optional): The filename to save the zip file to.
            unzip (bool, optional): Whether to unzip the zip file. Defaults to True.
            timeout (float, optional): The timeout for the export and download. Defaults to infinity, i.e. no timeout.
            sleep_time (float, optional): The time to sleep between checking whether the download is complete.
            chunk_size (int, optional): The size of each chunk. Defaults to 8192B.
            show_bar (bool, optional): Whether to show a progress bar. Defaults to True.

        """

        def _get_default_fname() -> str:
            if unzip:
                return "./"
            return "./submissions.zip"

        if fname is None:
            fname = _get_default_fname()
        fname = Path(fname)

        logging.debug("Starting export...")

        response = self.session.post(
            f"{self.url}/export",
            headers={"x-csrf-token": get_csrf_token(self.course)},
        )
        generated_file_id = json.loads(response.text)["generated_file_id"]

        check_url = f"{self.course.url}/generated_files/{generated_file_id}.json"

        response = self.session.get(check_url)

        def _get_progress(most_recent_response: requests.Response) -> float:
            return 100 * float(json.loads(most_recent_response.text)["progress"])

        def _finished_exporting(most_recent_response: requests.Response) -> bool:
            return json.loads(most_recent_response.text)["status"] == "completed"

        pbar = tqdm(
            total=100,
            desc="Exporting...",
            disable=not show_bar,
            bar_format="{l_bar}{bar} [{elapsed}>{remaining}]",
        )
        curr_progress = 0
        start_time = time.time()
        while time.time() - start_time < timeout and curr_progress < 100:  # noqa: PLR2004
            progress = _get_progress(response)
            pbar.update(progress - curr_progress)

            curr_progress = progress

            time.sleep(sleep_time)
            response = self.session.get(check_url)
        if not _finished_exporting(response):
            msg = "Timed out waiting for export to finish"
            raise TimeoutError(msg)
        pbar.update(100 - curr_progress)
        pbar.close()

        total_time = time.time() - start_time
        logging.debug(
            "Export finished in %.2f seconds. Beginning download...",
            total_time,
        )

        # check that export is ready for download on server
        pattern = re.escape(f"{self.course.url}/generated_files/") + r"([0-9]+)\.zip"

        def _ready_for_download(most_recent_response: requests.Response) -> bool:
            return re.match(pattern, most_recent_response.headers["Location"])

        response = self.session.head(f"{self.url}/export")
        while not _ready_for_download(response):
            time.sleep(sleep_time)
            response = self.session.head(f"{self.url}/export")

        start_attempt_export = time.time()
        while time.time() - start_attempt_export < timeout:
            try:
                download_start_time = time.time()
                stream_file(
                    self.session,
                    f"{self.url}/export",
                    fname,
                    chunk_size=chunk_size,
                    unzip=unzip,
                    show_bar=show_bar,
                )
                download_end_time = time.time()
                break
            except requests.exceptions.HTTPError as e:
                logging.debug(e)
                logging.info("File not yet ready for download. Retrying...")
                time.sleep(2.0)
        logging.debug("Downloaded in %.2f seconds.", download_end_time - download_start_time)

    def _load_questions_if_needed(self) -> None:
        if not self._loaded_questions:
            self._lazy_load_questions()

    def _lazy_load_questions(self) -> None:
        self.questions.clear()
        outline_resp = self.session.get(f"{self.url}/outline/edit")
        parsed_outline_resp = BeautifulSoup(outline_resp.text, "html.parser")

        props = parsed_outline_resp.find(
            "div",
            attrs={"data-react-class": "AssignmentOutline"},
        ).get("data-react-props")
        json_props = json.loads(props)
        outline = json_props["outline"]

        def _parse_recursive(outline: dict) -> GSQuestion:
            question = GSQuestion(
                question_id=outline["id"],
                title=outline["title"],
                weight=outline["weight"],
                type=QuestionType.str_to_enum(outline["type"]),
                children=[],
                parent_id=outline["parent_id"],
                content=outline["content"],
                crop=outline["crop_rect_list"],
            )
            for child in outline.get("children", []):
                question.children.append(_parse_recursive(child))
            self.questions.add(question)
            return question

        all_questions = [_parse_recursive(q) for q in outline]
        self.root = GSQuestion.create_root(all_questions)
        self._loaded_questions = True

    def _apply_extension(self, extension: GSExtension, student_email: str) -> None:
        """Apply an extension to a student.

        Inspired by https://github.com/cs161-staff/gradescope-api/blob/master/src/gradescope_api/assignment.py.
        """
        extension_url = f"{self.url}/extensions"
        extension_resp = self.session.get(extension_url)
        parsed_extension_resp = BeautifulSoup(extension_resp.text, "html.parser")
        props = parsed_extension_resp.find("li", {"data-react-class": "AddExtension"})["data-react-props"]
        data = json.loads(props)
        students = {row["email"]: row["id"] for row in data.get("students", [])}
        if student_email not in students:
            msg = f"Could not find student with email {student_email}"
            raise StudentNotFoundError(msg)
        student_id = students[student_email]  # NOT the same as extension.student.data_id
        authenticity_token = parsed_extension_resp.find("meta", attrs={"name": "csrf-token"})["content"]
        new_settings = {"visible": True} | extension.get_extension_data(self)
        payload = {
            "override": {
                "settings": new_settings,
                "user_id": student_id,
            },
        }
        headers = {
            "x-csrf-token": authenticity_token,
            "Content-Type": "application/json",
        }
        self.session.post(extension_url, headers=headers, data=json.dumps(payload), timeout=20)

    def apply_extension(self, extension: GSExtension, student_email: str) -> None:
        """Apply an extension to a student.

        Args:
            extension (GSExtension): The extension to apply.
            student_email (str): The email of the student to apply the extension to.

        """
        self._apply_extension(extension, student_email=student_email)

    def remove_extension(self, student_email: str) -> None:
        """Remove an extension from a student, by re-applying all default fields.

        Args:
            student_email (str): The email of the student to remove the extension from.

        """
        self._apply_extension(GSExtension(), student_email=student_email)

    def format(self, prefix: str = "\t") -> str:
        """Return a string representation of the assignment."""
        return f"{prefix}Name: {self.name}\n{prefix}ID: {self.assignment_id}"

    def to_json(self) -> dict:
        """Return a JSON representation of the assignment."""
        return {
            "name": self.name,
            "id": self.assignment_id,
            "release": self.release_date.isoformat(),
            "due": self.due_date.isoformat(),
        }

    def get_hard_due_date(self) -> datetime:
        """Get the hard due date of the assignment, if it exists."""
        if self.hard_due_date:
            return self.hard_due_date
        return self.due_date
