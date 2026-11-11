"""Unit tests for advisor review (workflow 3)."""

from sqlmodel import select

from app.models.review import Notification, PlanReview
from app.repositories.review import ReviewRepository
from app.services.review import ReviewService


def review_repo(session) -> ReviewRepository:
    return ReviewRepository(session)


def review_service(session) -> ReviewService:
    return ReviewService(ReviewRepository(session))


def test_filter_plans(make, session):
    advisor = make.advisor()
    pending_student = make.student(advisor=advisor, name="Pending Student")
    reviewed_student = make.student(advisor=advisor, name="Reviewed Student")

    old_term = make.plan(
        pending_student,
        semester="1",
        academic_year="2024/2025",
        status="submitted",
    )
    other_semester = make.plan(
        pending_student,
        semester="2",
        academic_year="2025/2026",
        status="submitted",
    )
    matching_pending = make.plan(
        pending_student,
        semester="1",
        academic_year="2025/2026",
        status="submitted",
    )
    matching_reviewed = make.plan(
        reviewed_student,
        semester="1",
        academic_year="2025/2026",
        status="approved",
    )

    pending, reviewed = review_service(session).list_plans(
        advisor.id, academic_year="2025/2026", semester="1"
    )

    assert [row.planID for row in pending] == [matching_pending.id]
    assert [row.planID for row in reviewed] == [matching_reviewed.id]
    assert old_term.id not in {row.planID for row in pending + reviewed}
    assert other_semester.id not in {row.planID for row in pending + reviewed}


def test_review_screen(make, session):
    advisor = make.advisor()
    student = make.student(
        advisor=advisor,
        name="Alice Student",
        student_number="816000123",
    )
    first = make.course("COMP1600", "Programming I", 3)
    second = make.course("COMP2600", "Data Structures", 4)
    plan = make.plan(
        student,
        semester="2",
        academic_year="2025/2026",
        status="submitted",
        courses=[first, second],
    )
    review_repo(session).set_course_decision(
        plan.id, first.id, "approved", "Looks good"
    )

    screen = review_service(session).get_review_screen(advisor.id, plan.id)

    assert screen is not None
    assert screen.planID == plan.id
    assert screen.studentID == "816000123"
    assert screen.studentName == "Alice Student"
    assert screen.semester == "2"
    assert screen.academicYear == "2025/2026"
    assert screen.status == "submitted"
    assert screen.canReview is True
    assert [course.code for course in screen.courses] == ["COMP1600", "COMP2600"]
    assert [course.decision for course in screen.courses] == ["approved", "pending"]
    assert [course.feedback for course in screen.courses] == ["Looks good", None]


def test_approve_with_pending_course(make, session):
    advisor = make.advisor()
    student = make.student(advisor=advisor)
    first = make.course("COMP1600")
    second = make.course("COMP1601")
    plan = make.plan(student, status="submitted", courses=[first, second])

    error = review_service(session).submit_review(
        advisor.id,
        plan.id,
        {first.id: ("approved", "")},
        "",
        "approve",
    )

    assert error == "Set a decision on every course before approving this plan."
    assert review_repo(session).get_plan(plan.id).status == "submitted"
    assert session.exec(select(PlanReview)).all() == []


def test_approve_with_rejected_course(make, session):
    advisor = make.advisor()
    student = make.student(advisor=advisor)
    first = make.course("COMP1600")
    second = make.course("COMP1601")
    plan = make.plan(student, status="submitted", courses=[first, second])

    error = review_service(session).submit_review(
        advisor.id,
        plan.id,
        {
            first.id: ("approved", ""),
            second.id: ("rejected", "Does not fit the degree"),
        },
        "",
        "approve",
    )

    assert "cannot be approved while a course on it is rejected" in error
    assert review_repo(session).get_plan(plan.id).status == "submitted"
    assert session.exec(select(PlanReview)).all() == []


def test_reject_plan(make, session):
    advisor = make.advisor()
    student = make.student(advisor=advisor)
    first = make.course("COMP1600")
    second = make.course("COMP1601")
    plan = make.plan(student, status="submitted", courses=[first, second])

    error = review_service(session).submit_review(
        advisor.id,
        plan.id,
        {
            first.id: ("rejected", "Choose a different elective"),
            second.id: ("approved", ""),
        },
        "Please revise your selection.",
        "reject",
    )

    assert error is None
    assert review_repo(session).get_plan(plan.id).status == "rejected"

    review = session.exec(select(PlanReview)).one()
    assert review.planID == plan.id
    assert review.advisorID == advisor.id
    assert review.decision == "rejected"
    assert review.feedback == "Please revise your selection."

    notifications = session.exec(
        select(Notification).where(Notification.studentID == student.id)
    ).all()
    assert len(notifications) == 1
    assert "rejected" in notifications[0].message.lower()

    rows = review_repo(session).get_plan_courses(plan.id)
    decisions = {course.code: row.decision for row, course in rows}
    assert decisions == {"COMP1600": "rejected", "COMP1601": "approved"}


def test_review_unassigned_plan(make, session):
    responsible_advisor = make.advisor(name="Dr. Responsible")
    other_advisor = make.advisor(name="Dr. Other")
    student = make.student(advisor=responsible_advisor)
    course = make.course("COMP1600")
    plan = make.plan(student, status="submitted", courses=[course])

    service = review_service(session)
    assert service.get_review_screen(other_advisor.id, plan.id) is None

    error = service.submit_review(
        other_advisor.id,
        plan.id,
        {course.id: ("approved", "")},
        "",
        "approve",
    )

    assert error == "That semester plan is not one of your students'."
    assert review_repo(session).get_plan(plan.id).status == "submitted"
    assert session.exec(select(PlanReview)).all() == []
