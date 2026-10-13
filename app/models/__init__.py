"""Database table models.

Import every table model here so ``SQLModel.metadata.create_all`` sees them.
"""

from app.models.user import User
from app.models.progress import (
    Advisor,
    Course,
    Degree,
    DegreeCourse,
    Student,
    StudentCourse,
)
from app.models.planning import (
    CourseRelation,
    SemesterPlan,
    SemesterPlanCourse,
)
from app.models.review import Notification, PlanReview

__all__ = [
    "User",
    "Advisor",
    "Course",
    "Degree",
    "DegreeCourse",
    "Student",
    "StudentCourse",
    "CourseRelation",
    "SemesterPlan",
    "SemesterPlanCourse",
    "Notification",
    "PlanReview",
]
