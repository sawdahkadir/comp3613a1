from typing import List, Optional

from sqlmodel import SQLModel


class PlanCourse(SQLModel):
    """One row of the checkbox grid on the Create / Edit Semester Plan screen."""

    courseID: int
    code: str
    courseName: str
    credits: int
    alreadyCompleted: bool = False


class PlanSummary(SQLModel):
    """One row of the Bob's Semester Plans table."""

    planID: int
    semester: str
    academicYear: str
    status: str


class PlanCourseRow(SQLModel):
    """One row of the plan detail table, including the advisor's call."""

    code: str
    courseName: str
    credits: int
    decision: str
    feedback: Optional[str] = None


class PlanDetail(SQLModel):
    """Everything the Semester Plan detail screen renders."""

    planID: int
    studentName: str
    semester: str
    academicYear: str
    status: str
    canEdit: bool
    courses: List[PlanCourseRow]


class PlanForm(SQLModel):
    """Everything the Create / Edit Semester Plan screen renders."""

    planID: Optional[int] = None
    semester: str = "1"
    academicYear: str = ""
    submitting: bool = False
    error: Optional[str] = None
    selectedCourseIDs: List[int] = []
    courses: List[PlanCourse] = []