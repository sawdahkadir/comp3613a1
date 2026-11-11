"""Bearer-token authentication and shared plumbing for the JSON API.

The HTML app keeps reading the ``access_token`` cookie; the API reads the same
JWT from an ``Authorization: Bearer`` header, so both share one token format
without changing the browser flows.
"""

from typing import Annotated, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError

from app.config import get_settings
from app.dependencies.session import SessionDep
from app.models.progress import Advisor, Student
from app.models.user import User
from app.repositories.progress import ProgressRepository
from app.repositories.review import ReviewRepository
from app.repositories.user import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)


def credentials_error(detail: str = "Could not validate credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_api_user(
    db: SessionDep,
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)
    ],
) -> User:
    """Resolve the signed-in account from the Bearer token."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise credentials_error()

    try:
        payload = jwt.decode(
            credentials.credentials,
            get_settings().secret_key,
            algorithms=[get_settings().jwt_algorithm],
        )
        user_id = int(payload.get("sub"))
    except (InvalidTokenError, TypeError, ValueError):
        raise credentials_error()

    user = UserRepository(db).get_by_id(user_id)
    if user is None:
        raise credentials_error()
    return user


ApiUser = Annotated[User, Depends(get_api_user)]


async def get_api_student(user: ApiUser, db: SessionDep) -> Student:
    """Resolve the student profile that belongs to the signed-in account."""
    student = ProgressRepository(db).get_student_by_user_id(user.id)
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No student profile is linked to this account.",
        )
    return student


StudentDep = Annotated[Student, Depends(get_api_student)]


async def get_api_advisor(user: ApiUser, db: SessionDep) -> Advisor:
    """Resolve the advisor profile; only admin accounts may use advisor routes."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only available to advisors.",
        )
    advisor = ReviewRepository(db).get_advisor_by_user_id(user.id)
    if advisor is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not linked to an advisor profile.",
        )
    return advisor


AdvisorDep = Annotated[Advisor, Depends(get_api_advisor)]


def api_error(message: str) -> HTTPException:
    """Translate a service rule message into the matching HTTP status."""
    text = (message or "").lower()
    if (
        "already have a plan" in text
        or "already been reviewed" in text
        or "only a draft or a rejected plan" in text
    ):
        code = status.HTTP_409_CONFLICT
    elif "does not belong to you" in text or "not one of your students" in text:
        code = status.HTTP_404_NOT_FOUND
    else:
        code = status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=code, detail=message)
