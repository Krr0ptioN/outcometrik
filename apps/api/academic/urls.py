from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("institutions", views.InstitutionViewSet, basename="institution")
router.register("departments", views.DepartmentViewSet, basename="department")
router.register("programs", views.ProgramViewSet, basename="program")
router.register("terms", views.AcademicTermViewSet, basename="term")
router.register("courses", views.CourseViewSet, basename="course")
router.register("program-courses", views.ProgramCourseViewSet, basename="program-course")
router.register(
    "program-memberships", views.ProgramMembershipViewSet, basename="program-membership"
)
router.register("offerings", views.CourseOfferingViewSet, basename="offering")
router.register(
    "instructor-assignments", views.InstructorAssignmentViewSet, basename="instructor-assignment"
)
router.register("enrollments", views.EnrollmentViewSet, basename="enrollment")

urlpatterns = [
    path("workspaces/instructor/", views.InstructorWorkspaceView.as_view()),
    path("workspaces/student/", views.StudentWorkspaceView.as_view()),
    path("workspaces/coordinator/", views.CoordinatorWorkspaceView.as_view()),
    *router.urls,
]
