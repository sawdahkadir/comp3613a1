"""Semester planning model — Phase 5, workflow 2 (Create Semester Plan).

Maps to SEMESTER_PLAN, SEMESTER_PLAN_COURSE and COURSE_RELATION on the ERD.
"""
from sqlalchemy import UniqueConstraint

from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel

from app.models.progress import Course, Student


class SemesterPlan(SQLModel, table=True):
    """A student's course selection for one semester of one academic year."""

    id: Optional[int] = Field(default=None, primary_key=True)
    semester: str
    academicYear: str
    status: str = Field(default="draft", index=True)

    student: Optional["Student"] = Relationship(back_populates="plans")
    courses: List["SemesterPlanCourse"] = Relationship(back_populates="plan")

    studentID: int = Field(foreign_key="student.id", index=True)

    __table_args__ = (
        UniqueConstraint("studentID", "semester", "academicYear"),
    )


class SemesterPlanCourse(SQLModel, table=True):
    """One course on a semester plan, with the advisor's call on it."""

    planID: int = Field(foreign_key="semesterplan.id", primary_key=True)
    courseID: int = Field(foreign_key="course.id", primary_key=True)

    plan: Optional["SemesterPlan"] = Relationship(back_populates="courses")
    course: Optional["Course"] = Relationship()

    decision: str = Field(default="pending")
    feedback: Optional[str] = Field(default=None)


class CourseRelation(SQLModel, table=True):
    """A prerequisite or antirequisite link between two courses."""

    courseID: int = Field(foreign_key="course.id", primary_key=True)
    relatedCourseID: int = Field(foreign_key="course.id", primary_key=True)
    relationType: str = Field(default="prereq")

    # Both columns below point at `course`, so SQLAlchemy sees two valid join
    # paths and refuses to guess. Each relationship has to name the column it
    # joins on. SQLModel takes this through sa_relationship_kwargs.
    course: Optional["Course"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "CourseRelation.courseID"}
    )
    relatedCourse: Optional["Course"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "CourseRelation.relatedCourseID"}
    )