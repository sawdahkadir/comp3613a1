"""Integration test for the student degree progress workflow."""

from sqlmodel import select

from app.models.progress import StudentCourse


def test_progress_page(make, session, client, login_as):
    """A signed-in student sees progress built from their real transcript."""
    user = make.user(username="bob", role="regular_user")
    degree = make.degree(total_credits=93)
    student = make.student(user=user, degree=degree)

    first = make.course("COMP1600", "Introduction to Computing", 30)
    second = make.course("COMP1601", "Programming I", 30)
    third = make.course("COMP2600", "Data Structures", 40)
    for course in (first, second, third):
        make.complete(student, course)
        make.require(degree, course)

    login_as(user)
    response = client.get("/app/progress")

    assert response.status_code == 200
    body = response.text
    assert "My Degree Progress" in body
    assert "BSc Computer Science" in body
    assert "108% complete" in body
    assert "100 / 93" in body
    assert "COMP1600" in body
    assert "COMP1601" in body
    assert "COMP2600" in body

    session.expire_all()
    transcript = session.exec(
        select(StudentCourse).where(
            StudentCourse.studentID == student.id,
            StudentCourse.status == "completed",
        )
    ).all()
    assert len(transcript) == 3
