"""Semester plan rules — Phase 5, workflow 2.

Holds the Phase 3 / Phase 4 decisions about who may plan what:
one plan per student per term, prerequisites must already be completed,
and submitting clears stale advisor decisions.
"""

import logging
from typing import List, Optional

from app.models.planning import SemesterPlan
from app.repositories.planning import PlanningRepository
from app.schemas.planning import PlanCourse, PlanCourseRow, PlanDetail, PlanSummary

logger = logging.getLogger(__name__)


class PlanningService:
    def __init__(self, repo: PlanningRepository):
        self.repo = repo

    # —— reads the screens need ——

    def list_plans(self, student_id: int) -> List[PlanSummary]:
        return [
            PlanSummary(
                planID=plan.id,
                semester=plan.semester,
                academicYear=plan.academicYear,
                status=plan.status,
            )
            for plan in self.repo.list_plans_for_student(student_id)
        ]

    def get_course_grid(self, student_id: int) -> List[PlanCourse]:
        """The whole course catalogue, flagged where already completed."""
        completed = set(self.repo.get_completed_course_ids(student_id))
        return [
            PlanCourse(
                courseID=course.id,
                code=course.code,
                courseName=course.courseName,
                credits=course.credits,
                alreadyCompleted=course.id in completed,
            )
            for course in self.repo.list_all_courses()
        ]

    def get_plan_detail(self, student_id: int, plan_id: int) -> Optional[PlanDetail]:
        plan = self._get_own_plan(student_id, plan_id)
        if plan is None:
            return None
        rows = [
            PlanCourseRow(
                code=course.code,
                courseName=course.courseName,
                credits=course.credits,
                decision=row.decision,
                feedback=row.feedback,
            )
            for row, course in self.repo.get_plan_courses(plan.id)
        ]
        return PlanDetail(
            planID=plan.id,
            studentName=plan.student.name if plan.student else "",
            semester=plan.semester,
            academicYear=plan.academicYear,
            status=plan.status,
            canEdit=plan.status in ("draft", "rejected"),
            courses=rows,
        )

    # —— writes the rules gate ——

    def create_plan(
        self, student_id: int, semester: str, academic_year: str, course_ids: List[int]
    ) -> tuple[Optional[int], Optional[str]]:
        """Save a draft or submit a new plan.

        Returns (plan_id, error_message). The plan is only written once every
        rule below passes.
        """
        if not course_ids:
            return None, "Select at least one course before saving the plan."

        if self.repo.find_plan(student_id, semester, academic_year) is not None:
            return None, (
                f"You already have a plan for Semester {semester} of "
                f"{academic_year}. Edit that plan instead."
            )

        unmet = self._unmet_prerequisites(student_id, course_ids)
        if unmet:
            return None, unmet

        plan = SemesterPlan(
            studentID=student_id, semester=semester, academicYear=academic_year
        )
        self.repo.create_plan(plan, course_ids)
        return plan.id, None

    def save_draft(
        self, student_id: int, semester: str, academic_year: str, course_ids: List[int]
    ) -> tuple[Optional[int], Optional[str]]:
        """Create the plan, or overwrite an existing draft for the same term."""
        plan_id, error = self.create_plan(student_id, semester, academic_year, course_ids)
        if plan_id is not None or error is not None:
            return plan_id, error

        existing = self.repo.find_plan(student_id, semester, academic_year)
        if existing is None or existing.status != "draft":
            return None, "Only a draft plan can be edited."
        if self._unmet_prerequisites(student_id, course_ids):
            return None, self._unmet_prerequisites(student_id, course_ids)
        self.repo.replace_plan_courses(existing.id, course_ids)
        return existing.id, None

    def update_plan(
        self,
        student_id: int,
        plan_id: int,
        course_ids: List[int],
        submit: bool,
    ) -> Optional[str]:
        """Save an edited plan, then optionally send it for review.

        Allowed while the plan is a draft or was sent back. Rebuilding the
        course rows is what resets every decision to pending and clears the
        feedback, so an edited resubmission never shows stale calls.
        """
        plan = self._get_own_plan(student_id, plan_id)
        if plan is None:
            return "That plan does not belong to you."
        if plan.status not in ("draft", "rejected"):
            return "Only a draft or a rejected plan can be edited."
        if not course_ids:
            return "Select at least one course before saving the plan."

        unmet = self._unmet_prerequisites(student_id, course_ids)
        if unmet:
            return unmet

        self.repo.replace_plan_courses(plan_id, course_ids)
        self.repo.set_plan_status(plan_id, "submitted" if submit else "draft")
        return None

    def submit_existing_plan(self, student_id: int, plan_id: int) -> Optional[str]:
        """Resubmit a plan the advisor sent back, clearing stale decisions."""
        plan = self._get_own_plan(student_id, plan_id)
        if plan is None:
            return "That plan does not belong to you."
        if plan.status not in ("draft", "rejected"):
            return None
        if plan.status == "rejected":
            self.repo.replace_plan_courses(plan.id, self.repo.get_plan_course_ids(plan.id))
            self.repo.clear_feedback(plan.id)
        self.repo.set_plan_status(plan.id, "submitted")
        return None

    # —— helpers ——

    def _get_own_plan(self, student_id: int, plan_id: int) -> Optional[SemesterPlan]:
        plan = self.repo.get_plan(plan_id)
        if plan is None or plan.studentID != student_id:
            return None
        return plan

    def _unmet_prerequisites(self, student_id: int, course_ids: List[int]) -> Optional[str]:
        """One message naming every course blocked by an incomplete prerequisite."""
        completed = set(self.repo.get_completed_course_ids(student_id))
        by_code = {course.code: course.id for course in self.repo.list_all_courses()}
        blocked: List[str] = []
        for course_id in course_ids:
            for prereq_code in self.repo.get_prerequisite_codes(course_id):
                prereq_id = by_code.get(prereq_code)
                if prereq_id is not None and prereq_id not in completed:
                    blocked.append(f"{prereq_code} must be completed first")
        if not blocked:
            return None
        return "Prerequisite not completed — " + "; ".join(sorted(set(blocked)))