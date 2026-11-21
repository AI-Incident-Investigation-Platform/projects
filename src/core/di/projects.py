from dishka import Provider, Scope, provide

from src.api.acl.service import AclService
from src.api.api_tokens.service import ApiTokenService
from src.api.environments.service import EnvironmentService
from src.api.invitations.service import InvitationService
from src.api.members.service import MemberService
from src.api.monitored_services.service import MonitoredServiceService
from src.api.projects.service import ProjectService
from src.core.access.service import ProjectAccess


class ProjectsProvider(Provider):
    project_access = provide(ProjectAccess, scope=Scope.REQUEST)
    acl_service = provide(AclService, scope=Scope.APP)
    project_service = provide(ProjectService, scope=Scope.REQUEST)
    environment_service = provide(EnvironmentService, scope=Scope.REQUEST)
    monitored_service_service = provide(MonitoredServiceService, scope=Scope.REQUEST)
    api_token_service = provide(ApiTokenService, scope=Scope.REQUEST)
    member_service = provide(MemberService, scope=Scope.REQUEST)
    invitation_service = provide(InvitationService, scope=Scope.REQUEST)
