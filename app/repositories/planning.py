"""Datastore access for semester plans. Queries only."""

from typing import List, Optional, Tuple

from sqlmodel import Session, select

from app.models.planning import CourseRelation, SemesterPlan, SemesterPlanCourse
from app.models.progress import Course, StudentCourse


class PlanningRepository:
    def __init__(self, db: Session):
        self.db = db

    # —— reads ——

    def get_plan(self, plan_id: int) -> Optional[SemesterPlan]:
        return self.db.get(SemesterPlan, plan_id)

    def find_plan(self, student_id: int, semester: str, academic_year: str) -> Optional[SemesterPlan]:
        return self.db.exec(
            select(SemesterPlan).where(
                SemesterPlan.studentID == student_id,
                SemesterPlan.semester == semester,
                SemesterPlan.academicYear == academic_year,
            )
        ).one_or_none()

    def list_plans_for_student(self, student_id: int) -> List[SemesterPlan]:
        return list(
            self.db.exec(
                select(SemesterPlan)
                .where(SemesterPlan.studentID == student_id)
                .order_by(SemesterPlan.academicYear.desc(), SemesterPlan.semester)
            ).all()
        )

    def list_all_courses(self) -> List[Course]:
        return list(self.db.exec(select(Course).order_by(Course.code)).all())

    def get_plan_course_ids(self, plan_id: int) -> List[int]:
        rows = self.db.exec(
            select(SemesterPlanCourse.courseID).where(SemesterPlanCourse.planID == plan_id)
        ).all()
        return list(rows)

    def get_plan_courses(self, plan_id: int) -> List[Tuple[SemesterPlanCourse, Course]]:
        qry = (
            select(SemesterPlanCourse, Course)
            .join(Course, SemesterPlanCourse.courseID == Course.id)
            .where(SemesterPlanCourse.planID == plan_id)
            .order_by(Course.code)
        )
        return list(self.db.exec(qry).all())

    def get_completed_course_ids(self, student_id: int) -> List[int]:
        rows = self.db.exec(
            select(StudentCourse.courseID).where(
                StudentCourse.studentID == student_id,
                StudentCourse.status == "completed",
            )
        ).all()
        return list(rows)

    def get_prerequisite_codes(self, course_id: int) -> List[str]:
        """Codes of the courses that must be completed before *course_id*."""
        qry = (
            select(Course.code)
            .join(CourseRelation, CourseRelation.relatedCourseID == Course.id)
            .where(
                CourseRelation.courseID == course_id,
                CourseRelation.relationType == "prereq",
            )
            .order_by(Course.code)
        )
        return list(self.db.exec(qry).all())

    # —— writes ——

    def create_plan(self, plan: SemesterPlan, course_ids: List[int]) -> SemesterPlan:
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        self.replace_plan_courses(plan.id, course_ids)
        return plan

    def replace_plan_courses(self, plan_id: int, course_ids: List[int]) -> None:
        """Make the plan's course rows exactly *course_ids*.

        Rows are rebuilt rather than updated, so every decision starts back at
        pending — that is what stops a resubmitted plan showing stale calls.
        """
        for existing in self.db.exec(
            select(SemesterPlanCourse).where(SemesterPlanCourse.planID == plan_id)
        ).all():
            self.db.delete(existing)
        for course_id in course_ids:
            self.db.add(SemesterPlanCourse(planID=plan_id, courseID=course_id))
        self.db.commit()

    def set_plan_status(self, plan_id: int, status: str) -> None:
        plan = self.get_plan(plan_id)
        if plan is not None:
            plan.status = status
            self.db.add(plan)
            self.db.commit()

    def clear_feedback(self, plan_id: int) -> None:
        rows = self.db.exec(
            select(SemesterPlanCourse).where(SemesterPlanCourse.planID == plan_id)
        ).all()
        for row in rows:
            row.feedback = None
            self.db.add(row)
        self.db.commit()

    def set_course_decision(
        self, plan_id: int, course_id: int, decision: str, feedback: str = ""
    ) -> None:
        """Record the advisor's call on one course of a plan."""
        row = self.db.exec(
            select(SemesterPlanCourse).where(
                SemesterPlanCourse.planID == plan_id,
                SemesterPlanCourse.courseID == course_id,
            )
        ).one_or_none()
        if row is None:
            row = SemesterPlanCourse(planID=plan_id, courseID=course_id)
        row.decision = decision
        row.feedback = feedback
        self.db.add(row)
        self.db.commit()

    def add_prerequisite(self, course_id: int, prereq_course_id: int) -> None:
        """Record that course_id cannot be taken before prereq_course_id."""
        existing = self.db.exec(
            select(CourseRelation).where(
                CourseRelation.courseID == course_id,
                CourseRelation.relatedCourseID == prereq_course_id,
                CourseRelation.relationType == "prereq",
            )
        ).one_or_none()
        if existing:
            return
        self.db.add(
            CourseRelation(courseID=course_id, relatedCourseID=prereq_course_id, relationType="prereq")
        )
        self.db.commit()