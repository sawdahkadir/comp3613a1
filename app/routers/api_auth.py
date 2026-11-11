"""JSON login for the versioned API. Returns a Bearer token, not a cookie."""

from fastapi import HTTPException, status

from app.dependencies.session import SessionDep
from app.repositories.user import UserRepository
from app.schemas.api import LoginResponse
from app.schemas.auth import SigninRequest
from app.services.auth_service import AuthService
from . import api_router


@api_router.post("/v1/auth/login", response_model=LoginResponse, name="api_login")
async def api_login(payload: SigninRequest, db: SessionDep):
    repo = UserRepository(db)
    token = AuthService(repo).authenticate_user(payload.username, payload.password)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = repo.get_by_username(payload.username)
    return LoginResponse(
        access_token=token,
        username=user.username,
        role=user.role,
    )
