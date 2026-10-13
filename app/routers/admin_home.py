from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import status

from app.dependencies.session import SessionDep
from app.dependencies.auth import AdminDep
from app.repositories.review import ReviewRepository
from app.services.review import ReviewService
from . import router, templates


@router.get("/admin", response_class=HTMLResponse)
async def admin_home_view(
    request: Request,
    user: AdminDep,
    db: SessionDep
):
    repo = ReviewRepository(db)
    service = ReviewService(repo)
    advisor = repo.get_advisor_by_user_id(user.id)
    if advisor is None:
        return RedirectResponse(url=request.url_for("index_view"), status_code=status.HTTP_303_SEE_OTHER)

    pending, _ = service.list_plans(advisor.id, "pending")

    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "user": user,
            "advisor": advisor,
            "notifications": service.list_advisor_notifications(advisor.id),
            "pendingCount": len(pending),
        }
    )