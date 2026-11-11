from django.urls import path
from rest_framework.routers import SimpleRouter

from .controllers import (
    AcademicTermController,
    CoordinatorWorkspaceController,
    CourseController,
    CourseOfferingController,
    DepartmentController,
    EnrollmentController,
    InstitutionController,
    InstructorAssignmentController,
    InstructorWorkspaceController,
    ProgramController,
    ProgramCourseController,
    ProgramMembershipController,
    StudentWorkspaceController,
)

router = SimpleRouter()
router.register("institutions", InstitutionController, basename="institution")
router.register("departments", DepartmentController, basename="department")
router.register("programs", ProgramController, basename="program")
router.register("terms", AcademicTermController, basename="term")
router.register("courses", CourseController, basename="course")
router.register("program-courses", ProgramCourseController, basename="program-course")
router.register("program-memberships", ProgramMembershipController, basename="program-membership")
router.register("offerings", CourseOfferingController, basename="offering")
router.register(
    "instructor-assignments", InstructorAssignmentController, basename="instructor-assignment"
)
router.register("enrollments", EnrollmentController, basename="enrollment")

urlpatterns = [
    path("workspaces/instructor/", InstructorWorkspaceController.as_view()),
    path("workspaces/student/", StudentWorkspaceController.as_view()),
    path("workspaces/coordinator/", CoordinatorWorkspaceController.as_view()),
    *router.urls,
]
