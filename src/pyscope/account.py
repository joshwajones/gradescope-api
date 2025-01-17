from bs4 import BeautifulSoup
import re
import click
from typing import List

from pyscope.course import GSCourse
from pyscope.exceptions import HTMLParseError

class GSAccount():
    """A class designed to track the account details (instructor and student courses"""

    def __init__(self, email, session):
        self.email = email
        self.session = session
        self.instructor_courses = {}
        self.student_courses = {}
        self.courses = {
            True: self.instructor_courses,
            False: self.student_courses
        }

    def add_class(self, course: GSCourse):
        self.courses[course.instructor][course.course_id] = course

    def _delete_class(self, course: GSCourse, ask_for_confirmation: bool = True):
        course.delete(ask_for_confirmation=ask_for_confirmation)
        del self.instructor_courses[course.course_id]
    
    def _find_classes_regex(self, *, course_ids: List[str] = None, course_names: List[str] = None, instructor: bool = None):
        def _check_match(course: GSCourse, course_id: str = None, course_name: str = None, instructor: bool = None):
            is_match = False
            if course_id:
                is_match = is_match or bool(re.match(course_id, course.course_id))
            if course_name:
                is_match = is_match or bool(re.match(course_name, course.name))
            if instructor is not None:
                is_match = is_match and course.instructor == instructor
            return is_match

        matched_courses = []
        if course_ids is None:
            course_ids = []
        if course_names is None:
            course_names = []
        
        identifiers = [{'course_id': course_id} for course_id in course_ids] + [{'course_name': course_name} for course_name in course_names]
        
        all_courses = list(self.instructor_courses.values())
        for course in all_courses:
            for identifier in identifiers:
                if _check_match(course, **identifier):
                    matched_courses.append(course)
        
        return matched_courses
    
    def delete_classes(self, *, course_ids: List[str] = None, course_names: List[str] = None, ask_for_confirmation: bool = True):
        courses_to_delete = self._find_classes_regex(course_ids=course_ids, course_names=course_names, instructor=True)
        for course in courses_to_delete:
            self._delete_class(course, ask_for_confirmation=ask_for_confirmation)
    
    def get_classes(self, *, course_ids: List[str] = None, course_names: List[str] = None, instructor: bool = None):
        return self._find_classes_regex(course_ids=course_ids, course_names=course_names, instructor=instructor)


    def create_course(
        self, 
        name: str, 
        nickname: str, 
        description: str, 
        term: str, 
        year: str, 
        school: str = None, 
        entry_code_enabled: bool = False
    ):
        """Creates a course, and returns the course ID"""
        account_resp = self.session.get("https://www.gradescope.com/account")
        parsed_account_resp = BeautifulSoup(account_resp.text, 'html.parser')

        create_modal = parsed_account_resp.find('dialog', id = 'createCourseModal')
        authenticity_token = create_modal.find('input', attrs = {'name': 'authenticity_token'}).get('value')
        default_school = create_modal.find('input', attrs = {'name': 'course[school_name]'}).get('value')
        if school is not None and default_school != school:
            raise ValueError(f"Default school is {default_school}; course cannot be created for non-default school {school} programmatically. Please contact help@gradescope.com.")
    
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
        course_resp.raise_for_status()
        course_id = re.match(
            'Course ID: ([0-9]+)',
            BeautifulSoup(course_resp.text, 'html.parser').find('div', class_='courseHeader--courseID').text
        )

        if not course_id:
            raise HTMLParseError

        course_id = course_id.group(1)
    
        self.add_class(
            GSCourse(
                name = name,
                nickname = nickname,
                course_id = course_id,
                instructor = True,
                year = f'{term} {year}',
                session = self.session
            )
        )
        return course_id
    
    def __str__(self):
        repr = []
        repr.append(f"Email: {self.email}")
        repr.append(f"Session: {self.session}")
        repr.append(f"Instructor Courses:")
        repr.extend([f"\t{course}" for course in self.instructor_courses.values()])
        repr.append(f"Student Courses:")
        repr.extend([f"\t{course}" for course in self.student_courses.values()])
        return '\n'.join(repr)
        
