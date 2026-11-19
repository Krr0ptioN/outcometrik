from ..decorators import controller
from ..serializers import ProgramMembershipSerializer
from ..services import ProgramMembershipService
from .base import AcademicController


@controller("program-memberships", basename="program-membership")
class ProgramMembershipController(AcademicController):
    serializer_class = ProgramMembershipSerializer
    service_class = ProgramMembershipService
    filter_fields = ("program", "user", "status")
