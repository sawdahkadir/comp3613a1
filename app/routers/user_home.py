from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import status
from app.dependencies.session import SessionDep
from app.dependencies.auth import AuthDep, IsUserLoggedIn, get_current_user, is_admin
from app.services.progress import ProgressService
from app.services.review import ReviewService
from app.repositories.progress import ProgressRepository
from app.repositories.review import ReviewRepository
from . import router, templates


@router.get("/app", response_class=HTMLResponse)
async def user_home_view(
    request: Request,
    user: AuthDep,
    db:SessionDep
):
    repo = ProgressRepository(db)
    service = ProgressService(repo)
    review_service = ReviewService(ReviewRepository(db))

    student = repo.get_student_by_user_id(user.id)

    return templates.TemplateResponse(
        request=request, 
        name="app.html",
        context={
            "user": user,
            "progress": service.get_degree_progress(user.id),
            "notifications": review_service.list_student_notifications(student.id) if student else [],
        }
    )