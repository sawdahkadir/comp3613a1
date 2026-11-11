"""Integration tests for semester planning workflows (submit, validate, resubmit)."""

from sqlmodel import select

from app.models.planning import SemesterPlan, SemesterPlanCourse


def test_submit_plan(make, session, client, login_as):
    """Submitting a plan saves the plan and its courses, then shows the detail page."""
    user = make.user()
    student = make.student(user=user)
    first = make.course("COMP1600")
    second = make.course("COMP1601")

    login_as(user)
    response = client.post(
        "/app/plans",
        data={
            "semester": "1",
            "academicYear": "2025/2026",
            "courseIDs": [str(first.id), str(second.id)],
            "action": "submit",
        },
    )

    assert response.status_code == 303

    session.expire_all()
    plans = session.exec(
        select(SemesterPlan).where(SemesterPlan.studentID == student.id)
    ).all()
    assert len(plans) == 1
    plan = plans[0]
    assert plan.status == "submitted"
    assert response.headers["location"].endswith(f"/app/plans/{plan.id}")

    rows = session.exec(
        select(SemesterPlanCourse).where(SemesterPlanCourse.planID == plan.id)
    ).all()
    assert {row.courseID for row in rows} == {first.id, second.id}
    assert {row.decision for row in rows} == {"pending"}

    detail = client.get(f"/app/plans/{plan.id}")
    assert detail.status_code == 200
    assert "Submitted" in detail.text
    assert "COMP1600" in detail.text
    assert "COMP1601" in detail.text


def test_empty_plan(make, session, client, login_as):
    """A plan with no courses is rejected and nothing is written."""
    user = make.user()
    student = make.student(user=user)

    login_as(user)
    response = client.post(
        "/app/plans",
        data={
            "semester": "1",
            "academicYear": "2025/2026",
            "action": "submit",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Select at least one course before saving the plan." in response.text

    session.expire_all()
    assert (
        session.exec(
            select(SemesterPlan).where(SemesterPlan.studentID == student.id)
        ).all()
        == []
    )


def test_unmet_prerequisite(make, session, client, login_as):
    """A course whose prerequisite is not completed blocks the plan."""
    user = make.user()
    student = make.student(user=user)
    prerequisite = make.course("COMP1600", "Programming I")
    target = make.course("COMP2600", "Data Structures")
    make.prerequisite(target, prerequisite)

    login_as(user)
    response = client.post(
        "/app/plans",
        data={
            "semester": "1",
            "academicYear": "2025/2026",
            "courseIDs": [str(target.id)],
            "action": "submit",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Prerequisite not completed" in response.text
    assert "COMP1600 must be completed first" in response.text

    session.expire_all()
    assert (
        session.exec(
            select(SemesterPlan).where(SemesterPlan.studentID == student.id)
        ).all()
        == []
    )


def test_met_prerequisite(make, session, client, login_as):
    """Once the prerequisite is completed the plan is created and submitted."""
    user = make.user()
    student = make.student(user=user)
    prerequisite = make.course("COMP1600", "Programming I")
    target = make.course("COMP2600", "Data Structures")
    make.prerequisite(target, prerequisite)
    make.complete(student, prerequisite)

    login_as(user)
    response = client.post(
        "/app/plans",
        data={
            "semester": "1",
            "academicYear": "2025/2026",
            "courseIDs": [str(target.id)],
            "action": "submit",
        },
    )

    assert response.status_code == 303

    session.expire_all()
    plans = session.exec(
        select(SemesterPlan).where(SemesterPlan.studentID == student.id)
    ).all()
    assert len(plans) == 1
    plan = plans[0]
    assert plan.status == "submitted"

    rows = session.exec(
        select(SemesterPlanCourse).where(SemesterPlanCourse.planID == plan.id)
    ).all()
    assert [row.courseID for row in rows] == [target.id]


def test_resubmit_plan(make, session, client, login_as):
    """Editing a rejected plan replaces its courses and resubmits it clean."""
    user = make.user()
    student = make.student(user=user)
    old_course = make.course("COMP1600")
    new_course = make.course("COMP1601")
    plan = make.plan(
        student,
        semester="2",
        academic_year="2026/2027",
        status="rejected",
        courses=[old_course],
        decisions=[(old_course, "rejected", "Please choose another course.")],
    )

    login_as(user)
    edit = client.get(f"/app/plans/{plan.id}/edit")
    assert edit.status_code == 200
    assert "COMP1600" in edit.text
    assert f'value="{old_course.id}"' in edit.text

    response = client.post(
        "/app/plans",
        data={
            "planID": str(plan.id),
            "semester": "2",
            "academicYear": "2026/2027",
            "courseIDs": [str(new_course.id)],
            "action": "submit",
        },
    )

    assert response.status_code == 303
    assert response.headers["location"].endswith(f"/app/plans/{plan.id}")

    session.expire_all()
    updated = session.get(SemesterPlan, plan.id)
    assert updated.status == "submitted"

    rows = session.exec(
        select(SemesterPlanCourse).where(SemesterPlanCourse.planID == plan.id)
    ).all()
    assert [row.courseID for row in rows] == [new_course.id]
    assert rows[0].decision == "pending"
    assert rows[0].feedback is None
