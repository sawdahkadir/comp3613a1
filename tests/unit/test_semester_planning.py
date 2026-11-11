"""Unit tests for semester planning (workflow 2)."""

from app.repositories.planning import PlanningRepository
from app.services.planning import PlanningService


def planning_repo(session) -> PlanningRepository:
    return PlanningRepository(session)


def planning_service(session) -> PlanningService:
    return PlanningService(PlanningRepository(session))


def test_create_plan(make, session):
    student = make.student()
    first = make.course("COMP1600", credits=3)
    second = make.course("COMP1601", credits=3)

    plan_id, error = planning_service(session).create_plan(
        student.id, "1", "2025/2026", [first.id, second.id]
    )

    assert error is None
    assert plan_id is not None

    repo = planning_repo(session)
    plan = repo.get_plan(plan_id)
    assert plan is not None
    assert plan.studentID == student.id
    assert plan.semester == "1"
    assert plan.academicYear == "2025/2026"
    assert plan.status == "draft"
    assert set(repo.get_plan_course_ids(plan_id)) == {first.id, second.id}


def test_no_courses(make, session):
    student = make.student()

    plan_id, error = planning_service(session).create_plan(
        student.id, "1", "2025/2026", []
    )

    assert plan_id is None
    assert error == "Select at least one course before saving the plan."
    assert planning_repo(session).list_plans_for_student(student.id) == []


def test_duplicate_plan(make, session):
    student = make.student()
    course = make.course("COMP1600")
    service = planning_service(session)

    first_id, first_error = service.create_plan(
        student.id, "1", "2025/2026", [course.id]
    )
    second_id, second_error = service.create_plan(
        student.id, "1", "2025/2026", [course.id]
    )

    assert first_error is None
    assert first_id is not None
    assert second_id is None
    assert "already have a plan" in second_error
    assert len(planning_repo(session).list_plans_for_student(student.id)) == 1


def test_unmet_prerequisite(make, session):
    student = make.student()
    prerequisite = make.course("COMP1600", "Programming I")
    target = make.course("COMP2600", "Data Structures")
    make.prerequisite(target, prerequisite)

    plan_id, error = planning_service(session).create_plan(
        student.id, "1", "2025/2026", [target.id]
    )

    assert plan_id is None
    assert "Prerequisite not completed" in error
    assert "COMP1600 must be completed first" in error
    assert planning_repo(session).list_plans_for_student(student.id) == []


def test_met_prerequisite(make, session):
    student = make.student()
    prerequisite = make.course("COMP1600", "Programming I")
    target = make.course("COMP2600", "Data Structures")
    make.prerequisite(target, prerequisite)
    make.complete(student, prerequisite)

    plan_id, error = planning_service(session).create_plan(
        student.id, "1", "2025/2026", [target.id]
    )

    assert error is None
    assert plan_id is not None
    assert planning_repo(session).get_plan_course_ids(plan_id) == [target.id]


def test_resubmit_rejected_plan(make, session):
    student = make.student()
    old_course = make.course("COMP1600")
    new_course = make.course("COMP1601")
    repo = planning_repo(session)
    plan = make.plan(student, status="rejected", courses=[old_course])
    repo.set_course_decision(
        plan.id, old_course.id, "rejected", "Please choose another course."
    )

    error = planning_service(session).update_plan(
        student.id, plan.id, [new_course.id], submit=True
    )

    assert error is None
    updated = repo.get_plan(plan.id)
    assert updated.status == "submitted"
    assert repo.get_plan_course_ids(plan.id) == [new_course.id]

    rows = repo.get_plan_courses(plan.id)
    assert [row.decision for row, _ in rows] == ["pending"]
    assert [row.feedback for row, _ in rows] == [None]


def test_edit_other_students_plan(make, session):
    owner = make.student(name="Plan Owner")
    other_student = make.student(name="Other Student")
    course = make.course("COMP1600")
    repo = planning_repo(session)
    plan = make.plan(owner, courses=[course])

    error = planning_service(session).update_plan(
        other_student.id, plan.id, [course.id], submit=True
    )

    assert error == "That plan does not belong to you."
    assert repo.get_plan(plan.id).status == "draft"
