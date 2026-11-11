from ..serializers import CourseSerializer
from ..services import CourseService
from .base import AcademicController


class CourseController(AcademicController):
    serializer_class = CourseSerializer
    service_class = CourseService
    filter_fields = ("home_department", "code", "active")
