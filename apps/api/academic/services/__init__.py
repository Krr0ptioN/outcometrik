from .assessments import AssessmentService
from .enrollments import EnrollmentService
from .grades import GradeBatchService, GradeService
from .offerings import CourseOfferingService, InstructorAssignmentService
from .outcomes import ProgramOutcomeService, ProgramOutcomeSetService
from .programs import ProgramCourseService, ProgramMembershipService, ProgramService
from .provider import AcademicServiceProvider, academic_service_provider
from .structure import AcademicTermService, CourseService, DepartmentService, InstitutionService
from .syllabi import SyllabusService
from .workspaces import WorkspaceService

__all__ = [
    "AcademicServiceProvider",
    "AcademicTermService",
    "AssessmentService",
    "CourseOfferingService",
    "CourseService",
    "DepartmentService",
    "EnrollmentService",
    "GradeBatchService",
    "GradeService",
    "InstitutionService",
    "InstructorAssignmentService",
    "ProgramCourseService",
    "ProgramMembershipService",
    "ProgramOutcomeService",
    "ProgramOutcomeSetService",
    "ProgramService",
    "SyllabusService",
    "WorkspaceService",
    "academic_service_provider",
]
