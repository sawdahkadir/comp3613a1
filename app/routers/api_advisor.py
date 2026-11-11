"""Advisor-facing JSON endpoints: plan queue, review screen and decisions."""

from typing import Literal

from fastapi import HTTPException, Query, status

from app.dependencies.session import SessionDep
from app.repositories.review import ReviewRepository
from app.schemas.api import PlanDecisionRequest
from app.schemas.review import AdvisorPlanRow, PlanReviewScreen
from app.services.review import ReviewService
from . import api_router
from .api_deps import AdvisorDep, api_error


def _review(db) -> ReviewService:
    return ReviewService(ReviewRepository(db))


@api_router.get(
    "/v1/advisor/plans",
    response_model=list[AdvisorPlanRow],
    name="api_advisor_plans",
)
async def api_advisor_plans(
    advisor: AdvisorDep,
    db: SessionDep,
    status_tab: Literal["pending", "reviewed"] = Query(default="pending", alias="status"),
    academicYear: str = "",
    semester: str = "",
):
    pending, reviewed = _review(db).list_plans(
        advisor.id, status_tab, academicYear, semester
    )
    return pending if status_tab == "pending" else reviewed


@api_router.get(
    "/v1/advisor/plans/{plan_id}",
    response_model=PlanReviewScreen,
    name="api_advisor_plan_detail",
)
async def api_advisor_plan_detail(plan_id: int, advisor: AdvisorDep, db: SessionDep):
    screen = _review(db).get_review_screen(advisor.id, plan_id)
    if screen is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="That semester plan could not be found.",
        )
    return screen


@api_router.post(
    "/v1/advisor/plans/{plan_id}/decision",
    response_model=PlanReviewScreen,
    name="api_advisor_decision",
)
async def api_advisor_decision(
    plan_id: int,
    payload: PlanDecisionRequest,
    advisor: AdvisorDep,
    db: SessionDep,
):
    service = _review(db)
    decisions = {
        course.courseID: (course.decision, course.feedback)
        for course in payload.courses
    }
    error = service.submit_review(
        advisor.id, plan_id, decisions, payload.planFeedback, payload.decision
    )
    if error:
        raise api_error(error)

    screen = service.get_review_screen(advisor.id, plan_id)
    if screen is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="That semester plan could not be found.",
        )
    return screen
