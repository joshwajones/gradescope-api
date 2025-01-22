from datetime import datetime
import os
import logging

from pyscope.session import GSConnection
from pyscope.account import GSAccount
from pyscope.course import GSCourse, GSPerson, GSRole
from pyscope.assignment import GSAssignment
from pyscope.extension import GSExtension

from private_config import email, password

def create_test_course(conn: GSConnection) -> GSAssignment:
    account = conn.account

    # delete any existing test courses 
    # account.delete_classes(
    #     course_names=["Test Course"],
    #     ask_for_confirmation=True
    # )
    account.delete_classes(
        course_ids=["957713"],
    )
    breakpoint()

    account.create_course(
        name = "Test Course",
        nickname = "test",
        description = "Dummy course for testing",
        term = "Spring",
        year = "2026",
        entry_code_enabled = False
    )
    matched_courses = account.get_classes(course_names=["Test Course"], instructor=True)
    assert len(matched_courses) == 1

    course: GSCourse = matched_courses[0]
    course.update_roster()

    course.add_person(
        name="Test Person 1",
        email="test1@gmail.com",
        role=GSRole.STUDENT,
        notify=True,
    )
    course.change_person_role(name="Test Person 1", new_role=GSRole.READER)

    course.add_person(
        name="Test Person 2",
        email="test2@gmail.com",
        role=GSRole.INSTRUCTOR,
        sid="123456789",
        notify=False,
    )
    course.change_person_role(name="Test Person 2", new_role=GSRole.STUDENT)

    course.add_person(
        name = "Test Person 3",
        email = "test3@gmail.com",
        role = GSRole.STUDENT,
        notify = False,
    )

    course.add_person(
        name="Test Person 4",
        email="test4@gmail.com",
        role=GSRole.INSTRUCTOR,
        notify=False,
    )

    all_people = course.get_all_people()
    assert len(all_people) == 5
    
    name_to_person = {person.name: person for person in all_people}
    assert name_to_person["Test Person 1"].role == GSRole.READER
    assert name_to_person["Test Person 2"].role == GSRole.STUDENT
    assert name_to_person["Test Person 3"].role == GSRole.STUDENT
    assert name_to_person["Test Person 4"].role == GSRole.INSTRUCTOR

    course.remove_person(name="Test Person 3", ask_for_confirmation=False)
    course.remove_person(name="Test Person 4", ask_for_confirmation=True)

    all_people = course.get_all_people()
    assert len(all_people) == 3
    name_to_person = {person.name: person for person in all_people}
    assert {"Test Person 1", "Test Person 2"} <= set(name_to_person.keys())

    return course


def create_test_assignment(course: GSCourse) -> GSAssignment: 
    test_file_path = os.path.join(os.path.dirname(__file__), "test_pdf.pdf")
    course.add_assignment(
        name="Test Assignment",
        release=datetime.fromisoformat("2022-01-01T00:00"),
        due=datetime.fromisoformat("2022-01-02T00:40"),
        template_file_path=test_file_path,
    )
    course.add_assignment(
        name="Test Assignment 2",
        release=datetime.fromisoformat("2022-03-02T00:00-08:00"),
        due=datetime.fromisoformat("2022-01-01T00:00"),
        template_file_path=test_file_path,
    )
    course.add_assignment(
        name="Test Assignment 3",
        release=datetime.fromisoformat("2022-01-01T00:00"),
        due=datetime.fromisoformat("2022-01-01T00:00"),
        template_file_path=test_file_path,
    )
    course.update_assignments()
    course.remove_assignment(name="Test Assignment 3", ask_for_confirmation=False)
    course.update_assignments()

    assert len(course.assignments) == 2
    
    assignments = course.get_all_assignments()
    assert len(assignments) == 2
    assignments = sorted(assignments, key=lambda x: x.name)
    assert assignments[0].name == "Test Assignment"
    assert assignments[1].name == "Test Assignment 2"
    # breakpoint()
    

    extension = GSExtension(
        student = course.get_person(name="Test Person 1"),
        release_date = datetime.datetime.now(),
        due_date = datetime.datetime.now(),
        late_due_date = datetime.datetime.now(),
        time_limit_minutes = 10,

        # release_delta = datetime.timedelta(days=1),
        # due_delta = datetime.timedelta(days=1),
        # late_due_delta = datetime.timedelta(days=10),
        # limit_multipler = 2
    )

    asn: GSAssignment = course.get_assignment(name="Test Assignment 2")
    asn.apply_extension(extension)
    asn.remove_extension(course.get_person(name="test_student2"))

    asn = course.get_assignment(name="Test Assignment")
    asn.apply_extension(extension)

    extension = GSExtension(
        student = course.get_person(name="Test Person 2"),
        release_date = datetime.datetime.now(),
        due_date = datetime.datetime.now(),
        late_due_date = datetime.datetime.now(),
        time_limit_minutes = 10,

        # release_delta = datetime.timedelta(days=1),
        # due_delta = datetime.timedelta(days=1),
        # late_due_delta = datetime.timedelta(days=10),
        # limit_multipler = 2
    )
    asn.apply_extension(extension)
    return asn

def add_questions(conn: GSConnection, asn: GSAssignment):
    for i in range(5):
        asn.add_question(
            title=f"Test Question {i}",
            weight=100,
        )
    assert len(asn.questions) == 5
    for i in range(5):
        asn.add_question(
            title=f"Test Question 5",
            weight=100,
        )
    assert len(asn.questions) == 10
    asn.remove_questions(question_titles=["Test Question 5"])
    assert len(asn.questions) == 5
    asn.remove_questions(question_titles=["Test Question [0-9]+"])
    assert len(asn.questions) == 0
    asn.add_question(
        title="Test Question",
        weight=100,
    )
    assert len(asn.questions) == 1

def add_instructor_submission(asn: GSAssignment):
    asn.add_instructor_submission(fname=os.path.join(os.path.dirname(__file__), "test_pdf.pdf"))
    

def download_submissions(asn: GSAssignment):
    asn.download_submissions()


def run_tests():
    logging.basicConfig(level=logging.DEBUG)
    conn = GSConnection()
    conn.login(email, password)
    conn.load_account_data()
    print(conn.account)
    #exit()
    test_course = create_test_course(conn)
    test_asn = create_test_assignment(test_course)
    breakpoint()
    add_questions(conn, test_asn)
    add_instructor_submission(test_asn)
    test_asn.publish_grades()
    test_asn.unpublish_grades()
    test_asn.download_submissions()

def test_util():
    course = GSConnection.get_course(
        email=email,
        password=password,
        course_id="957700",
        instructor=True
    )
    print(course)

if __name__ == "__main__":
    run_tests()
    # test_util()
    # logging.basicConfig(level=logging.DEBUG)
    # conn = GSConnection()
    # conn.login(email, password)
    # conn.get_account()
    
    # asn = create_test_course(conn)
    
    # course: GSCourse = conn.account.get_classes(course_ids=["836005"], instructor=True)[0]
    # asn: GSAssignment = course.get_assignment(name="Homework 14")
    # add_questions(conn, asn)
    # add_instructor_submission(asn)
    # asn.publish_grades()
    # # breakpoint()
    # asn.unpublish_grades()
    # asn.download_submissions()a
    # asn: GSAssignment = conn.account.get_classes(course_ids=["957700"], instructor=True)[0].get_assignment(name="Test Assignment 2")
    # asn.download_grades(fname="grades.csv")
    # add_questions(conn, asn)
    # add_instructor_submission(asn)
    # asn.publish_grades()
    # # breakpoint()
    # asn.unpublish_grades()
    # asn.download_submissions()
