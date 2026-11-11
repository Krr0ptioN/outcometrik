from .courses import CourseController
from .departments import DepartmentController
from .enrollments import EnrollmentController
from .institutions import InstitutionController
from .instructor_assignments import InstructorAssignmentController
from .offerings import CourseOfferingController
from .program_courses import ProgramCourseController
from .program_memberships import ProgramMembershipController
from .programs import ProgramController
from .terms import AcademicTermController
from .workspaces import (
    CoordinatorWorkspaceController,
    InstructorWorkspaceController,
    StudentWorkspaceController,
)

__all__ = [
    "AcademicTermController",
    "CoordinatorWorkspaceController",
    "CourseController",
    "CourseOfferingController",
    "DepartmentController",
    "EnrollmentController",
    "InstitutionController",
    "InstructorAssignmentController",
    "InstructorWorkspaceController",
    "ProgramController",
    "ProgramCourseController",
    "ProgramMembershipController",
    "StudentWorkspaceController",
]
