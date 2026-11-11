"""Student-facing JSON endpoints: progress, catalogue and semester plans."""

from fastapi import HTTPException, Response, status

from app.dependencies.session import SessionDep
from app.repositories.planning import PlanningRepository
from app.repositories.progress import ProgressRepository
from app.schemas.api import PlanCreateRequest, PlanUpdateRequest
from app.schemas.planning import PlanCourse, PlanDetail, PlanSummary
from app.schemas.progress import DegreeProgress
from app.services.planning import PlanningService
from app.services.progress import ProgressService
from . import api_router
from .api_deps import ApiUser, StudentDep, api_error


def _planning(db) -> PlanningService:
    return PlanningService(PlanningRepository(db))


@api_router.get(
    "/v1/students/me/progress",
    response_model=DegreeProgress,
    name="api_progress",
)
async def api_progress(user: ApiUser, db: SessionDep):
    progress = ProgressService(ProgressRepository(db)).get_degree_progress(user.id)
    if progress is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No degree is linked to this account.",
        )
    return progress


@api_router.get("/v1/courses", response_model=list[PlanCourse], name="api_courses")
async def api_courses(student: StudentDep, db: SessionDep):
    return _planning(db).get_course_grid(student.id)


@api_router.get("/v1/plans", response_model=list[PlanSummary], name="api_plans")
async def api_plans(student: StudentDep, db: SessionDep):
    return _planning(db).list_plans(student.id)


@api_router.post(
    "/v1/plans",
    response_model=PlanDetail,
    status_code=status.HTTP_201_CREATED,
    name="api_plan_create",
)
async def api_plan_create(
    payload: PlanCreateRequest,
    student: StudentDep,
    db: SessionDep,
    response: Response,
):
    service = _planning(db)
    plan_id, error = service.create_plan(
        student.id, payload.semester, payload.academicYear, payload.courseIDs
    )
    if error:
        raise api_error(error)

    detail = service.get_plan_detail(student.id, plan_id)
    response.headers["Location"] = f"/api/v1/plans/{plan_id}"
    return detail


@api_router.get(
    "/v1/plans/{plan_id}",
    response_model=PlanDetail,
    name="api_plan_detail",
)
async def api_plan_detail(plan_id: int, student: StudentDep, db: SessionDep):
    detail = _planning(db).get_plan_detail(student.id, plan_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="That semester plan could not be found.",
        )
    return detail


@api_router.patch(
    "/v1/plans/{plan_id}",
    response_model=PlanDetail,
    name="api_plan_update",
)
async def api_plan_update(
    plan_id: int,
    payload: PlanUpdateRequest,
    student: StudentDep,
    db: SessionDep,
):
    service = _planning(db)
    error = service.update_plan(student.id, plan_id, payload.courseIDs, submit=False)
    if error:
        raise api_error(error)

    detail = service.get_plan_detail(student.id, plan_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="That semester plan could not be found.",
        )
    return detail


@api_router.post(
    "/v1/plans/{plan_id}/submit",
    response_model=PlanDetail,
    name="api_plan_submit",
)
async def api_plan_submit(plan_id: int, student: StudentDep, db: SessionDep):
    service = _planning(db)
    error = service.submit_existing_plan(student.id, plan_id)
    if error:
        raise api_error(error)

    detail = service.get_plan_detail(student.id, plan_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="That semester plan could not be found.",
        )
    return detail
