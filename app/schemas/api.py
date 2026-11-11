"""Request/response bodies for the versioned JSON API."""

from typing import List, Literal

from sqlmodel import SQLModel

Semester = Literal["1", "2", "3"]
CourseDecisionValue = Literal["approved", "rejected", "pending"]
ReviewAction = Literal["approve", "reject"]


class LoginResponse(SQLModel):
    """Token and account details returned by ``POST /api/v1/auth/login``."""

    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class PlanCreateRequest(SQLModel):
    semester: Semester
    academicYear: str
    courseIDs: List[int] = []


class PlanUpdateRequest(SQLModel):
    courseIDs: List[int] = []


class CourseDecision(SQLModel):
    courseID: int
    decision: CourseDecisionValue
    feedback: str = ""


class PlanDecisionRequest(SQLModel):
    decision: ReviewAction
    planFeedback: str = ""
    courses: List[CourseDecision] = []
