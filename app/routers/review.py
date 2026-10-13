"""Advisor plan review routes — Phase 5, workflow 3."""

from logging import error
from typing import Dict, Tuple

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import status

from app.dependencies.auth import AdminDep
from app.dependencies.session import SessionDep
from app.repositories.review import ReviewRepository
from app.services.review import ReviewService
from app.utilities.flash import flash
from . import router, templates


def _advisor(db, user):
    """Build the repository and service and resolve the signed-in advisor."""
    repo = ReviewRepository(db)
    return repo, ReviewService(repo), repo.get_advisor_by_user_id(user.id)


@router.get("/admin/plans", response_class=HTMLResponse, name="admin_plans_view")
async def admin_plans_view(
    request: Request,
    user: AdminDep,
    db: SessionDep,
    tab: str = "pending",
    academicYear: str = "",
    semester: str = "",
):
    repo, service, advisor = _advisor(db, user)
    if advisor is None:
        flash(request, "This account is not linked to an advisor profile.", "danger")
        return RedirectResponse(url=request.url_for("admin_home_view"), status_code=status.HTTP_303_SEE_OTHER)

    pending, reviewed = service.list_plans(advisor.id, tab, academicYear, semester)

    return templates.TemplateResponse(
        request=request,
        name="admin_plans.html",
        context={
            "user": user,
            "advisor": advisor,
            "tab": tab,
            "academicYear": academicYear,
            "semester": semester,
            "pending": pending,
            "reviewed": reviewed,
            "plans": pending if tab == "pending" else reviewed,
        },
    )


@router.get("/admin/plans/{plan_id}", response_class=HTMLResponse, name="admin_plan_review_view")
async def admin_plan_review_view(request: Request, plan_id: int, user: AdminDep, db: SessionDep):
    repo, service, advisor = _advisor(db, user)
    screen = service.get_review_screen(advisor.id, plan_id) if advisor else None
    if screen is None:
        flash(request, "That semester plan could not be found.", "danger")
        return RedirectResponse(url=request.url_for("admin_plans_view"), status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request=request,
        name="review_plan.html",
        context={"user": user, "screen": screen},
    )


@router.post("/admin/plans/{plan_id}", response_class=HTMLResponse, name="admin_plan_review_action")
async def admin_plan_review_action(
    request: Request,
    plan_id: int,
    user: AdminDep,
    db: SessionDep,
):
    repo, service, advisor = _advisor(db, user)
    if advisor is None:
        flash(request, "This account is not linked to an advisor profile.", "danger")
        return RedirectResponse(url=request.url_for("admin_home_view"), status_code=status.HTTP_303_SEE_OTHER)

    form = await request.form()
    action = form.get("action", "")
    plan_feedback = form.get("planFeedback", "")

    # Each row names its own fields — decision_<courseID> and
    # courseFeedback_<courseID> — so the pair belonging to a course is carried
    # by the key names rather than by the position of two parallel lists.
    # That is what lets a course be left undecided without the two lists
    # drifting out of step.
    course_decisions: Dict[int, Tuple[str, str]] = {}
    for key, value in form.items():
        if not key.startswith("decision_"):
            continue
        try:
            course_id = int(key.removeprefix("decision_"))
        except ValueError:
            continue
        decision = value.strip().lower()
        if decision not in {"approved", "rejected", "pending"}:
            flash(request, "Invalid review submission.", "danger")
            return RedirectResponse(
                url=request.url_for("admin_plan_review_view", plan_id=plan_id),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        course_decisions[course_id] = (decision, form.get(f"courseFeedback_{course_id}", ""))

    error = service.submit_review(advisor.id, plan_id, course_decisions, plan_feedback, action)

    if error:
        flash(request, error, "danger")
        return RedirectResponse(
            url=request.url_for("admin_plan_review_view", plan_id=plan_id),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    flash(request, "Semester plan review submitted.", "success")
    return RedirectResponse(url=request.url_for("admin_plans_view"), status_code=status.HTTP_303_SEE_OTHER)

