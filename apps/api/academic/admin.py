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
    models.Syllabus,
    models.LearningOutcome,
    models.SyllabusAssessment,
    models.Assessment,
    models.ProgramOutcomeSet,
    models.ProgramOutcome,
):
    admin.site.register(model)
