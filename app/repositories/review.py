"""Datastore access for advisor plan review. Queries only."""

from typing import List, Optional, Tuple

from sqlmodel import Session, select

from app.models.planning import SemesterPlan, SemesterPlanCourse
from app.models.progress import Advisor, Course, Student
from app.models.review import Notification, PlanReview


class ReviewRepository:
    def __init__(self, db: Session):
        self.db = db

    # —— reads ——

    def get_advisor_by_user_id(self, user_id: int) -> Optional[Advisor]:
        return self.db.exec(select(Advisor).where(Advisor.userID == user_id)).one_or_none()

    def get_plan(self, plan_id: int) -> Optional[SemesterPlan]:
        return self.db.get(SemesterPlan, plan_id)

    def get_student(self, student_id: int) -> Optional[Student]:
        return self.db.get(Student, student_id)

    def list_plans_for_advisor(
        self, advisor_id: int, statuses: Optional[List[str]] = None
    ) -> List[Tuple[SemesterPlan, Student]]:
        """Plans belonging to this advisor's own students, newest term first."""
        qry = (
            select(SemesterPlan, Student)
            .join(Student, SemesterPlan.studentID == Student.id)
            .where(Student.advisorID == advisor_id)
            .order_by(SemesterPlan.academicYear.desc(), SemesterPlan.semester)
        )
        if statuses:
            qry = qry.where(SemesterPlan.status.in_(statuses))
        return list(self.db.exec(qry).all())

    def get_plan_courses(self, plan_id: int) -> List[Tuple[SemesterPlanCourse, Course]]:
        qry = (
            select(SemesterPlanCourse, Course)
            .join(Course, SemesterPlanCourse.courseID == Course.id)
            .where(SemesterPlanCourse.planID == plan_id)
            .order_by(Course.code)
        )
        return list(self.db.exec(qry).all())

    def list_notifications_for_advisor(self, advisor_id: int) -> List[Notification]:
        return list(
            self.db.exec(
                select(Notification)
                .where(Notification.advisorID == advisor_id)
                .order_by(Notification.date.desc())
            ).all()
        )

    def list_notifications_for_student(self, student_id: int) -> List[Notification]:
        return list(
            self.db.exec(
                select(Notification)
                .where(Notification.studentID == student_id)
                .order_by(Notification.date.desc())
            ).all()
        )

    # —— writes ——

    def set_course_decision(self, plan_id: int, course_id: int, decision: str, feedback: str) -> None:
        row = self.db.exec(
            select(SemesterPlanCourse).where(
                SemesterPlanCourse.planID == plan_id,
                SemesterPlanCourse.courseID == course_id,
            )
        ).one_or_none()
        if row is None:
            return
        row.decision = decision
        row.feedback = feedback or None
        self.db.add(row)
        self.db.commit()

    def set_plan_status(self, plan_id: int, status: str) -> None:
        plan = self.get_plan(plan_id)
        if plan is not None:
            plan.status = status
            self.db.add(plan)
            self.db.commit()

    def add_review(self, review: PlanReview) -> PlanReview:
        self.db.add(review)
        self.db.commit()
        self.db.refresh(review)
        return review

    def add_notification(self, notification: Notification) -> Notification:
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification