"""Datastore access for the degree progress screen. Queries only."""

from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.progress import (
    Advisor,
    Course,
    Degree,
    DegreeCourse,
    Student,
    StudentCourse,
)


class ProgressRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_student_by_user_id(self, user_id: int) -> Optional[Student]:
        return self.db.exec(select(Student).where(Student.userID == user_id)).one_or_none()

    def get_degree(self, degree_id: int) -> Optional[Degree]:
        return self.db.get(Degree, degree_id)

    def get_degree_by_name(self, degree_name: str) -> Optional[Degree]:
        return self.db.exec(select(Degree).where(Degree.degreeName == degree_name)).one_or_none()

    def count_required_courses(self, degree_id: int) -> int:
        count_qry = select(func.count()).select_from(DegreeCourse).where(
            DegreeCourse.degreeID == degree_id
        )
        return self.db.exec(count_qry).one()

    def get_completed_transcript(self, student_id: int) -> List[Tuple[StudentCourse, Course]]:
        """Completed transcript rows joined to their course."""
        qry = (
            select(StudentCourse, Course)
            .join(Course, StudentCourse.courseID == Course.id)
            .where(
                StudentCourse.studentID == student_id,
                StudentCourse.status == "completed",
            )
            .order_by(Course.code)
        )
        return list(self.db.exec(qry).all())

    # —— writes, used by the demo seeder and by transcript maintenance ——

    def create_degree(self, degree: Degree) -> Degree:
        self.db.add(degree)
        self.db.commit()
        self.db.refresh(degree)
        return degree

    def create_course(self, course: Course) -> Course:
        self.db.add(course)
        self.db.commit()
        self.db.refresh(course)
        return course

    def get_course_by_code(self, code: str) -> Optional[Course]:
        return self.db.exec(select(Course).where(Course.code == code)).one_or_none()

    def create_advisor(self, advisor: Advisor) -> Advisor:
        self.db.add(advisor)
        self.db.commit()
        self.db.refresh(advisor)
        return advisor

    def create_student(self, student: Student) -> Student:
        self.db.add(student)
        self.db.commit()
        self.db.refresh(student)
        return student

    def get_student_by_name(self, name: str) -> Optional[Student]:
        return self.db.exec(select(Student).where(Student.name == name)).one_or_none()

    def get_advisor_by_name(self, name: str) -> Optional[Advisor]:
        return self.db.exec(select(Advisor).where(Advisor.name == name)).one_or_none()

    def require_course(self, degree_id: int, course_id: int, requirement_type: str = "core") -> None:
        """Record that a degree requires a course. Duplicate pairs are skipped."""
        existing = self.db.exec(
            select(DegreeCourse).where(
                DegreeCourse.degreeID == degree_id,
                DegreeCourse.courseID == course_id,
            )
        ).one_or_none()
        if existing:
            return
        self.db.add(
            DegreeCourse(degreeID=degree_id, courseID=course_id, requirementType=requirement_type)
        )
        self.db.commit()

    def record_transcript(self, student_id: int, course_id: int, status: str) -> None:
        """Record a transcript outcome for a student, replacing any earlier one."""
        row = self.db.exec(
            select(StudentCourse).where(
                StudentCourse.studentID == student_id,
                StudentCourse.courseID == course_id,
            )
        ).one_or_none()
        if row is None:
            row = StudentCourse(studentID=student_id, courseID=course_id)
        row.status = status
        self.db.add(row)
        self.db.commit()