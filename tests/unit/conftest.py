"""Shared fixtures for the unit tests.

Each test gets its own in-memory SQLite database, so the tests never touch the
local ``database.db`` file. The ``make`` fixture provides small factory helpers
for the SQLModel tables the services work with.
"""

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401  registers every table on SQLModel.metadata
from app.models.planning import CourseRelation, SemesterPlan, SemesterPlanCourse
from app.models.progress import (
    Advisor,
    Course,
    Degree,
    DegreeCourse,
    Student,
    StudentCourse,
)
from app.models.user import User
from app.utilities.security import encrypt_password


class Factories:
    """Small helpers that persist one row and return the refreshed object."""

    def __init__(self, session: Session):
        self.session = session
        self._user_seq = 0
        self._course_seq = 0

    def _save(self, row):
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def user(
        self,
        username: str | None = None,
        password: str = "secret123",
        role: str = "regular_user",
        email: str | None = None,
    ) -> User:
        if username is None:
            self._user_seq += 1
            username = f"user{self._user_seq}"
        if email is None:
            email = f"{username}@example.com"
        return self._save(
            User(
                username=username,
                email=email,
                password=encrypt_password(password),
                role=role,
            )
        )

    def degree(
        self,
        name: str = "BSc Computer Science",
        faculty: str = "Science",
        total_credits: int = 93,
    ) -> Degree:
        return self._save(
            Degree(degreeName=name, faculty=faculty, totalCredits=total_credits)
        )

    def course(
        self,
        code: str | None = None,
        name: str | None = None,
        credits: int = 3,
    ) -> Course:
        if code is None:
            self._course_seq += 1
            code = f"TEST{self._course_seq}"
        if name is None:
            name = f"Course {code}"
        return self._save(Course(code=code, courseName=name, credits=credits))

    def advisor(
        self,
        name: str = "Dr. Ada Lovelace",
        faculty: str = "Science",
        user: User | None = None,
    ) -> Advisor:
        return self._save(
            Advisor(
                userID=user.id if user is not None else None,
                name=name,
                faculty=faculty,
            )
        )

    def student(
        self,
        user: User | None = None,
        degree: Degree | None = None,
        name: str = "Bob Student",
        advisor: Advisor | None = None,
        academic_year: str = "2025/2026",
        student_number: str | None = None,
    ) -> Student:
        if degree is None:
            degree = self.degree()
        return self._save(
            Student(
                userID=user.id if user is not None else None,
                studentNumber=student_number,
                name=name,
                currentAcademicYear=academic_year,
                degreeID=degree.id,
                advisorID=advisor.id if advisor is not None else None,
            )
        )

    def complete(
        self,
        student: Student,
        course: Course,
        status: str = "completed",
    ) -> StudentCourse:
        return self._save(
            StudentCourse(studentID=student.id, courseID=course.id, status=status)
        )

    def require(
        self,
        degree: Degree,
        course: Course,
        requirement_type: str = "core",
    ) -> DegreeCourse:
        return self._save(
            DegreeCourse(
                degreeID=degree.id,
                courseID=course.id,
                requirementType=requirement_type,
            )
        )

    def prerequisite(self, course: Course, prereq: Course) -> CourseRelation:
        return self._save(
            CourseRelation(
                courseID=course.id,
                relatedCourseID=prereq.id,
                relationType="prereq",
            )
        )

    def plan(
        self,
        student: Student,
        semester: str = "1",
        academic_year: str = "2025/2026",
        status: str = "draft",
        courses=(),
    ) -> SemesterPlan:
        plan = self._save(
            SemesterPlan(
                studentID=student.id,
                semester=semester,
                academicYear=academic_year,
                status=status,
            )
        )
        for course in courses:
            self._save(SemesterPlanCourse(planID=plan.id, courseID=course.id))
        return plan


@pytest.fixture()
def engine():
    """A fresh in-memory database for one test."""
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(test_engine)
    yield test_engine
    SQLModel.metadata.drop_all(test_engine)
    test_engine.dispose()


@pytest.fixture()
def session(engine):
    with Session(engine) as db_session:
        yield db_session


@pytest.fixture()
def make(session):
    return Factories(session)
