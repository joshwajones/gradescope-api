import requests
from bs4 import BeautifulSoup
from enum import Enum
import datetime

from pyscope.account import GSAccount
from pyscope.course import GSCourse
from pyscope.utils import ConnState, CourseSplit
from pyscope.exceptions import UninitializedAccountError
from pyscope.person import GSRole

class GSConnection():
    """The main connection class that keeps state about the current connection."""
        
    def __init__(self):
        """Initialize the session for the connection."""
        self.session = requests.Session()
        self.state = ConnState.INIT
        self.account = None

    def login(self, email, pswd):
        """
        Login to gradescope using email and password.
        Note that the future commands depend on account privilages.
        """
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

    def get_courses(self, split: CourseSplit = CourseSplit.ALL):
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


    def get_account(self):
        """
        Gets and parses account data after login. Note will return false if we are not in a logged in state, but 
        this is subject to change.
        """
        if self.state != ConnState.LOGGED_IN:
            raise UninitializedAccountError
        
        all_courses = self.get_courses()
        for course in all_courses:
            self.account.add_class(course)
