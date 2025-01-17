import requests
from bs4 import BeautifulSoup
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Union

from pyscope.question import GSQuestion
from pyscope.pyscope_types import RosterType
from pyscope.extension import GSExtension
from pyscope.person import GSPerson


@dataclass
class GSAssignment(RosterType):
    name: str
    assignment_id: str
    points: int
    percent_graded: float
    submissions: int
    regrades_on: bool
    session: requests.Session
    course: 'GSCourse'

    def __post_init__(self):
        self.questions = []
    
    def unique_id(self) -> str:
        return self.assignment_id

    @property
    def url(self):
        return f'{self.course.url}/assignments/{self.assignment_id}'

    def add_question(self, title, weight, crop = None, content = [], parent_id = None):
        new_q_data = [q.to_patch() for q in self.questions]
        new_crop = crop if crop else [{'x1': 10, 'x2': 91, 'y1': 73, 'y2': 93, 'page_number': 1}]
        new_q = {'title': title, 'weight': weight, 'crop_rect_list': new_crop}
        if parent_id:
            # TODO: This should throw a custom exception if a parent is not found
            parent = [parent for parent in new_q_data if parent['id'] == parent_id][0]
            if parent['children']:
                parent['children'].append(new_q)
            else:
                parent['children'] = [new_q]
        else:
            new_q_data.append(new_q)

        # TODO add id region support
        new_patch = {'assignment': {'identification_regions': {'name': None, 'sid': None}},
                     'question_data': new_q_data}

        outline_resp = self.course.session.get(f'{self.url}/outline/edit')
        parsed_outline_resp = BeautifulSoup(outline_resp.text, 'html.parser')
        authenticity_token = parsed_outline_resp.find('meta', attrs = {'name': 'csrf-token'} ).get('content')

        patch_resp = self.course.session.patch(f'{self.url}/outline/',
                                               headers = {'x-csrf-token': authenticity_token,
                                                          'Content-Type': 'application/json'},
                                               data = json.dumps(new_patch,separators=(',',':')))

        if patch_resp.status_code != requests.codes.ok:
            patch_resp.raise_for_status()

        # TODO this should be done smarter :(
        self.questions = []
        self._lazy_load_questions()

    # TODO allow this to be a predicate remove
    def remove_question(self, title=None, qid=None):
        if not title and not qid:
            return
        new_q_data = [q.to_patch() for q in self.questions]

        # TODO Yes this is slow and ugly, should be improved
        if title: 
            new_q_data = [q for q in new_q_data if q['title'] != title]
            for q in new_q_data:
                if q.get('children'):
                    q['children'] = [sq for sq in q['children'] if sq['title'] != title]
        else:
            new_q_data = [q for q in new_q_data if q['id'] != qid]
            for q in new_q_data:
                if q.get('children'):
                    q['children'] = [sq for sq in q['children'] if sq['id'] != qid]

        new_patch = {'assignment': {'identification_regions': {'name': None, 'sid': None}},
                     'question_data': new_q_data}

        outline_resp = self.course.session.get(f'{self.url}/outline/edit')
        parsed_outline_resp = BeautifulSoup(outline_resp.text, 'html.parser')
        authenticity_token = parsed_outline_resp.find('meta', attrs = {'name': 'csrf-token'} ).get('content')

        patch_resp = self.course.session.patch(f'{self.url}/outline/',
                                               headers = {'x-csrf-token': authenticity_token,
                                                          'Content-Type': 'application/json'},
                                               data = json.dumps(new_patch,separators=(',',':')))

        if patch_resp.status_code != requests.codes.ok:
            patch_resp.raise_for_status()

        # TODO this should be done smarter :(
        self.questions = []
        self._lazy_load_questions()
        
    # TODO INCOMPLETE
    def add_instructor_submission(self, fname):
        """
        Upload a PDF submission.
        """
        submission_resp = self.course.session.get(f'{self.url}/submission_batches')
        parsed_assignment_resp = BeautifulSoup(submission_resp.text, 'html.parser')
        authenticity_token = parsed_assignment_resp.find('meta', attrs = {'name': 'csrf-token'} ).get('content')

        submission_files = {
            "file" : open(fname, 'rb')
        }

        submission_resp = self.course.session.post(f'{self.url}/submission_batches',
                                            files = submission_files,
                                            headers = {'x-csrf-token': authenticity_token})
        
    # TODO
    def publish_grades(self):
        pass

    # TODO
    def unpublish_grades(self):
        pass

    def _lazy_load_questions(self):        
        outline_resp = self.course.session.get(f'{self.url}/outline/edit')
        parsed_outline_resp = BeautifulSoup(outline_resp.text, 'html.parser')

        props = parsed_outline_resp.find('div',
                                         attrs={'data-react-class':'AssignmentOutline'}).get('data-react-props')
        json_props = json.loads(props)
        outline = json_props['outline']

        for question in outline:
            qid = question['id']
            title = question['title']
            parent_id = question['parent_id']
            weight = question['weight']
            content = question['content']
            crop = question['crop_rect_list']
            children = []
            qchildren = question.get('children', [])
            
            for subquestion in qchildren:
                c_qid = subquestion['id']
                c_title = subquestion['title']
                c_parent_id = subquestion['parent_id']
                c_weight = subquestion['weight']
                c_content = subquestion['content']
                c_crop = subquestion['crop_rect_list']
                children.append(GSQuestion(c_qid, c_title, c_weight, [], c_parent_id, c_content, c_crop))
            self.questions.append(GSQuestion(qid, title, weight, children, parent_id, content, crop))
    

    # inspired by https://github.com/cs161-staff/gradescope-api/blob/master/src/gradescope_api/assignment.py
    def _apply_extension(self, extension: GSExtension, revert_to_default_params: bool = False):
        extension_url = f'{self.url}/extensions'
        extension_resp = self.session.get(extension_url)
        parsed_extension_resp = BeautifulSoup(extension_resp.text, 'html.parser')
        props = parsed_extension_resp.find(
            "li", {"data-react-class": "AddExtension"}
        )["data-react-props"]
        data = json.loads(props)
        students = {row["email"]: row["id"] for row in data.get("students", [])}
        student_id = students[extension.student.email] # NOT the same as extension.student.data_id
        authenticity_token = parsed_extension_resp.find(
            'meta', attrs={'name': 'csrf-token'}
        )['content']
        
        def format_date(dt: Union[str, datetime]) -> str:
            if isinstance(dt, str):
                time = dt
            elif isinstance(dt, datetime):
                time = dt.strftime('%Y-%m-%dT%H:%M')
            else:
                raise TypeError
            return {
                'type': 'absolute',
                'value': f'{time}'
            }

        new_settings = {'visible': True}
        if revert_to_default_params:
            new_settings['due_date'] = None
            new_settings['hard_due_date'] = None
            new_settings['release_date'] = None
            new_settings['time_limit'] = None
        else:
            if extension.due_date:
                new_settings['due_date'] = format_date(extension.due_date)
            if extension.late_due_date:
                new_settings['hard_due_date'] = format_date(extension.late_due_date)
            if extension.release_date:
                new_settings['release_date'] = format_date(extension.release_date)
            if extension.time_limit_minutes:
                new_settings['time_limit'] = {
                    'type': 'absolute_minutes',
                    'value': f'{extension.time_limit_minutes}'
                }
        payload = {
            'override': {
                'settings': new_settings,
                'user_id': student_id,
            }
        }
        headers = {'x-csrf-token': authenticity_token,'Content-Type': 'application/json'}
        extension_resp = self.session.post(
            extension_url, headers=headers, data=json.dumps(payload), timeout=20
        )
        extension_resp.raise_for_status()
    
    def apply_extension(self, extension: GSExtension):
        self._apply_extension(extension)

    def remove_extension(self, student: GSPerson):
        self._apply_extension(GSExtension(student=student), revert_to_default_params=True)

    def format(self, prefix='\t'):
        return f"{prefix}Name: {self.name}\n{prefix}ID: {self.assignment_id}"
            
        
