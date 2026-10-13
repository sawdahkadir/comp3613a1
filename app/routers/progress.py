"""Student degree progress routes — Phase 5, workflow 1."""

from fastapi import Request
from fastapi.responses import HTMLResponse

from app.dependencies.auth import AuthDep
from app.dependencies.session import SessionDep
from . import router, templates

from app.repositories.progress import ProgressRepository
from app.services.progress import ProgressService


@router.get("/app/progress", response_class=HTMLResponse, name="progress_view")
async def progress_view(request: Request, user: AuthDep, db: SessionDep):

    repo = ProgressRepository(db)
    service = ProgressService(repo)
    progress = service.get_degree_progress(user.id)

    return templates.TemplateResponse(
        request=request,
        name="progress.html",
        context={
            "user": user,
            "progress": progress,
        },
    )
