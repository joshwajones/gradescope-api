import requests
from bs4 import BeautifulSoup

from pyscope.account import GSAccount
from pyscope.course import GSCourse
from pyscope.exceptions import UninitializedAccountError
from pyscope.pyscope_types import ConnState, CourseInfo, CourseSplit
from pyscope.utils import SafeSession


class GSConnection:
    """Tracks the current session/connection to Gradescope."""

    def __init__(self) -> None:
        self.session = SafeSession()
        self.state = ConnState.INIT
        self.account = None

    def _login(self, email: str, pswd: str) -> bool:
        login_success = False
        init_resp = self.session.get("https://www.gradescope.com/")
        parsed_init_resp = BeautifulSoup(init_resp.text, "html.parser")
        for form in parsed_init_resp.find_all("form"):
            if form.get("action") == "/login":
                for inp in form.find_all("input"):
                    if inp.get("name") == "authenticity_token":
                        auth_token = inp.get("value")

        login_data = {
            "utf8": "✓",
            "session[email]": email,
            "session[password]": pswd,
            "session[remember_me]": 0,
            "commit": "Log In",
            "session[remember_me_sso]": 0,
            "authenticity_token": auth_token,
        }
        login_resp = self.session.post("https://www.gradescope.com/login", params=login_data)
        if len(login_resp.history) and login_resp.history[0].status_code == requests.codes.found:
            self.state = ConnState.LOGGED_IN
            self.account = GSAccount(email, self.session)
            login_success = True

        return login_success

    def _load_courses(self, split: CourseSplit = CourseSplit.ALL) -> list[CourseInfo]:
        account_resp = self.session.get("https://www.gradescope.com/account")
        parsed_account_resp = BeautifulSoup(account_resp.text, "html.parser")

        def _parse_courses(course_list: list, instructor: bool) -> list[CourseInfo]:
            parsed_courses = []
            for course in course_list:
                year = None
                for tag in course.parent.previous_siblings:
                    if "courseList--term" in tag.get("class"):
                        year = tag.string
                        break
                parsed_courses.append(
                    GSCourse(
                        name=course.find("div", class_="courseBox--name").text,
                        nickname=course.find("h3", class_="courseBox--shortname").text,
                        course_id=course.get("href").split("/")[-1],
                        year=year,
                        session=self.session,
                    ),
                )
            return [{"course": course, "is_instructor": instructor} for course in parsed_courses]

        course_list = []
        if split in (CourseSplit.INSTRUCTOR, CourseSplit.ALL):
            course_list += _parse_courses(
                parsed_account_resp.find("h1", class_="pageHeading").next_sibling.find_all(
                    "a",
                    class_="courseBox",
                ),
                instructor=True,
            )
        if split in (CourseSplit.STUDENT, CourseSplit.ALL):
            course_list += _parse_courses(
                parsed_account_resp.find(
                    "h2",
                    class_="pageHeading",
                    string="Student Courses",
                ).next_sibling.find_all("a", class_="courseBox"),
                instructor=False,
            )
        return course_list

    def _load_account_data(self) -> None:
        if self.state != ConnState.LOGGED_IN:
            raise UninitializedAccountError
        self.account.add_classes(self._load_courses())

    def login(self, email: str, password: str) -> bool:
        """Login to Gradescope and initialize the account.

        Args:
            email (str): The email of the account.
            password (str): The password of the account.

        Returns:
            bool: Whether the login was successful.

        """
        login_success = self._login(email, password)
        if login_success:
            self._load_account_data()
        return login_success

    @classmethod
    def get_course(
        cls,
        email: str,
        password: str,
        course_id: str,
        instructor: bool | None = None,
    ) -> GSCourse:
        """Get a GSCourse object for a GradeScope course.

        A convenience method that logs in, loads the account, and finds the course.

        Args:
            email (str): The email of the GradeScope account.
            password (str): The password of the GradeScope account.
            course_id (str): The ID of the course.
            instructor (bool or None): if not None, filters the course by whether the account is in instructor/student.

        Returns:
            GSCourse: The course object.

        """
        conn = cls()
        conn.login(email, password)
        matched_courses = conn.account.get_classes(course_ids=[course_id], instructor=instructor)
        if len(matched_courses) != 1:
            msg = f"Found {len(matched_courses)} courses with id {course_id}; expected 1."
            raise ValueError(
                msg,
            )
        return matched_courses[0]
