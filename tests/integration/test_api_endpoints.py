"""Integration tests for the versioned JSON API (``/api/v1``).

These exercise the new API layer end to end against the same isolated
temporary database used by the other integration tests. The existing HTML
workflows are covered separately and are not touched here.
"""

from sqlmodel import select

from app.models.planning import SemesterPlan
from app.models.review import Notification
from app.utilities.security import create_access_token


def auth_header(user) -> dict:
    """Build the ``Authorization: Bearer`` header the API expects."""
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return {"Authorization": f"Bearer {token}"}


# —— authentication ——————————————————————————————————————————————


def test_api_login_success(make, client):
    user = make.user(username="bob", password="secret123")

    response = client.post(
        "/api/v1/auth/login",
        json={"username": "bob", "password": "secret123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["username"] == user.username
    assert body["role"] == user.role
    assert body["access_token"]


def test_api_login_invalid_credentials(make, client):
    make.user(username="bob", password="secret123")

    response = client.post(
        "/api/v1/auth/login",
        json={"username": "bob", "password": "wrong"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password."


def test_api_requires_token(client):
    response = client.get("/api/v1/plans")

    assert response.status_code == 401
    assert "detail" in response.json()


def test_api_rejects_bad_token(client):
    response = client.get(
        "/api/v1/plans", headers={"Authorization": "Bearer not-a-real-token"}
    )

    assert response.status_code == 401
    assert "detail" in response.json()


# —— student progress and catalogue ——————————————————————————————


def test_api_progress(make, client):
    user = make.user()
    degree = make.degree(total_credits=93)
    student = make.student(user=user, degree=degree, name="Bob Student")
    first = make.course("COMP1600", "Introduction to Computing", 30)
    second = make.course("COMP1601", "Programming I", 30)
    for course in (first, second):
        make.complete(student, course)
        make.require(degree, course)

    response = client.get("/api/v1/students/me/progress", headers=auth_header(user))

    assert response.status_code == 200
    body = response.json()
    assert body["studentName"] == "Bob Student"
    assert body["degreeName"] == "BSc Computer Science"
    assert body["creditsCompleted"] == 60
    assert body["creditsTotal"] == 93
    assert body["percentComplete"] == 65
    assert [course["code"] for course in body["completedCourses"]] == [
        "COMP1600",
        "COMP1601",
    ]


def test_api_progress_without_student_profile(make, client):
    user = make.user()

    response = client.get("/api/v1/students/me/progress", headers=auth_header(user))

    assert response.status_code == 404
    assert "degree" in response.json()["detail"].lower()


def test_api_course_catalogue_flags_completed(make, client):
    user = make.user()
    student = make.student(user=user)
    done = make.course("COMP1600")
    make.course("COMP1601")
    make.complete(student, done)

    response = client.get("/api/v1/courses", headers=auth_header(user))

    assert response.status_code == 200
    courses = {course["code"]: course for course in response.json()}
    assert courses["COMP1600"]["alreadyCompleted"] is True
    assert courses["COMP1601"]["alreadyCompleted"] is False


# —— semester plans ——————————————————————————————————————————————


def test_api_list_plans_is_empty_for_new_student(make, client):
    user = make.user()
    make.student(user=user)

    response = client.get("/api/v1/plans", headers=auth_header(user))

    assert response.status_code == 200
    assert response.json() == []


def test_api_create_plan(make, client):
    user = make.user()
    make.student(user=user)
    course = make.course("COMP1600")

    response = client.post(
        "/api/v1/plans",
        headers=auth_header(user),
        json={
            "semester": "1",
            "academicYear": "2026/2027",
            "courseIDs": [course.id],
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "draft"
    assert body["semester"] == "1"
    assert body["academicYear"] == "2026/2027"
    assert [row["code"] for row in body["courses"]] == ["COMP1600"]
    assert response.headers["location"] == f"/api/v1/plans/{body['planID']}"


def test_api_create_empty_plan_is_rejected(make, session, client):
    user = make.user()
    student = make.student(user=user)

    response = client.post(
        "/api/v1/plans",
        headers=auth_header(user),
        json={"semester": "1", "academicYear": "2026/2027", "courseIDs": []},
    )

    assert response.status_code == 400
    assert "at least one course" in response.json()["detail"].lower()

    session.expire_all()
    assert (
        session.exec(
            select(SemesterPlan).where(SemesterPlan.studentID == student.id)
        ).all()
        == []
    )


def test_api_unmet_prerequisite_is_rejected(make, session, client):
    user = make.user()
    student = make.student(user=user)
    prerequisite = make.course("COMP1600", "Programming I")
    target = make.course("COMP2600", "Data Structures")
    make.prerequisite(target, prerequisite)

    response = client.post(
        "/api/v1/plans",
        headers=auth_header(user),
        json={"semester": "1", "academicYear": "2026/2027", "courseIDs": [target.id]},
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "prerequisite" in detail.lower()
    assert "COMP1600" in detail

    session.expire_all()
    assert (
        session.exec(
            select(SemesterPlan).where(SemesterPlan.studentID == student.id)
        ).all()
        == []
    )


def test_api_duplicate_term_is_conflict(make, client):
    user = make.user()
    student = make.student(user=user)
    course = make.course("COMP1600")
    make.plan(student, semester="1", academic_year="2026/2027", courses=[course])

    response = client.post(
        "/api/v1/plans",
        headers=auth_header(user),
        json={
            "semester": "1",
            "academicYear": "2026/2027",
            "courseIDs": [course.id],
        },
    )

    assert response.status_code == 409
    assert "already have a plan" in response.json()["detail"].lower()


def test_api_plan_detail_is_scoped_to_owner(make, client):
    owner = make.user()
    make.student(user=owner)
    other = make.user()
    other_student = make.student(user=other)
    plan = make.plan(other_student, courses=[make.course("COMP1600")])

    response = client.get(f"/api/v1/plans/{plan.id}", headers=auth_header(owner))

    assert response.status_code == 404


def test_api_plan_detail_returns_courses(make, client):
    user = make.user()
    student = make.student(user=user)
    course = make.course("COMP1600", "Introduction to Computing")
    plan = make.plan(student, courses=[course])

    response = client.get(f"/api/v1/plans/{plan.id}", headers=auth_header(user))

    assert response.status_code == 200
    body = response.json()
    assert body["planID"] == plan.id
    assert body["canEdit"] is True
    assert body["courses"][0]["code"] == "COMP1600"


def test_api_update_plan(make, session, client):
    user = make.user()
    student = make.student(user=user)
    old_course = make.course("COMP1600")
    new_course = make.course("COMP1601")
    plan = make.plan(student, status="draft", courses=[old_course])

    response = client.patch(
        f"/api/v1/plans/{plan.id}",
        headers=auth_header(user),
        json={"courseIDs": [new_course.id]},
    )

    assert response.status_code == 200
    assert [row["code"] for row in response.json()["courses"]] == ["COMP1601"]
    assert response.json()["status"] == "draft"

    session.expire_all()
    assert session.get(SemesterPlan, plan.id).status == "draft"


def test_api_submit_plan(make, session, client):
    user = make.user()
    student = make.student(user=user)
    course = make.course("COMP1600")
    plan = make.plan(student, status="draft", courses=[course])

    response = client.post(
        f"/api/v1/plans/{plan.id}/submit", headers=auth_header(user)
    )

    assert response.status_code == 200
    assert response.json()["status"] == "submitted"

    session.expire_all()
    assert session.get(SemesterPlan, plan.id).status == "submitted"


def test_api_cannot_edit_submitted_plan(make, client):
    user = make.user()
    student = make.student(user=user)
    course = make.course("COMP1600")
    plan = make.plan(student, status="submitted", courses=[course])

    response = client.patch(
        f"/api/v1/plans/{plan.id}",
        headers=auth_header(user),
        json={"courseIDs": [course.id]},
    )

    assert response.status_code == 409


# —— advisor review ——————————————————————————————————————————————


def test_api_advisor_lists_assigned_submitted_plans(make, client):
    admin = make.user(username="advisor", role="admin")
    advisor = make.advisor(user=admin)
    student = make.student(advisor=advisor, name="Alice Student")
    plan = make.plan(student, status="submitted", courses=[make.course("COMP1600")])

    response = client.get("/api/v1/advisor/plans", headers=auth_header(admin))

    assert response.status_code == 200
    rows = response.json()
    assert [row["planID"] for row in rows] == [plan.id]
    assert rows[0]["studentName"] == "Alice Student"


def test_api_student_cannot_use_advisor_routes(make, client):
    user = make.user(role="regular_user")
    make.student(user=user)

    response = client.get("/api/v1/advisor/plans", headers=auth_header(user))

    assert response.status_code == 403
    assert "advisor" in response.json()["detail"].lower()


def test_api_advisor_review_screen(make, client):
    admin = make.user(username="advisor", role="admin")
    advisor = make.advisor(user=admin)
    student = make.student(advisor=advisor, student_number="816000123")
    course = make.course("COMP1600")
    plan = make.plan(student, status="submitted", courses=[course])

    response = client.get(
        f"/api/v1/advisor/plans/{plan.id}", headers=auth_header(admin)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["planID"] == plan.id
    assert body["studentID"] == "816000123"
    assert body["canReview"] is True
    assert body["courses"][0]["code"] == "COMP1600"


def test_api_advisor_approve_plan(make, session, client):
    admin = make.user(username="advisor", role="admin")
    advisor = make.advisor(user=admin)
    student = make.student(advisor=advisor)
    course = make.course("COMP1600")
    plan = make.plan(student, status="submitted", courses=[course])

    response = client.post(
        f"/api/v1/advisor/plans/{plan.id}/decision",
        headers=auth_header(admin),
        json={
            "decision": "approve",
            "planFeedback": "Approved for this term.",
            "courses": [
                {"courseID": course.id, "decision": "approved", "feedback": "Good"}
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "approved"
    assert body["courses"][0]["decision"] == "approved"
    assert body["courses"][0]["feedback"] == "Good"

    session.expire_all()
    assert session.get(SemesterPlan, plan.id).status == "approved"
    notifications = session.exec(
        select(Notification).where(Notification.studentID == student.id)
    ).all()
    assert len(notifications) == 1


def test_api_advisor_reject_plan(make, session, client):
    admin = make.user(username="advisor", role="admin")
    advisor = make.advisor(user=admin)
    student = make.student(advisor=advisor)
    course = make.course("COMP1600")
    plan = make.plan(student, status="submitted", courses=[course])

    response = client.post(
        f"/api/v1/advisor/plans/{plan.id}/decision",
        headers=auth_header(admin),
        json={
            "decision": "reject",
            "planFeedback": "Please revise.",
            "courses": [
                {"courseID": course.id, "decision": "rejected", "feedback": "No"}
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"

    session.expire_all()
    assert session.get(SemesterPlan, plan.id).status == "rejected"


def test_api_advisor_cannot_review_again(make, client):
    admin = make.user(username="advisor", role="admin")
    advisor = make.advisor(user=admin)
    student = make.student(advisor=advisor)
    course = make.course("COMP1600")
    plan = make.plan(student, status="approved", courses=[course])

    response = client.post(
        f"/api/v1/advisor/plans/{plan.id}/decision",
        headers=auth_header(admin),
        json={"decision": "approve", "courses": []},
    )

    assert response.status_code == 409
    assert "already been reviewed" in response.json()["detail"].lower()


def test_api_advisor_cannot_review_other_advisors_plan(make, client):
    admin = make.user(username="advisor", role="admin")
    make.advisor(user=admin)
    other_advisor = make.advisor(name="Dr. Other")
    other_student = make.student(advisor=other_advisor)
    plan = make.plan(other_student, status="submitted", courses=[make.course("COMP1600")])

    response = client.get(
        f"/api/v1/advisor/plans/{plan.id}", headers=auth_header(admin)
    )

    assert response.status_code == 404
