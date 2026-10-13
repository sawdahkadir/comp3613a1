"""Advisor review rules — Phase 5, workflow 3.

Holds the Phase 4 decisions about committing a review:
Approve / Reject finalise the per-course chips rather than deciding them,
approval is refused while any course is still pending or rejected, and the
student is notified as part of the same commit.
"""

import logging
from typing import Dict, List, Optional, Tuple

from app.models.review import Notification, PlanReview
from app.repositories.review import ReviewRepository
from app.schemas.review import AdvisorPlanRow, PlanReviewScreen, ReviewPlanRow

logger = logging.getLogger(__name__)

PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"

# The review screen's buttons submit the imperative form; the plan stores the
# past tense. Both spellings map to the stored outcome.
_OUTCOME_FOR_ACTION = {
    "approve": APPROVED,
    APPROVED: APPROVED,
    "reject": REJECTED,
    REJECTED: REJECTED,
}


class ReviewService:
    def __init__(self, repo: ReviewRepository):
        self.repo = repo

    # —— reads the screens need ——

    def list_plans(
        self, advisor_id: int, tab: str = "pending", academic_year: str = "", semester: str = ""
    ) -> Tuple[List[AdvisorPlanRow], List[AdvisorPlanRow]]:
        """Pending and Reviewed rows for this advisor, after the filters."""
        pending_rows, reviewed_rows = self.repo.list_plans_for_advisor(
            advisor_id, statuses=[PENDING, "submitted"]
        ), self.repo.list_plans_for_advisor(advisor_id, statuses=[APPROVED, REJECTED])

        pending = [self._to_row(plan, student) for plan, student in pending_rows]
        reviewed = [self._to_row(plan, student) for plan, student in reviewed_rows]

        if academic_year:
            pending = [r for r in pending if r.academicYear == academic_year]
            reviewed = [r for r in reviewed if r.academicYear == academic_year]
        if semester:
            pending = [r for r in pending if r.semester == semester]
            reviewed = [r for r in reviewed if r.semester == semester]

        return pending, reviewed

    def get_review_screen(self, advisor_id: int, plan_id: int) -> Optional[PlanReviewScreen]:
        plan, student = self._get_advisee_plan(advisor_id, plan_id)
        if plan is None:
            return None
        courses = [
            ReviewPlanRow(
                courseID=course.id,
                code=course.code,
                courseName=course.courseName,
                credits=course.credits,
                decision=row.decision,
                feedback=row.feedback,
            )
            for row, course in self.repo.get_plan_courses(plan.id)
        ]
        return PlanReviewScreen(
            planID=plan.id,
            studentID=student.studentNumber or str(student.id),
            studentName=student.name,
            semester=plan.semester,
            academicYear=plan.academicYear,
            status=plan.status,
            canReview=plan.status == "submitted",
            courses=courses,
        )

    def list_student_notifications(self, student_id: int) -> List[Notification]:
        """Messages addressed to a student, newest first."""
        return self.repo.list_notifications_for_student(student_id)

    def list_advisor_notifications(self, advisor_id: int) -> List[Notification]:
        """Messages addressed to an advisor, newest first."""
        return self.repo.list_notifications_for_advisor(advisor_id)

    # —— the commit —

    def submit_review(
        self,
        advisor_id: int,
        plan_id: int,
        decisions: Dict[int, Tuple[str, str]],
        plan_feedback: str,
        action: str,
    ) -> Optional[str]:
        """Finalise the chips and record the decision. Returns an error, or None."""
        plan, student = self._get_advisee_plan(advisor_id, plan_id)
        if plan is None:
            return "That semester plan is not one of your students'."
        if plan.status != "submitted":
            return "This plan has already been reviewed."

        # The buttons send the imperative ("approve"), the stored states are
        # past tense ("approved"), and a resubmitted plan can also arrive with
        # a past-tense value. Accept both spellings rather than comparing a
        # button's value against a status name and silently skipping the rules.
        outcome = _OUTCOME_FOR_ACTION.get((action or "").strip().lower())
        if outcome is None:
            return "Unknown review action."

        chosen = {course_id: value[0] for course_id, value in decisions.items()}

        # A course with no chip ticked submits no field at all, so "pending"
        # has to be worked out from the courses actually on the plan — not
        # from the ones the form happened to mention.
        on_plan = {course.id for _, course in self.repo.get_plan_courses(plan.id)}
        still_pending = sorted(
            course_id for course_id in on_plan if chosen.get(course_id, PENDING) == PENDING
        )
        rejected_courses = sorted(
            course_id for course_id in on_plan if chosen.get(course_id) == REJECTED
        )

        if outcome == APPROVED:
            if still_pending:
                return "Set a decision on every course before approving this plan."
            if rejected_courses:
                return (
                    "This plan cannot be approved while a course on it is rejected. "
                    "Reject the plan instead."
                )

        for course_id, (decision, feedback) in decisions.items():
            self.repo.set_course_decision(plan.id, course_id, decision, feedback)

        self.repo.set_plan_status(plan.id, outcome)

        self.repo.add_review(
            PlanReview(
                planID=plan.id,
                advisorID=advisor_id,
                decision=outcome,
                feedback=plan_feedback or None,
            )
        )

        # Notify Student is «include»d by Make Decision — same commit.
        self.repo.add_notification(
            Notification(
                studentID=student.id,
                message=self._notification_message(outcome),
            )
        )
        return None

    # —— helpers ——

    def _get_advisee_plan(self, advisor_id: int, plan_id: int):
        plan = self.repo.get_plan(plan_id)
        if plan is None:
            return None, None
        student = self.repo.get_student(plan.studentID)
        if student is None or student.advisorID != advisor_id:
            return None, None
        return plan, student

    def _to_row(self, plan, student) -> AdvisorPlanRow:
        return AdvisorPlanRow(
            planID=plan.id,
            studentID=student.studentNumber or str(student.id),
            studentName=student.name,
            semester=plan.semester,
            academicYear=plan.academicYear,
            status=plan.status,
        )

    def _notification_message(self, outcome: str) -> str:
        if outcome == APPROVED:
            return "Your semester plan has been approved."
        return (
            "One of the courses in your semester plan has been rejected. "
            "Review and resubmit."
        )