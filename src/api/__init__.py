from fastapi import APIRouter

from src.api.acl.v1.router import router as acl_v1_router
from src.api.api_tokens.v1.router import router as api_tokens_v1_router
from src.api.environments.v1.router import router as environments_v1_router
from src.api.invitations.v1.router import router as invitations_v1_router
from src.api.members.v1.router import router as members_v1_router
from src.api.monitored_services.v1.router import router as services_v1_router
from src.api.projects.v1.router import router as projects_v1_router

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(projects_v1_router)
v1_router.include_router(environments_v1_router)
v1_router.include_router(services_v1_router)
v1_router.include_router(api_tokens_v1_router)
v1_router.include_router(members_v1_router)
v1_router.include_router(invitations_v1_router)

router = APIRouter(prefix="/api")
router.include_router(v1_router)

# служебный API для других сервисов: не опубликован через Traefik, только внутри кластера
internal_v1_router = APIRouter(prefix="/v1")
internal_v1_router.include_router(acl_v1_router)

internal_router = APIRouter(prefix="/internal")
internal_router.include_router(internal_v1_router)
