from .enrollments import EnrollmentService
from .offerings import CourseOfferingService, InstructorAssignmentService
from .programs import ProgramCourseService, ProgramMembershipService, ProgramService
from .provider import AcademicServiceProvider, academic_service_provider
from .structure import AcademicTermService, CourseService, DepartmentService, InstitutionService
from .syllabi import SyllabusService
from .workspaces import WorkspaceService

__all__ = [
    "AcademicServiceProvider",
    "AcademicTermService",
    "CourseOfferingService",
    "CourseService",
    "DepartmentService",
    "EnrollmentService",
    "InstitutionService",
    "InstructorAssignmentService",
    "ProgramCourseService",
    "ProgramMembershipService",
    "ProgramService",
    "SyllabusService",
    "WorkspaceService",
    "academic_service_provider",
]
