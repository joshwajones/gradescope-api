from enum import Enum
from bs4 import BeautifulSoup
from dataclasses import dataclass
import requests
from typing import Union, Optional
import click
from datetime import datetime
import json
import re

from pyscope.person import GSPerson, GSRole
from pyscope.roster import Roster
from pyscope.assignment import GSAssignment
from pyscope.exceptions import HTMLParseError
from pyscope.pyscope_types import CourseData, SubmissionType
from pyscope.utils import get_csrf_token


@dataclass
class GSCourse():
    course_id: str
    name: str
    nickname: str
    instructor: bool
    session: requests.Session
    year: Union[int, None]

    def __post_init__(self):
        self.roster = Roster()
        self.assignments = Roster()
        self._currently_loaded = 0
    
    @property
    def url(self):
        return f'https://www.gradescope.com/courses/{self.course_id}'
        
    def update_roster(self):
        self.roster.clear()
        self._lazy_load_roster()
    
    def update_assignments(self):
        self.assignments.clear()
        self._lazy_load_assignments()
    # ~~~~~~~~~~~~~~~~~~~~~~PEOPLE~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def add_person(
        self, 
        name: str, 
        email: str, 
        role: GSRole, 
        sid: Optional[str] = None, 
        notify: bool = False
    ):
        self._load_necessary_data(CourseData.ROSTER)

        authenticity_token = get_csrf_token(self)
        person_params = {
            "utf8": "✓",
            "user[name]" : name,
            "user[email]" : email,
            "user[sid]" : "" if sid is None else sid, 
            "course_membership[role]" : role.value,
            "button" : ""
        }
        if notify:
            person_params['notify_by_email'] = 1

        self.session.post(
            f'{self.url}/memberships',
            data = person_params,
            headers = {'x-csrf-token': authenticity_token}
        )

        # Wasteful, but post response does not include new person's data id
        self._currently_loaded &= ~CourseData.ROSTER

    def remove_person(self, *, name: str = None, email: str = None, person: GSPerson = None, ask_for_confirmation: bool = True):
        self._load_necessary_data(CourseData.ROSTER)
        
        authenticity_token = get_csrf_token(self)
        remove_params = {
            "_method" : "delete",
            "authenticity_token" : authenticity_token
        }
        person = self.roster.get_entity(name=name, uid=email, entity=person, raise_error=False)
        if ask_for_confirmation:
            if not click.confirm(f"Found person:\n{person.format()}.\nAre you sure you want to remove?", default=False):
                return

        self.session.post(
            f'https://www.gradescope.com/courses/{self.course_id}/memberships/{person.data_id}',
            data = remove_params,
            headers = {'x-csrf-token': authenticity_token}
        )
        self.roster.remove_entity(entity=person)

    def change_person_role(self, *, name: str = None, email: str = None, person: GSPerson = None, new_role: GSRole):
        self._load_necessary_data(CourseData.ROSTER)
        authenticity_token = get_csrf_token(self)
        role_params = {
            "course_membership[role]" : new_role.value,
        }
        person = self.roster.get_entity(name=name, uid=email, entity=person)

        self.session.patch(f'{self.url}/memberships/{person.data_id}/update_role',
            data = role_params,
            headers = {'x-csrf-token': authenticity_token}
        )
        person.role = new_role

    def get_person(self, *, name: str = None, email: str = None, person: GSPerson = None):
        self._load_necessary_data(CourseData.ROSTER)
        return self.roster.get_entity(name=name, uid=email, entity=person, raise_error=False)

    # ~~~~~~~~~~~~~~~~~~~~~~ASSIGNMENTS~~~~~~~~~~~~~~~~~~~~~~~~~~

    def add_assignment(
        self,
        name: str,
        release: datetime,
        due: datetime,
        template_file_path: str,
        submission_type: SubmissionType = SubmissionType.PDF,
        student_submissions: bool = True,
        late_submissions: bool = False,
        group_submissions: int = 0
    ):
        self._load_necessary_data(CourseData.ASSIGNMENTS)
        authenticity_token = get_csrf_token(self)

        assignment_params = {
            "authenticity_token" : authenticity_token,
            "assignment[title]" : name,
            "assignment[student_submission]" : student_submissions,
            "assignment[release_date_string]" : release,
            "assignment[due_date_string]" : due,
            "assignment[allow_late_submissions]" : int(late_submissions),
            "assignment[submission_type]" : str(submission_type),
            "assignment[group_submission]" : group_submissions,
        }
        assignment_files = {
            "template_pdf" : open(template_file_path, 'rb')
        }
        self.session.post(f'{self.url}/assignments',
                                            files = assignment_files,
                                            data = assignment_params)

        # Wasteful, but post response does not include new assignment ID
        self._currently_loaded &= ~CourseData.ASSIGNMENTS
        
    def remove_assignment(self, *, name: str = None, assignment_id: str = None, assignment: GSAssignment = None, ask_for_confirmation: bool = True):
        self._load_necessary_data(CourseData.ASSIGNMENTS)
        assignment = self.assignments.get_entity(name=name, uid=assignment_id, entity=assignment)
        authenticity_token = get_csrf_token(self)
        if ask_for_confirmation:
            if not click.confirm(f"Found assignment:\n{assignment.format()}.\nAre you sure you want to remove?", default=False):
                return
        remove_params = {
            "_method" : "delete",
            "authenticity_token" : authenticity_token
        }

        self.session.post(
            f'{self.url}/assignments/{assignment.assignment_id}',
            data = remove_params
        )

        self.assignments.remove_entity(name=name) 
    
    def get_assignment(self, *, name: str = None, assignment_id: str = None, assignment: GSAssignment = None):
        self._load_necessary_data(CourseData.ASSIGNMENTS)
        return self.assignments.get_entity(name=name, uid=assignment_id, entity=assignment)

    # ~~~~~~~~~~~~~~~~~~~~~~HOUSEKEEPING~~~~~~~~~~~~~~~~~~~~~~~~~

    def _lazy_load_assignments(self):
        """
        Load the assignment dictionary from assignments. This is done lazily to avoid slowdown caused by getting
        all the assignments for all classes. Also makes us less vulnerable to blocking.
        """
        assignment_resp = self.session.get(f'{self.url}/assignments')
        parsed_assignment_resp = BeautifulSoup(assignment_resp.text, 'html.parser')
        assignment_data = parsed_assignment_resp.findAll(
            'div', attrs={'data-react-class': 'AssignmentsTable'}
        )
        if len(assignment_data) != 1:
            raise HTMLParseError(f"Expected one AssignmentTable but got {len(assignment_data)}")
        
        assignment_data = json.loads(assignment_data[0].get('data-react-props'))['table_data']
        for row in assignment_data:
            name = row['title']
            aid = re.match(
                "assignment_(\d+)",
                row['id']
            )
            if not aid:
                raise HTMLParseError("Could not parse assignment id")
            aid = aid.group(1)

            points = row['total_points']
            submissions = row['num_active_submissions']
            percent_graded = row['grading_progress']

            regrades_on  = row['regrade_requests_possible']
            self.assignments.add(
                GSAssignment(
                    name=name, assignment_id=aid, points=points, percent_graded=percent_graded, session=self.session, submissions=submissions, regrades_on=regrades_on, course=self
                )
            )
        self._currently_loaded |= CourseData.ASSIGNMENTS
        

    def _lazy_load_roster(self):
        """
        Load the roster list  This is done lazily to avoid slowdown caused by getting
        all the rosters for all classes. Also makes us less vulnerable to blocking.
        """
        membership_resp = self.session.get(f'{self.url}/memberships')
        parsed_membership_resp = BeautifulSoup(membership_resp.text, 'html.parser')

        roster_table = []
        for student_row in parsed_membership_resp.find_all('tr', class_ = 'rosterRow'):
            found_data = False
            for td in student_row('td'):
                if td.find('button', class_ = 'rosterCell--editIcon'):
                    roster_table.append(td.find('button', class_ = 'rosterCell--editIcon'))
                    found_data = True
                    break
            if not found_data:
                raise HTMLParseError("Could not parse roster data")
        
        for student_data in roster_table:
            data_cm = json.loads(student_data.get('data-cm'))
            name = data_cm['full_name']
            sid = data_cm.get('sid', None)
            data_id = student_data.get('data-id')
            email = student_data.get('data-email')

            role = GSRole(int(student_data.get('data-role')))
            self.roster.add(GSPerson(
                name=name,
                data_id=data_id,
                sid=sid,
                email=email,
                role=role,
            ))
        self._currently_loaded |= CourseData.ROSTER
        
    def _load_necessary_data(self, needed_data: int):
        """
        checks if we have the needed data loaded and gets them lazily.
        """
        need_to_load = needed_data & ~self._currently_loaded
        if need_to_load & CourseData.ROSTER:
            self.update_roster()
        if need_to_load & CourseData.ASSIGNMENTS:
            self.update_assignments()

    def delete(self, ask_for_confirmation: bool = True):
        if ask_for_confirmation:
            if not click.confirm(f"Are you sure you want to delete {self}?", default=False):
                return
        authenticity_token = get_csrf_token(self)
        delete_params = {
            "_method": "delete",
            "authenticity_token": authenticity_token
        }
        self.session.post(
            f'{self.url}',
            data = delete_params,
            headers={
                'referer': f'{self.url}/edit',
                'origin': 'https://www.gradescope.com'
            }
        )
    
    def __str__(self):
        return f"Course(name='{self.name}', course_id={self.course_id}, year='{self.year}')"
