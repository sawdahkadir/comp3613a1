"""Degree progress rules — Phase 5, workflow 1.

Holds the arithmetic the View Degree Progress screen shows: which credits
count toward the degree, what is left, and the completion percentage.
"""

import logging
from typing import Optional

from app.repositories.progress import ProgressRepository
from app.schemas.progress import CompletedCourse, DegreeProgress

logger = logging.getLogger(__name__)


class ProgressService:
    def __init__(self, repo: ProgressRepository):
        self.repo = repo

    def get_degree_progress(self, user_id: int) -> Optional[DegreeProgress]:
        """Build the progress figures for the signed-in student.

        Returns None when the login account has no student profile or the
        profile is not enrolled in a degree yet.
        """
        student = self.repo.get_student_by_user_id(user_id)
        if student is None:
            logger.info("No student profile for user %s", user_id)
            return None

        degree = self.repo.get_degree(student.degreeID)
        if degree is None:
            logger.info("Student %s has no degree", student.id)
            return None

        transcript = self.repo.get_completed_transcript(student.id)
        completed = [
            CompletedCourse(code=course.code, courseName=course.courseName, credits=course.credits)
            for _, course in transcript
        ]
        credits_completed = sum(course.credits for course in completed)
        credits_total = degree.totalCredits
        percent = round(credits_completed / credits_total * 100) if credits_total else 0

        return DegreeProgress(
            studentName=student.name,
            degreeName=degree.degreeName,
            faculty=degree.faculty,
            academicYear=student.currentAcademicYear,
            creditsCompleted=credits_completed,
            creditsTotal=credits_total,
            creditsRemaining=max(credits_total - credits_completed, 0),
            percentComplete=percent,
            coursesCompleted=len(completed),
            coursesRequired=self.repo.count_required_courses(degree.id),
            completedCourses=completed,
        )