from datetime import datetime, timedelta
import os
import logging
import argparse

from pyscope.session import GSConnection
from pyscope.course import GSCourse, GSRole
from pyscope.assignment import GSAssignment
from pyscope.extension import GSExtension

from private_config import email, password

TEST_COURSE_NAME = "-GRADESCOPE-API-TEST-COURSE-"


def create_test_course(conn: GSConnection) -> GSAssignment:
    account = conn.account

    account.delete_classes(course_names=[TEST_COURSE_NAME], ask_for_confirmation=False)

    account.create_course(
        name=TEST_COURSE_NAME,
        nickname=TEST_COURSE_NAME,
        description="Dummy course for testing",
        term="Spring",
        year="2026",
        entry_code_enabled=False,
    )
    matched_courses = account.get_classes(
        course_names=[TEST_COURSE_NAME], instructor=True
    )
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
        name="Test Person 3",
        email="test3@gmail.com",
        role=GSRole.STUDENT,
        notify=False,
    )

    course.add_person(
        name="Test Person 4",
        email="test4@gmail.com",
        role=GSRole.INSTRUCTOR,
        notify=False,
    )

    course.add_person(
        name="Test Person 5",
        email="test5@gmail.com",
        role=GSRole.STUDENT,
        notify=False,
    )

    all_people = course.get_all_people()
    assert len(all_people) == 6, all_people

    name_to_person = {person.name: person for person in all_people}
    assert name_to_person["Test Person 1"].role == GSRole.READER
    assert name_to_person["Test Person 2"].role == GSRole.STUDENT
    assert name_to_person["Test Person 3"].role == GSRole.STUDENT
    assert name_to_person["Test Person 4"].role == GSRole.INSTRUCTOR
    assert name_to_person["Test Person 5"].role == GSRole.STUDENT

    course.remove_person(name="Test Person 3", ask_for_confirmation=False)
    course.remove_person(name="Test Person 4", ask_for_confirmation=False)

    all_people = course.get_all_people()
    assert len(all_people) == 4
    name_to_person = {person.name: person for person in all_people}
    assert {"Test Person 1", "Test Person 2", "Test Person 5"} <= set(
        name_to_person.keys()
    )

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
        release=datetime.fromisoformat("2022-03-05T00:00"),
        due=datetime.fromisoformat("2022-04-08T00:40"),
        template_file_path=test_file_path,
    )
    course.add_assignment(
        name="Test Assignment 3",
        release=datetime.fromisoformat("2022-03-05T00:00"),
        due=datetime.fromisoformat("2022-04-08T00:40"),
        template_file_path=test_file_path,
    )

    assignments = course.get_all_assignments()
    assert len(assignments) == 3
    names = [assignment.name for assignment in assignments]
    assert set(names) == set(
        ["Test Assignment", "Test Assignment 2", "Test Assignment 3"]
    )

    course.remove_assignment(name="Test Assignment 3", ask_for_confirmation=False)
    assignments = course.get_all_assignments()
    assert len(course.assignments) == 2
    names = [assignment.name for assignment in assignments]
    assert set(names) == set(["Test Assignment", "Test Assignment 2"])

    extension = GSExtension.create(
        release_date=datetime.now(),
        due_date=datetime.now(),
        late_due_date=datetime.now(),
        time_limit_minutes=10,
    )

    asn: GSAssignment = course.get_assignment(name="Test Assignment 2")
    asn.apply_extension(extension, student_email="test2@gmail.com")
    asn.remove_extension(course.get_person(name="Test Person 2").email)

    asn = course.get_assignment(name="Test Assignment")
    asn.apply_extension(extension, student_email="test2@gmail.com")

    extension = GSExtension.create(
        release_date=datetime.now(),
        due_date=datetime.now(),
        late_due_date=datetime.now(),
        time_limit_minutes=10,
        release_delta=timedelta(days=1),
        due_delta=timedelta(days=1),
        late_due_delta=timedelta(days=100),
        limit_multipler=2,
    )
    asn.apply_extension(extension, student_email="test5@gmail.com")
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
            title="Test Question 5",
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
    asn.add_instructor_submission(
        fname=os.path.join(os.path.dirname(__file__), "test_pdf.pdf")
    )


def download_submissions(asn: GSAssignment):
    asn.download_submissions()


def run_tests(
    course_name: str = None, assignment_name: str = None, course_id: str = None
):
    conn = GSConnection()
    conn.login(email, password)
    conn.load_account_data()
    skip_create = bool(course_name) or bool(assignment_name) or bool(course_id)
    if skip_create:
        if course_name is None:
            course_name = TEST_COURSE_NAME
        if assignment_name is None:
            assignment_name = "Test Assignment"
        if course_id is None:
            course_id = conn.account.get_classes(
                course_names=[course_name], instructor=True
            )[0].course_id

        test_course = conn.account.get_classes(course_ids=[course_id], instructor=True)[
            0
        ]
        test_asn = test_course.get_assignment(name=assignment_name)
    else:
        test_course = create_test_course(conn)
        test_asn = create_test_assignment(test_course)
        add_questions(conn, test_asn)
        test_asn.add_student_submission(
            fname=os.path.join(os.path.dirname(__file__), "test_pdf.pdf"),
            student_email="test5@gmail.com",
        )
        test_asn.publish_grades()
        test_asn.unpublish_grades()
    test_asn.download_submissions()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-l",
        "--log-level",
        default="INFO",
        choices=logging._nameToLevel.keys(),
        help="Set the log level",
    )
    parser.add_argument(
        "-c",
        "--course-id",
        default=None,
        help="The id of the course to access. If not provided, will use the test course",
    )
    parser.add_argument(
        "-a",
        "--assignment-name",
        default=None,
        help="The name of the assignment to access. If not provided, will use the test assignment",
    )
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level))
    run_tests(course_id=args.course_id, assignment_name=args.assignment_name)
