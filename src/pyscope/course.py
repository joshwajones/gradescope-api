import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import click
import requests
from bs4 import BeautifulSoup

from pyscope.assignment import GSAssignment
from pyscope.exceptions import HTMLParseError
from pyscope.person import GSPerson, GSRole
from pyscope.pyscope_types import CourseData, SubmissionType
from pyscope.roster import Roster
from pyscope.utils import get_csrf_token


@dataclass
class GSCourse:
    """An object that represents a Gradescope course.

    Tracks all the important data about the course, e.g. roster, assignments, etc.

    Attributes:
        course_id (str): The ID of the course.
        name (str): The name of the course.
        nickname (str): The nickname of the course.
        session (requests.Session): The session used to make requests.
        year (int | None): The year of the course.

        _roster (Roster): A roster of people in the course. Should NOT be accessed directly, as it may be invalid.
        _assignments (Roster): A list of assignments. Should NOT be accessed directly, as it may be invalid.
        _currently_loaded (int): A representation of the currently valid data.

    """

    course_id: str
    name: str
    nickname: str
    session: requests.Session
    year: int | None

    def __post_init__(self) -> None:
        self._roster = Roster()
        self._assignments = Roster()
        self._currently_loaded = 0

    @property
    def url(self) -> str:
        """Get the full URL of the course."""
        return f"https://www.gradescope.com/courses/{self.course_id}"

    def update_roster(self) -> None:
        """Update the person roster."""
        self._roster.clear()
        self._lazy_load_roster()

    def update_assignments(self) -> None:
        """Update the assignment roster."""
        self._assignments.clear()
        self._lazy_load_assignments()

    # ~~~~~~~~~~~~~~~~~~~~~~PEOPLE~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def add_person(
        self,
        name: str,
        email: str,
        role: GSRole,
        sid: str | None = None,
        notify: bool = False,
    ) -> None:
        """Add a person to the course.

        For the same reason as with `add_assignment`, this is done lazily.

        Args:
            name (str): The name of the person.
            email (str): The email of the person.
            role (GSRole): The role of the person.
            sid (str | None, optional): The SID of the person. Defaults to None.
            notify (bool, optional): Whether to notify the person via email. Defaults to False.

        """
        self._load_necessary_data(CourseData.ROSTER)

        authenticity_token = get_csrf_token(self)
        person_params = {
            "utf8": "✓",
            "user[name]": name,
            "user[email]": email,
            "user[sid]": "" if sid is None else sid,
            "course_membership[role]": role.value,
            "button": "",
        }
        if notify:
            person_params["notify_by_email"] = 1

        self.session.post(
            f"{self.url}/memberships",
            data=person_params,
            headers={"x-csrf-token": authenticity_token},
        )

        # Wasteful, but post response does not include new person's data id
        self._currently_loaded &= ~CourseData.ROSTER

    def remove_person(
        self,
        *,
        name: str | None = None,
        email: str | None = None,
        person: GSPerson = None,
        ask_for_confirmation: bool = True,
    ) -> None:
        """Remove a person from the course."""
        self._load_necessary_data(CourseData.ROSTER)

        authenticity_token = get_csrf_token(self)
        remove_params = {"_method": "delete", "authenticity_token": authenticity_token}
        person = self._roster.get_entity(name=name, uid=email, entity=person, raise_error=False)
        if ask_for_confirmation and not click.confirm(
            f"Found person:\n{person.format()}.\nAre you sure you want to remove?",
            default=False,
        ):
            return

        self.session.post(
            f"https://www.gradescope.com/courses/{self.course_id}/memberships/{person.data_id}",
            data=remove_params,
            headers={"x-csrf-token": authenticity_token},
        )
        self._roster.remove_entity(entity=person)

    def change_person_role(
        self,
        *,
        name: str | None = None,
        email: str | None = None,
        person: GSPerson = None,
        new_role: GSRole,
    ) -> None:
        """Change the role of a person in the course."""
        self._load_necessary_data(CourseData.ROSTER)
        authenticity_token = get_csrf_token(self)
        role_params = {
            "course_membership[role]": new_role.value,
        }
        person = self._roster.get_entity(name=name, uid=email, entity=person)

        self.session.patch(
            f"{self.url}/memberships/{person.data_id}/update_role",
            data=role_params,
            headers={"x-csrf-token": authenticity_token},
        )
        person.role = new_role

    def get_person(
        self,
        *,
        name: str | None = None,
        email: str | None = None,
        person: GSPerson = None,
    ) -> GSPerson:
        """Get a person by name or email."""
        self._load_necessary_data(CourseData.ROSTER)
        return self._roster.get_entity(name=name, uid=email, entity=person, raise_error=False)

    def get_all_people(self) -> list[GSPerson]:
        """Get a list of all people in the course."""
        self._load_necessary_data(CourseData.ROSTER)
        return self._roster.get_all()

    def add_assignment(
        self,
        name: str,
        release: datetime,
        due: datetime,
        template_file_path: str | Path,
        submission_type: SubmissionType = SubmissionType.PDF,
        student_submissions: bool = True,
        late_submissions: bool = False,
        group_submissions: int = 0,
    ) -> None:
        """Add an assignment to the course.

        The assignment id is not returned with the response. Therefore, rather than making an additional request
        to get the assignment ID, the assignment roster is marked invalid; any later accesses will reload it.

        Args:
            name (str): The name of the assignment.
            release (datetime): The date the assignment is released.
            due (datetime): The date the assignment is due.
            template_file_path (str or Path): The path to the template PDF file.
            submission_type (SubmissionType, optional): The type of submission. Defaults to SubmissionType.PDF.
            student_submissions (bool, optional): Whether student submissions are allowed. Defaults to True.
            late_submissions (bool, optional): Whether late submissions are allowed. Defaults to False.
            group_submissions (int, optional): Whether group submissions are allowed. Defaults to 0.

        """
        template_file_path = Path(template_file_path)
        self._load_necessary_data(CourseData.ASSIGNMENTS)
        authenticity_token = get_csrf_token(self)

        assignment_params = {
            "authenticity_token": authenticity_token,
            "assignment[title]": name,
            "assignment[student_submission]": student_submissions,
            "assignment[release_date_string]": release,
            "assignment[due_date_string]": due,
            "assignment[allow_late_submissions]": int(late_submissions),
            "assignment[submission_type]": str(submission_type),
            "assignment[group_submission]": group_submissions,
        }
        assignment_files = {"template_pdf": template_file_path.open("rb")}
        self.session.post(f"{self.url}/assignments", files=assignment_files, data=assignment_params)

        # Wasteful, but post response does not include new assignment ID
        self._currently_loaded &= ~CourseData.ASSIGNMENTS

    def remove_assignment(
        self,
        *,
        name: str | None = None,
        assignment_id: str | None = None,
        assignment: GSAssignment = None,
        ask_for_confirmation: bool = True,
    ) -> None:
        """Remove the assignment with the given name or ID."""
        self._load_necessary_data(CourseData.ASSIGNMENTS)
        assignment = self._assignments.get_entity(name=name, uid=assignment_id, entity=assignment)
        authenticity_token = get_csrf_token(self)
        if ask_for_confirmation and not click.confirm(
            f"Found assignment:\n{assignment.format()}.\nAre you sure you want to remove?",
            default=False,
        ):
            return
        remove_params = {"_method": "delete", "authenticity_token": authenticity_token}

        self.session.post(f"{self.url}/assignments/{assignment.assignment_id}", data=remove_params)

        self._assignments.remove_entity(entity=assignment)

    def get_assignment(
        self,
        *,
        name: str | None = None,
        assignment_id: str | None = None,
        assignment: GSAssignment = None,
    ) -> GSAssignment:
        """Return the assignment with the given name or ID."""
        self._load_necessary_data(CourseData.ASSIGNMENTS)
        return self._assignments.get_entity(name=name, uid=assignment_id, entity=assignment)

    def get_all_assignments(self) -> list[GSAssignment]:
        """Return all assignments in the course."""
        self._load_necessary_data(CourseData.ASSIGNMENTS)
        return self._assignments.get_all()

    # ~~~~~~~~~~~~~~~~~~~~~~HOUSEKEEPING~~~~~~~~~~~~~~~~~~~~~~~~~

    def _lazy_load_assignments(self) -> None:
        """Load the assignments.

        To do so, request and parse the assignments page.
        This is done lazily to avoid slowdown; often it is not necessary to have both the
        students and assignments loaded.

        """
        assignment_resp = self.session.get(f"{self.url}/assignments")
        parsed_assignment_resp = BeautifulSoup(assignment_resp.text, "html.parser")
        assignment_data = parsed_assignment_resp.findAll(
            "div",
            attrs={"data-react-class": "AssignmentsTable"},
        )
        if len(assignment_data) != 1:
            msg = f"Expected one AssignmentTable but got {len(assignment_data)}"
            raise HTMLParseError(msg)

        assignment_data = json.loads(assignment_data[0].get("data-react-props"))["table_data"]
        for row in assignment_data:
            name = row["title"]
            aid = re.match(r"assignment_(\d+)", row["id"])
            if not aid:
                msg = "Could not parse assignment id"
                raise HTMLParseError(msg)
            aid = aid.group(1)

            points = row["total_points"]
            submissions = row["num_active_submissions"]
            percent_graded = row["grading_progress"]

            release_date = (
                datetime.fromisoformat(row["submission_window"]["release_date"])
                if row["submission_window"]["release_date"]
                else None
            )
            due_date = (
                datetime.fromisoformat(row["submission_window"]["due_date"])
                if row["submission_window"]["due_date"]
                else None
            )
            hard_due_date = (
                datetime.fromisoformat(row["submission_window"]["hard_due_date"])
                if row["submission_window"]["hard_due_date"]
                else due_date
            )
            time_limit = row["submission_window"]["time_limit"]

            regrades_on = row["regrade_requests_possible"]
            self._assignments.add(
                GSAssignment(
                    name=name,
                    assignment_id=aid,
                    points=points,
                    percent_graded=percent_graded,
                    session=self.session,
                    submissions=submissions,
                    regrades_on=regrades_on,
                    release_date=release_date,
                    due_date=due_date,
                    hard_due_date=hard_due_date,
                    time_limit=time_limit,
                    course=self,
                ),
            )
        self._currently_loaded |= CourseData.ASSIGNMENTS

    def _lazy_load_roster(self) -> None:
        """Load the roster list.

        To do so, request and parse the memberships page.
        This is done lazily to avoid slowdown; often it is not necessary to have both the
        students and assignments loaded.

        """
        membership_resp = self.session.get(f"{self.url}/memberships")
        parsed_membership_resp = BeautifulSoup(membership_resp.text, "html.parser")

        roster_table = []
        for student_row in parsed_membership_resp.find_all("tr", class_="rosterRow"):
            found_data = False
            for td in student_row("td"):
                if td.find("button", class_="rosterCell--editIcon"):
                    roster_table.append(td.find("button", class_="rosterCell--editIcon"))
                    found_data = True
                    break
            if not found_data:
                msg = "Could not parse roster data"
                raise HTMLParseError(msg)

        for student_data in roster_table:
            data_cm = json.loads(student_data.get("data-cm"))
            name = data_cm["full_name"]
            sid = data_cm.get("sid", None)
            data_id = student_data.get("data-id")
            email = student_data.get("data-email")

            role = GSRole(int(student_data.get("data-role")))
            self._roster.add(
                GSPerson(
                    name=name,
                    data_id=data_id,
                    sid=sid,
                    email=email,
                    role=role,
                ),
            )
        self._currently_loaded |= CourseData.ROSTER

    def _load_necessary_data(self, needed_data: int) -> None:
        """Check if we have the needed data loaded. If not, load it."""
        need_to_load = needed_data & ~self._currently_loaded
        if need_to_load & CourseData.ROSTER:
            self.update_roster()
        if need_to_load & CourseData.ASSIGNMENTS:
            self.update_assignments()

    def delete(self, ask_for_confirmation: bool = True) -> None:
        """Delete the course.

        This is IRREVERSIBLE.

        Args:
            ask_for_confirmation (bool, optional): Whether to ask for confirmation. Defaults to True.

        """
        if ask_for_confirmation and not click.confirm(
            f"Are you sure you want to delete {self}? \
                This is irreversible and will delete all assignments and submissions:   ",
            default=False,
        ):
            return

        for assignment in self.get_all_assignments():
            self.remove_assignment(assignment=assignment, ask_for_confirmation=False)

        authenticity_token = get_csrf_token(self)
        delete_params = {"_method": "delete", "authenticity_token": authenticity_token}
        self.session.post(
            f"{self.url}",
            data=delete_params,
            headers={
                "referer": f"{self.url}/edit",
                "origin": "https://www.gradescope.com",
            },
        )

    def __str__(self) -> str:
        return f"Course(name='{self.name}', course_id={self.course_id}, year='{self.year}')"

    def __hash__(self) -> int:
        """Return the hash of course entity; the ID is unique, so it can be used."""
        return hash(self.course_id)
