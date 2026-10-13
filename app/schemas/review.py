from typing import List, Optional

from sqlmodel import SQLModel


class ReviewPlanRow(SQLModel):
    """One course on the Review Semester Plan screen."""

    courseID: int
    code: str
    courseName: str
    credits: int
    decision: str
    feedback: Optional[str] = None


class AdvisorPlanRow(SQLModel):
    """One row of the advisor's Semester Plan list."""

    planID: int
    studentID: str
    studentName: str
    semester: str
    academicYear: str
    status: str


class PlanReviewScreen(SQLModel):
    """Everything the Review Semester Plan screen renders."""

    planID: int
    studentID: str
    studentName: str
    semester: str
    academicYear: str
    status: str
    canReview: bool
    courses: List[ReviewPlanRow]