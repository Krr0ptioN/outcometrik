from django.contrib import admin

from . import models

for model in (
    models.Institution,
    models.Department,
    models.Program,
    models.AcademicTerm,
    models.Course,
    models.ProgramCourse,
    models.CourseOffering,
    models.ProgramMembership,
    models.InstructorAssignment,
    models.Enrollment,
    models.EnrollmentStatusEvent,
):
    admin.site.register(model)
