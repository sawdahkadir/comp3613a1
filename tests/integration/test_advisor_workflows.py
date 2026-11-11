"""Integration tests for advisor plan lists, review screens and decisions."""

from sqlmodel import select

from app.models.planning import SemesterPlan, SemesterPlanCourse
from app.models.progress import Student
from app.models.review import Notification, PlanReview


def test_advisor_plan_list(make, session, client, login_as):
    """An advisor only sees submitted plans for their own assigned students."""
    admin_user = make.user(username="advisor", role="admin")
    advisor = make.advisor(user=admin_user)

    pending_student = make.student(
        advisor=advisor,
        name="Pending Student",
        student_number="816000123",
    )
    reviewed_student = make.student(
        advisor=advisor,
        name="Reviewed Student",
        student_number="816000124",
    )
    draft_student = make.student(
        advisor=advisor,
        name="Draft Student",
        student_number="816000125",
    )
    other_advisor = make.advisor(name="Dr. Other")
    other_student = make.student(
        advisor=other_advisor,
        name="Other Advisor Student",
        student_number="816000126",
    )

    pending_plan = make.plan(
        pending_student,
        semester="1",
        academic_year="2025/2026",
        status="submitted",
        courses=[make.course("COMP1600")],
    )
    make.plan(
        reviewed_student,
        semester="1",
        academic_year="2025/2026",
        status="approved",
        courses=[make.course("COMP1601")],
    )
    make.plan(
        draft_student,
        semester="2",
        academic_year="2025/2026",
        status="draft",
        courses=[make.course("COMP1602")],
    )
    make.plan(
        other_student,
        semester="1",
        academic_year="2025/2026",
        status="submitted",
        courses=[make.course("COMP1603")],
    )

    login_as(admin_user)
    response = client.get("/admin/plans")

    assert response.status_code == 200
    assert "Pending Student" in response.text
    assert "816000123" in response.text
    assert "Reviewed Student" not in response.text
    assert "Draft Student" not in response.text
    assert "Other Advisor Student" not in response.text

    session.expire_all()
    submitted = session.exec(
        select(SemesterPlan)
        .join(Student, SemesterPlan.studentID == Student.id)
        .where(
            Student.advisorID == advisor.id,
            SemesterPlan.status == "submitted",
        )
    ).all()
    assert [plan.id for plan in submitted] == [pending_plan.id]


def test_advisor_review_page(make, session, client, login_as):
    """The review screen shows the student, term, courses and saved decisions."""
    admin_user = make.user(username="advisor", role="admin")
    advisor = make.advisor(user=admin_user)
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
        decisions=[(first, "approved", "Looks good")],
    )

    login_as(admin_user)
    response = client.get(f"/admin/plans/{plan.id}")

    assert response.status_code == 200
    assert "Review Semester Plan" in response.text
    assert "816000123" in response.text
    assert "Semester 2" in response.text
    assert "2025/2026" in response.text
    assert "COMP1600" in response.text
    assert "COMP2600" in response.text
    assert "Looks good" in response.text
    assert "Approve Plan" in response.text
    assert "Reject Plan" in response.text

    session.expire_all()
    saved_plan = session.get(SemesterPlan, plan.id)
    assert saved_plan.status == "submitted"
    rows = session.exec(
        select(SemesterPlanCourse).where(SemesterPlanCourse.planID == plan.id)
    ).all()
    assert len(rows) == 2


def test_approve_plan(make, session, client, login_as):
    """Approving saves every course decision, the plan status, a review and a notification."""
    admin_user = make.user(username="advisor", role="admin")
    advisor = make.advisor(user=admin_user)
    student = make.student(advisor=advisor, name="Alice Student")
    first = make.course("COMP1600")
    second = make.course("COMP1601")
    plan = make.plan(
        student,
        semester="1",
        academic_year="2025/2026",
        status="submitted",
        courses=[first, second],
    )

    login_as(admin_user)
    response = client.post(
        f"/admin/plans/{plan.id}",
        data={
            "action": "approve",
            f"decision_{first.id}": "approved",
            f"courseFeedback_{first.id}": "Great choice",
            f"decision_{second.id}": "approved",
            f"courseFeedback_{second.id}": "Good",
            "planFeedback": "Approved for this term.",
        },
    )

    assert response.status_code == 303
    assert response.headers["location"].endswith("/admin/plans")

    session.expire_all()
    updated = session.get(SemesterPlan, plan.id)
    assert updated.status == "approved"

    rows = session.exec(
        select(SemesterPlanCourse).where(SemesterPlanCourse.planID == plan.id)
    ).all()
    decisions = {row.courseID: (row.decision, row.feedback) for row in rows}
    assert decisions == {
        first.id: ("approved", "Great choice"),
        second.id: ("approved", "Good"),
    }

    review = session.exec(
        select(PlanReview).where(PlanReview.planID == plan.id)
    ).one()
    assert review.advisorID == advisor.id
    assert review.decision == "approved"
    assert review.feedback == "Approved for this term."

    notifications = session.exec(
        select(Notification).where(Notification.studentID == student.id)
    ).all()
    assert len(notifications) == 1
    assert "approved" in notifications[0].message.lower()


def test_reject_plan(make, session, client, login_as):
    """Rejecting saves course feedback, the plan status, a review and a notification."""
    admin_user = make.user(username="advisor", role="admin")
    advisor = make.advisor(user=admin_user)
    student = make.student(advisor=advisor, name="Alice Student")
    first = make.course("COMP1600")
    second = make.course("COMP1601")
    plan = make.plan(
        student,
        semester="1",
        academic_year="2025/2026",
        status="submitted",
        courses=[first, second],
    )

    login_as(admin_user)
    response = client.post(
        f"/admin/plans/{plan.id}",
        data={
            "action": "reject",
            f"decision_{first.id}": "rejected",
            f"courseFeedback_{first.id}": "Choose a different course",
            f"decision_{second.id}": "approved",
            f"courseFeedback_{second.id}": "",
            "planFeedback": "Please revise your selection.",
        },
    )

    assert response.status_code == 303
    assert response.headers["location"].endswith("/admin/plans")

    session.expire_all()
    updated = session.get(SemesterPlan, plan.id)
    assert updated.status == "rejected"

    rows = session.exec(
        select(SemesterPlanCourse).where(SemesterPlanCourse.planID == plan.id)
    ).all()
    decisions = {row.courseID: (row.decision, row.feedback) for row in rows}
    assert decisions == {
        first.id: ("rejected", "Choose a different course"),
        second.id: ("approved", None),
    }

    review = session.exec(
        select(PlanReview).where(PlanReview.planID == plan.id)
    ).one()
    assert review.advisorID == advisor.id
    assert review.decision == "rejected"
    assert review.feedback == "Please revise your selection."

    notifications = session.exec(
        select(Notification).where(Notification.studentID == student.id)
    ).all()
    assert len(notifications) == 1
    assert "rejected" in notifications[0].message.lower()
