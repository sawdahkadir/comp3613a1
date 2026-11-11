"""Unit tests for degree progress (workflow 1)."""

from app.repositories.progress import ProgressRepository
from app.services.progress import ProgressService


def progress_service(session) -> ProgressService:
    return ProgressService(ProgressRepository(session))


def test_progress_calculation(make, session):
    user = make.user()
    degree = make.degree(total_credits=93)
    student = make.student(user=user, degree=degree)

    first = make.course("COMP1600", "Introduction to Computing", 30)
    second = make.course("COMP1601", "Programming I", 30)
    third = make.course("COMP2600", "Data Structures", 40)
    for course in (first, second, third):
        make.complete(student, course)
        make.require(degree, course)

    progress = progress_service(session).get_degree_progress(user.id)

    assert progress is not None
    assert progress.studentName == student.name
    assert progress.degreeName == degree.degreeName
    assert progress.faculty == degree.faculty
    assert progress.creditsCompleted == 100
    assert progress.creditsTotal == 93
    # Deliberately not capped: 100 / 93 rounds to 108%.
    assert progress.percentComplete == 108
    assert progress.creditsRemaining == 0
    assert progress.coursesCompleted == 3
    assert progress.coursesRequired == 3
    assert [course.code for course in progress.completedCourses] == [
        "COMP1600",
        "COMP1601",
        "COMP2600",
    ]


def test_no_student_profile(make, session):
    user = make.user()

    progress = progress_service(session).get_degree_progress(user.id)

    assert progress is None


def test_no_degree_record(make, session):
    user = make.user()
    degree = make.degree()
    student = make.student(user=user, degree=degree)

    student.degreeID = 9999
    session.add(student)
    session.commit()

    progress = progress_service(session).get_degree_progress(user.id)

    assert progress is None


def test_zero_required_credits(make, session):
    user = make.user()
    degree = make.degree(total_credits=0)
    make.student(user=user, degree=degree)

    progress = progress_service(session).get_degree_progress(user.id)

    assert progress is not None
    assert progress.creditsCompleted == 0
    assert progress.creditsTotal == 0
    assert progress.creditsRemaining == 0
    assert progress.percentComplete == 0


def test_empty_transcript(make, session):
    user = make.user()
    degree = make.degree(total_credits=93)
    make.student(user=user, degree=degree)

    progress = progress_service(session).get_degree_progress(user.id)

    assert progress is not None
    assert progress.creditsCompleted == 0
    assert progress.creditsTotal == 93
    assert progress.creditsRemaining == 93
    assert progress.percentComplete == 0
    assert progress.coursesCompleted == 0
    assert progress.completedCourses == []
