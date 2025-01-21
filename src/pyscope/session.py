import requests
from bs4 import BeautifulSoup

from pyscope.account import GSAccount
from pyscope.course import GSCourse
from pyscope.pyscope_types import ConnState, CourseSplit
from pyscope.exceptions import UninitializedAccountError
from pyscope.utils import SafeSession

class GSConnection:
    """Tracks the current session/connection to Gradescope."""

    def __init__(self):
        self.session = SafeSession()
        self.state = ConnState.INIT
        self.account = None

    def login(self, email: str, pswd: str) -> bool:
        login_success = False
        init_resp = self.session.get("https://www.gradescope.com/")
        parsed_init_resp = BeautifulSoup(init_resp.text, 'html.parser')
        for form in parsed_init_resp.find_all('form'):
            if form.get("action") == "/login":
                for inp in form.find_all('input'):
                    if inp.get('name') == "authenticity_token":
                        auth_token = inp.get('value')

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

    def load_courses(self, split: CourseSplit = CourseSplit.ALL):
        account_resp = self.session.get("https://www.gradescope.com/account")
        parsed_account_resp = BeautifulSoup(account_resp.text, 'html.parser')

        def _parse_courses(course_list: list, instructor: bool):
            parsed_courses = []
            for course in course_list:
                year = None
                for tag in course.parent.previous_siblings:
                    if 'courseList--term' in tag.get("class"):
                        year = tag.string
                        break
                parsed_courses.append(
                    GSCourse(
                        name = course.find('div', class_ = 'courseBox--name').text,
                        nickname = course.find('h3', class_ = 'courseBox--shortname').text,
                        course_id = course.get("href").split("/")[-1],
                        instructor = instructor,
                        year = year,
                        session = self.session
                    )
                )
            return parsed_courses

        course_list = []
        if split == CourseSplit.INSTRUCTOR or split == CourseSplit.ALL:
            course_list += _parse_courses(
                parsed_account_resp.find('h1', class_ = 'pageHeading').next_sibling.find_all('a', class_ = 'courseBox'), instructor=True
            )
        if split == CourseSplit.STUDENT or split == CourseSplit.ALL:
            course_list += _parse_courses(
                parsed_account_resp.find('h1', class_ = 'pageHeading', string = "Student Courses").next_sibling.find_all('a', class_ = 'courseBox'), instructor=False
            )
        return course_list


    def load_account_data(self):
        if self.state != ConnState.LOGGED_IN:
            raise UninitializedAccountError
        self.account.add_classes(self.load_courses())
