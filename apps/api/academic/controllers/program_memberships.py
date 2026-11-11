from ..serializers import ProgramMembershipSerializer
from ..services import ProgramMembershipService
from .base import AcademicController


class ProgramMembershipController(AcademicController):
    serializer_class = ProgramMembershipSerializer
    service_class = ProgramMembershipService
    filter_fields = ("program", "user", "status")
