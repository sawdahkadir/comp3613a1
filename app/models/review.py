"""Advisor review model — Phase 5, workflow 3 (View Semester Plan / Make Decision).

Maps to PLAN_REVIEW and NOTIFICATION on the ERD.
"""

from datetime import datetime
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel

from app.models.planning import SemesterPlan
from app.models.progress import Advisor, Student


class PlanReview(SQLModel, table=True):
    """One decision an advisor made on a plan — the history row.

    A plan collects many of these across reject → edit → resubmit cycles. The
    plan's current state is read from SemesterPlan.status, never from the most
    recent review.
    """

    planID: int = Field(foreign_key="semesterplan.id", index=True)
    advisorID: int = Field(foreign_key="advisor.id", index=True)

    plan: Optional["SemesterPlan"] = Relationship()
    advisor: Optional["Advisor"] = Relationship()

    id: Optional[int] = Field(default=None, primary_key=True)
    decision: str = Field(default="pending", index=True)
    feedback: Optional[str] = Field(default=None)
    date: datetime = Field(default_factory=datetime.now, index=True)


class Notification(SQLModel, table=True):
    """A message shown on a dashboard — to a student or to an advisor.

    Exactly one of studentID / advisorID is set: the row belongs to whoever it
    was addressed to.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    message: str
    date: datetime = Field(default_factory=datetime.now, index=True)

    studentID: Optional[int] = Field(default=None, foreign_key="student.id", index=True)
    advisorID: Optional[int] = Field(default=None, foreign_key="advisor.id", index=True)

    student: Optional["Student"] = Relationship()
    advisor: Optional["Advisor"] = Relationship()