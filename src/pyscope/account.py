import re

from bs4 import BeautifulSoup

from pyscope.course import GSCourse
from pyscope.exceptions import HTMLParseError
from pyscope.pyscope_types import CourseInfo


class GSAccount:
    """Class to represent a Gradescope account, primarily tracking courses."""

    def __init__(self, email: str, session: str) -> None:
        self.email = email
        self.session = session
        self.instructor_courses = {}
        self.student_courses = {}
        self.courses = {True: self.instructor_courses, False: self.student_courses}

    def _add_class(self, course: GSCourse, is_instructor: bool) -> None:
        self.courses[is_instructor][course.course_id] = course

    def add_class(self, course: GSCourse, is_instructor: bool) -> None:
        """Add a course to the account."""
        self._add_class(course, is_instructor)

    def add_classes(self, course_infos: list[CourseInfo]) -> None:
        """Add multiple courses at once."""
        for course_info in course_infos:
            self._add_class(course_info["course"], course_info["is_instructor"])

    def _delete_class(self, course: GSCourse, ask_for_confirmation: bool = True) -> None:
        course.delete(ask_for_confirmation=ask_for_confirmation)
        del self.instructor_courses[course.course_id]

    def _find_classes_regex(
        self,
        *,
        course_ids: list[str] | None = None,
        course_names: list[str] | None = None,
        instructor: bool | None = None,
    ) -> list[GSCourse]:
        def _check_match(
            course: GSCourse,
            course_id: str | None = None,
            course_name: str | None = None,
            instructor: bool | None = None,
        ) -> bool:
            is_match = False
            if course_id:
                is_match = is_match or bool(re.match(course_id, course.course_id))
            if course_name:
                is_match = is_match or bool(re.match(course_name, course.name))
            if instructor is not None:
                is_match = is_match and course.instructor == instructor
            return is_match

        if course_ids is None:
            course_ids = []
        if course_names is None:
            course_names = []

        identifiers = [{"course_id": course_id} for course_id in course_ids] + [
            {"course_name": course_name} for course_name in course_names
        ]

        if instructor is not None:
            all_courses = list(self.courses[instructor].values())
        else:
            all_courses = list(self.instructor_courses.values()) + list(
                self.student_courses.values(),
            )

        return list(
            {course for course in all_courses for identifier in identifiers if _check_match(course, **identifier)},
        )

    def delete_classes(
        self,
        *,
        course_ids: list[str] | None = None,
        course_names: list[str] | None = None,
        ask_for_confirmation: bool = True,
    ) -> None:
        """Delete courses matching the specified criteria.

        Args:
            course_ids (list[str] | None, optional): A list of course IDs to match. Defaults to None.
            course_names (list[str] | None, optional): A list of course names to match. Defaults to None.
            ask_for_confirmation (bool, optional): Whether to ask for confirmation before deleting each course.

        """
        courses_to_delete = self._find_classes_regex(
            course_ids=course_ids,
            course_names=course_names,
            instructor=True,
        )
        for course in courses_to_delete:
            self._delete_class(course, ask_for_confirmation=ask_for_confirmation)

    def get_classes(
        self,
        *,
        course_ids: list[str] | None = None,
        course_names: list[str] | None = None,
        instructor: bool | None = None,
    ) -> list[GSCourse]:
        """Get a list of courses matching the specified criteria.

        Args:
            course_ids (list[str] | None, optional): A list of course IDs to match. Defaults to None.
            course_names (list[str] | None, optional): A list of course names to match. Defaults to None.
            instructor (bool | None, optional): If non-None, filters by whether the course is an instructor course.

        Returns:
            list[GSCourse]: A list of courses that match any of the specified criteria.

        """
        return self._find_classes_regex(
            course_ids=course_ids,
            course_names=course_names,
            instructor=instructor,
        )

    def create_course(
        self,
        name: str,
        nickname: str,
        description: str,
        term: str,
        year: str,
        school: str | None = None,
        entry_code_enabled: bool = False,
    ) -> str:
        """Create a course, and returns the course ID."""
        account_resp = self.session.get("https://www.gradescope.com/account")
        parsed_account_resp = BeautifulSoup(account_resp.text, "html.parser")

        create_modal = parsed_account_resp.find("dialog", id="createCourseModal")
        authenticity_token = create_modal.find("input", attrs={"name": "authenticity_token"}).get(
            "value",
        )
        default_school = create_modal.find("input", attrs={"name": "course[school_name]"}).get(
            "value",
        )
        if school is not None and default_school != school:
            msg = (
                f"Default school is {default_school}; course cannot be created for non-"
                f"default school {school} programmatically. Please contact help@gradescope.com."
            )
            raise ValueError(
                msg,
            )

        course_data = {
            "utf8": "✓",
            "authenticity_token": authenticity_token,
            "course[shortname]": nickname,
            "course[name]": name,
            "course[description]": description,
            "course[term]": term,
            "course[year]": year,
            "course[school_id]": "1",
            "course[school_name]": default_school,
            "course[entry_code_enabled]": 1 if entry_code_enabled else 0,
            "commit": "Create Course",
        }

        course_resp = self.session.post("https://www.gradescope.com/courses", params=course_data)
        course_id = re.match(
            "Course ID: ([0-9]+)",
            BeautifulSoup(course_resp.text, "html.parser").find("div", class_="courseHeader--courseID").text,
        )

        if not course_id:
            raise HTMLParseError

        course_id = course_id.group(1)

        self.add_class(
            GSCourse(
                name=name,
                nickname=nickname,
                course_id=course_id,
                year=f"{term} {year}",
                session=self.session,
            ),
            is_instructor=True,
        )
        return course_id

    def __str__(self) -> str:
        string = []
        string.append(f"Email: {self.email}")
        string.append(f"Session: {self.session}")
        string.append("Instructor Courses:")
        string.extend([f"\t{course}" for course in self.instructor_courses.values()])
        string.append("Student Courses:")
        string.extend([f"\t{course}" for course in self.student_courses.values()])
        return "\n".join(string)
