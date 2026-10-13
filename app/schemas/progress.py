from sqlmodel import SQLModel


class CompletedCourse(SQLModel):
    """One row of the completed-courses table on the progress screen."""

    code: str
    courseName: str
    credits: int


class DegreeProgress(SQLModel):
    """Everything the View Degree Progress screen renders."""

    studentName: str
    degreeName: str
    faculty: str
    academicYear: str
    creditsCompleted: int
    creditsTotal: int
    creditsRemaining: int
    percentComplete: int
    coursesCompleted: int
    coursesRequired: int
    completedCourses: list[CompletedCourse]