"""Degree progress model — Phase 5, workflow 1 (Track Degree Progress).

Tables here map to STUDENT, ADVISOR, DEGREE, COURSE, DEGREE_COURSE and
STUDENT_COURSE on the Phase 3 ERD, plus the Phase 5 revision that ties a
STUDENT / ADVISOR row to the login account that signs in.
"""

from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


class Degree(SQLModel, table=True):
    """A degree programme a student is enrolled in."""

    id: Optional[int] = Field(default=None, primary_key=True)
    degreeName: str
    faculty: str
    totalCredits: int

    students: List["Student"] = Relationship(back_populates="degree")
    required_courses: List["DegreeCourse"] = Relationship(back_populates="degree")


class Course(SQLModel, table=True):
    """A course offered by the faculty, identified in the app by its code."""

    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)
    courseName: str
    credits: int

    required_by: List["DegreeCourse"] = Relationship(back_populates="course")


class Advisor(SQLModel, table=True):
    """The advisor who reviews a student's semester plans."""

    id: Optional[int] = Field(default=None, primary_key=True)
    userID: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    name: str
    faculty: str

    students: List["Student"] = Relationship(back_populates="advisor")


class Student(SQLModel, table=True):
    """A student, signed in through a login account, enrolled in one degree."""

    id: Optional[int] = Field(default=None, primary_key=True)
    userID: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    studentNumber: Optional[str] = Field(default=None, index=True)
    name: str
    currentAcademicYear: str

    degree: Optional["Degree"] = Relationship(back_populates="students")
    advisor: Optional["Advisor"] = Relationship(back_populates="students")
    transcript: List["StudentCourse"] = Relationship(back_populates="student")
    plans: List["SemesterPlan"] = Relationship(back_populates="student")

    # ===== student-build gap (model 1 of 2) ==================================
    # Two foreign keys are missing from this table:
    #   * the degree this student is enrolled in — required;
    #   * the advisor assigned to this student — optional, a student may not
    #     have one yet.
    # Add them as columns. The relationship attributes above already exist.

    degreeID: int = Field(foreign_key="degree.id", index=True)
    advisorID: Optional[int] = Field(default=None, foreign_key="advisor.id", index=True)
    # ========================================================================


class DegreeCourse(SQLModel, table=True):
    """A course required by a degree — the many-to-many bridge."""

    degreeID: int = Field(foreign_key="degree.id", primary_key=True)
    courseID: int = Field(foreign_key="course.id", primary_key=True)
    requirementType: str = "core"

    degree: Optional["Degree"] = Relationship(back_populates="required_courses")
    course: Optional["Course"] = Relationship(back_populates="required_by")


class StudentCourse(SQLModel, table=True):
    """One row of a student's transcript."""

    status: str = Field(default="in_progress", index=True)

    student: Optional["Student"] = Relationship(back_populates="transcript")
    course: Optional["Course"] = Relationship()

    # ===== student-build gap (model 2 of 2) ==================================
    # Two foreign keys are missing from this table:
    #   * the student this transcript row belongs to;
    #   * the course the row is about.
    # A student takes a given course once, so together they identify the row.

    studentID: int = Field(foreign_key="student.id", primary_key=True)
    courseID: int = Field(foreign_key="course.id", primary_key=True)
    # ========================================================================


# Imported at the bottom, after every class here exists, so the planning and
# review models register with SQLModel without a circular import and the
# Student relationships to them resolve.
import app.models.planning  # noqa: E402,F401  isort:skip
import app.models.review  # noqa: E402,F401  isort:skip