import requests
from bs4 import BeautifulSoup
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Union
import re
import time
import logging

from pyscope.question import GSQuestion
from pyscope.pyscope_types import RosterType, QuestionType
from pyscope.extension import GSExtension
from pyscope.person import GSPerson
from pyscope.roster import Roster
from pyscope.utils import get_csrf_token, stream_file


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
        self.questions = Roster()
        self._loaded_questions = False
    
    def get_name(self):
        return self.name
    
    def get_unique_id(self) -> str:
        return self.assignment_id

    @property
    def url(self):
        return f'{self.course.url}/assignments/{self.assignment_id}'

    def serialize_questions(self):
        return self.root.serialize()
    
    def _find_question_parent(self, parent_id):
        self._load_questions_if_needed()
        def _find_recursive(curr_q: GSQuestion, parent_id: str):
            if curr_q.question_id == parent_id:
                return curr_q
            if curr_q.children:
                for child in curr_q.children:
                    found = _find_recursive(child, parent_id)
                    if found:
                        return found
            return None
        return _find_recursive(self.root, parent_id)
    
    def get_question(self, *, question_id: str = None, title: str = None, question: GSQuestion = None):
        self._load_questions_if_needed()
        return self.questions.get_entity(uid=question_id, name=title, entity=question)
    
    def add_question(self, title, weight, crop = None, content = [], parent_id = None):
        self._load_questions_if_needed()

        new_crop = crop if crop else GSQuestion.default_crop()

        parent = self._find_question_parent(parent_id)
        if not parent:
            raise ValueError(f"Could not find parent question with id {parent_id}")
        if not parent.children:
            parent.children = []
        
        new_question = GSQuestion(
            question_id = None,
            title = title,
            weight = weight,
            children = [],
            type = None,
            parent_id=parent_id,
            crop=new_crop,
            content = content
        )
        parent.children.append(new_question)
        self.questions.add(new_question)

        root = self.serialize_questions()
        new_patch = {'assignment': {'identification_regions': {'name': None, 'sid': None}},
                     'question_data': root['children']}


        authenticity_token = get_csrf_token(self.course)

        self.session.patch(
            f'{self.url}/outline/',
            headers = {'x-csrf-token': authenticity_token,
                       'Content-Type': 'application/json'},
            data = json.dumps(new_patch,separators=(',',':'))
        )                      
        
        # Wastful, but response does not include the new question ID
        self._loaded_questions = False

    def remove_question(self, *, question_id: str = None, title: str = None, question: GSQuestion = None):
        self._load_questions_if_needed()
        question = self.get_question(question_id=question_id, title=title, question=question)

        parent = self._find_question_parent(question.parent_id)
        if not parent:
            raise ValueError(f"Could not find parent question with id {question.parent_id}")
        parent.children = [q for q in parent.children if q.question_id != question.question_id]
        root = self.serialize_questions()

        new_patch = {'assignment': {'identification_regions': {'name': None, 'sid': None}},
                     'question_data': root['children']}

        authenticity_token = get_csrf_token(self.course)
        self.session.patch(f'{self.url}/outline/',
                                               headers = {'x-csrf-token': authenticity_token,
                                                          'Content-Type': 'application/json'},
                                               data = json.dumps(new_patch,separators=(',',':')))

        self.questions.remove_entity(entity=question)
    
    def _match_questions_regex(self, *, question_ids: list[str] = None, question_titles: list[str] = None):
        def _check_match(question: GSQuestion, question_id: str = None, question_title: str = None):
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
        
        identifiers = [{'question_id': question_id} for question_id in question_ids] \
            + [{'question_title': question_title} for question_title in question_titles]
        
        all_questions = self.questions.get_all()
        for question in all_questions:
            for identifier in identifiers:
                if _check_match(question, **identifier):
                    matched_questions.append(question)
        
        return matched_questions
    
    def remove_questions(self, *, question_ids: list[str] = None, question_titles: list[str] = None, questions: list[GSQuestion] = None):
        self._load_questions_if_needed()
        if questions is None:
            questions = []
        matched_questions = set(self._match_questions_regex(question_ids=question_ids, question_titles=question_titles))
        matched_questions |= set(questions)
        for question in matched_questions:
            self.remove_question(question=question)
    
    def add_instructor_submission(self, fname):
        """
        Upload a PDF submission.
        """
        authenticity_token = get_csrf_token(self.course)

        submission_files = {"file" : open(fname, 'rb')}

        self.session.post(
            f'{self.url}/submission_batches',
            files = submission_files,
            headers = {'x-csrf-token': authenticity_token}
        )
        
    def _change_publish_status(self, published: bool):
        authenticity_token = get_csrf_token(self.course)
        data = {"assignment[published]": "true" if published else "false"}
        self.session.patch(
            self.url,
            data=data,
            headers={'x-csrf-token': authenticity_token}
        )

    def publish_grades(self):
        self._change_publish_status(published=True)

    def unpublish_grades(self):
        self._change_publish_status(published=False)

    def export_evaluations(self, fname: str = None):
        data = self.session.get(f'{self.url}/export_evaluations').content
        if fname: 
            with open(fname, 'wb') as f:
                f.write(data)
        return data
    
    def download_grades(self, fname: str):
        response = self.session.get(f'{self.url}/scores.csv')
        if fname:
            if not fname.endswith('.csv'):
                fname += '.csv'
            with open(fname, 'w') as f:
                f.write(response.text)
        return response.text

    def download_submissions(
        self, 
        fname: str = None, 
        unzip: bool = True, 
        timeout: float = float('inf'), 
        sleep_time: float = 1, 
        chunk_size: int = 8192,
        show_bar: bool = True,
    ):
        def _get_default_fname():
            if unzip:
                return './'
            else:
                return './submissions.zip'
        if fname is None:
            fname = _get_default_fname()

        logging.debug('Starting export...')

        response = self.session.head(f'{self.url}/export')

        pattern = re.escape(f'{self.course.url}/generated_files/') + '([0-9]+)\.zip'
        def _finished_exporting(most_recent_response):
            return re.match(pattern, most_recent_response.headers['Location'])
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            if _finished_exporting(response):
                break
            time.sleep(sleep_time)
            response = self.session.head(f'{self.url}/export')

        if not _finished_exporting(response):
            raise TimeoutError("Timed out waiting for export to finish")
        logging.debug(f'Export finished in {time.time() - start_time} seconds. Beginning download...')
        download_start_time = time.time()
        stream_file(
            self.session,
            f'{self.url}/export',
            fname,
            chunk_size=chunk_size,
            unzip=unzip,
            show_bar=show_bar,
        )
        download_end_time = time.time()
        logging.debug(f'Downloaded in {download_end_time - download_start_time} seconds.')
        

    def _load_questions_if_needed(self):
        if not self._loaded_questions:
            self._lazy_load_questions()

    def _lazy_load_questions(self):
        self.questions.clear()       
        outline_resp = self.session.get(f'{self.url}/outline/edit')
        parsed_outline_resp = BeautifulSoup(outline_resp.text, 'html.parser')

        props = parsed_outline_resp.find('div',
                                         attrs={'data-react-class':'AssignmentOutline'}).get('data-react-props')
        json_props = json.loads(props)
        outline = json_props['outline']
        def _parse_recursive(outline):
            question = GSQuestion(
                question_id=outline['id'],
                title=outline['title'],
                weight=outline['weight'],
                type=QuestionType.str_to_enum(outline['type']),
                children=[],
                parent_id=outline['parent_id'],
                content=outline['content'],
                crop=outline['crop_rect_list']
            )
            for child in outline.get('children', []):
                question.children.append(_parse_recursive(child))
            self.questions.add(question)
            return question
        all_questions = [_parse_recursive(q) for q in outline]
        self.root = GSQuestion.create_root(all_questions)
        self._loaded_questions = True
    

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
        headers = {'x-csrf-token': authenticity_token, 'Content-Type': 'application/json'}
        self.session.post(
            extension_url, headers=headers, data=json.dumps(payload), timeout=20
        )
    
    def apply_extension(self, extension: GSExtension):
        self._apply_extension(extension)

    def remove_extension(self, student: GSPerson):
        self._apply_extension(GSExtension(student=student), revert_to_default_params=True)

    def format(self, prefix='\t'):
        return f"{prefix}Name: {self.name}\n{prefix}ID: {self.assignment_id}"
