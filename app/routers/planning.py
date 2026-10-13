"""Student semester plan routes — Phase 5, workflow 2."""

from typing import List, Optional

from fastapi import Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import status

from app.dependencies.auth import AuthDep
from app.dependencies.session import SessionDep
from app.repositories.progress import ProgressRepository
from app.repositories.planning import PlanningRepository
from app.services.planning import PlanningService
from app.utilities.flash import flash
from . import router, templates


def _services(db):
    """Build the two repositories and the planning service for a handler."""
    student_repo = ProgressRepository(db)
    planning_repo = PlanningRepository(db)
    return student_repo, PlanningService(planning_repo)


@router.get("/app/plans", response_class=HTMLResponse, name="plans_view")
async def plans_view(request: Request, user: AuthDep, db: SessionDep):
    student_repo, service = _services(db)
    student = student_repo.get_student_by_user_id(user.id)

    return templates.TemplateResponse(
        request=request,
        name="plans.html",
        context={
            "user": user,
            "student": student,
            "plans": service.list_plans(student.id) if student else [],
        },
    )


@router.get("/app/plans/new", response_class=HTMLResponse, name="plan_create_view")
async def plan_create_view(request: Request, user: AuthDep, db: SessionDep):
    student_repo, service = _services(db)
    student = student_repo.get_student_by_user_id(user.id)

    return templates.TemplateResponse(
        request=request,
        name="plan_form.html",
        context={
            "user": user,
            "form": {
                "planID": None,
                "semester": "1",
                "academicYear": student.currentAcademicYear if student else "",
                "submitting": False,
                "error": None,
                "selectedCourseIDs": [],
                "courses": service.get_course_grid(student.id) if student else [],
            },
        },
    )


@router.post("/app/plans", response_class=HTMLResponse, name="plan_create_action")
async def plan_create_action(
    request: Request,
    user: AuthDep,
    db: SessionDep,
    semester: str = Form(),
    academicYear: str = Form(),
    courseIDs: List[int] = Form(default=[]),
    action: str = Form("draft"),
    planID: Optional[int] = Form(default=None),
):

    student_repo, service = _services(db)
    student = student_repo.get_student_by_user_id(user.id)

    if student is None:
        flash(request, "No student profile found.", "danger")
        return RedirectResponse(url=request.url_for("plans_view"), status_code=status.HTTP_303_SEE_OTHER)

    if action not in {"draft", "submit"}:
        flash(request, "Invalid plan action.", "danger")
        return RedirectResponse(url=request.url_for("plan_create_view"), status_code=status.HTTP_303_SEE_OTHER)

    if planID is not None:
        error = service.update_plan(student.id, planID, courseIDs, submit=(action == "submit"))
        plan_id = planID
    else:
       plan_id, error = service.create_plan(student.id, semester, academicYear, courseIDs)

    if error:
        flash(request, error, "danger")
                
        if planID is not None:
            return RedirectResponse(url=request.url_for("plan_edit_view", plan_id=planID), status_code=status.HTTP_303_SEE_OTHER)
        return RedirectResponse(url=request.url_for("plan_create_view"), status_code=status.HTTP_303_SEE_OTHER)
        
    if action == "submit":
        if planID is None:
            error = service.submit_existing_plan(student.id, plan_id)
            if error:
                flash(request, error, "danger")
                return RedirectResponse(url=request.url_for("plan_detail_view", plan_id=plan_id), status_code=status.HTTP_303_SEE_OTHER)

        flash(request, "Semester plan submitted for review.", "success")
    else:
        flash(request, "Semester plan saved as draft.", "success")

    return RedirectResponse(
        url=request.url_for("plan_detail_view", plan_id=plan_id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/app/plans/{plan_id}", response_class=HTMLResponse, name="plan_detail_view")
async def plan_detail_view(request: Request, plan_id: int, user: AuthDep, db: SessionDep):
    student_repo, service = _services(db)
    student = student_repo.get_student_by_user_id(user.id)
    if student is None:
        return RedirectResponse(url=request.url_for("plans_view"), status_code=status.HTTP_303_SEE_OTHER)

    detail = service.get_plan_detail(student.id, plan_id)
    if detail is None:
        flash(request, "That semester plan could not be found.", "danger")
        return RedirectResponse(url=request.url_for("plans_view"), status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request=request,
        name="plan_detail.html",
        context={"user": user, "detail": detail},
    )


@router.get("/app/plans/{plan_id}/edit", response_class=HTMLResponse, name="plan_edit_view")
async def plan_edit_view(request: Request, plan_id: int, user: AuthDep, db: SessionDep):
    student_repo, service = _services(db)
    student = student_repo.get_student_by_user_id(user.id)
    detail = service.get_plan_detail(student.id, plan_id) if student else None
    if detail is None:
        return RedirectResponse(url=request.url_for("plans_view"), status_code=status.HTTP_303_SEE_OTHER)

    selected = [row for row in detail.courses]
    return templates.TemplateResponse(
        request=request,
        name="plan_form.html",
        context={
            "user": user,
            "form": {
                "planID": detail.planID,
                "semester": detail.semester,
                "academicYear": detail.academicYear,
                "submitting": detail.status == "rejected",
                "error": None,
                "selectedCourseIDs": [c.courseID for c in service.get_course_grid(student.id)
                                      if c.code in {r.code for r in selected}],
                "courses": service.get_course_grid(student.id),
            },
        },
    )


@router.post("/app/plans/{plan_id}/resubmit", response_class=HTMLResponse, name="plan_resubmit_action")
async def plan_resubmit_action(request: Request, plan_id: int, user: AuthDep, db: SessionDep):
    student_repo, service = _services(db)
    student = student_repo.get_student_by_user_id(user.id)

    error = service.submit_existing_plan(student.id, plan_id) if student else "No student profile."
    if error:
        flash(request, error, "danger")
    else:
        flash(request, "Semester plan submitted for review.", "success")

    return RedirectResponse(
        url=request.url_for("plan_detail_view", plan_id=plan_id),
        status_code=status.HTTP_303_SEE_OTHER,
    )