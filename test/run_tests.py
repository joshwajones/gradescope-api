import datetime
import os

from pyscope.session import GSConnection
from pyscope.account import GSAccount
from pyscope.course import GSCourse, GSPerson, GSRole
from pyscope.assignment import GSAssignment
from pyscope.extension import GSExtension

from private_config import email, password

if __name__ == "__main__":
    conn = GSConnection()
    conn.login(email, password)
    conn.get_account()
    account = conn.account
    account.delete_classes(
        course_names=["Test Course"],
        ask_for_confirmation=False
    )

    account.create_course(
        name = "Test Course",
        nickname = "test",
        description = "Dummy course for testing",
        term = "Spring",
        year = "2026",
        entry_code_enabled = False
    )

    course: GSCourse  = account.get_classes(course_names=["Test Course"], instructor=True)[0]
    course.update_roster()
    course.add_person(
        name="test_student",
        email="test1@gmail.com",
        role=GSRole.STUDENT,
        notify=True,
    )
    course.change_person_role(name="test_student", new_role=GSRole.READER)
    course.add_person(
        name="test_instructor",
        email="test2@gmail.com",
        role=GSRole.INSTRUCTOR,
        sid="123456789",
        notify=False,
    )
    course.change_person_role(name="test_instructor", new_role=GSRole.STUDENT)
    course.add_person(
        name = "test_student2",
        email = "test3@gmail.com",
        role = GSRole.STUDENT,
        notify = True,
    )

    test_file_path = os.path.join(os.path.dirname(__file__), "test_pdf.pdf")
    course.add_assignment(
        name="Test Assignment",
        release=datetime.datetime.now(),
        due=datetime.datetime.now(),
        template_file_path=test_file_path,
    )
    course.add_assignment(
        name="Test Assignment 2",
        release=datetime.datetime.now(),
        due=datetime.datetime.now(),
        template_file_path=test_file_path,
    )
    course.update_assignments()


    extension = GSExtension(
        student = course.get_person(name="test_student2"),
        release_date = datetime.datetime.now(),
        due_date = datetime.datetime.now(),
        late_due_date = datetime.datetime.now(),
        time_limit_minutes = 10,
    )

    asn: GSAssignment = course.get_assignment(name="Test Assignment 2")
    asn.apply_extension(extension)
    asn.remove_extension(course.get_person(name="test_student2"))

    asn = course.get_assignment(name="Test Assignment")
    asn.apply_extension(extension)

    account.delete_classes(
        course_names=["Test Course"],
        ask_for_confirmation=False
    )
