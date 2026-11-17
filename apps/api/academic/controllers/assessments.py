from ..serializers import AssessmentSerializer
from ..services.assessments import AssessmentService
from .base import AcademicController


class AssessmentController(AcademicController):
    serializer_class = AssessmentSerializer
    service_class = AssessmentService
    filter_fields = ("offering",)
    http_method_names = ["get", "head", "options"]
