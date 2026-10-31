from enum import StrEnum


class Permission(StrEnum):
    """Права внутри проекта. Код проверяет только их, названия ролей — нигде."""

    PROJECT_READ = "project.read"
    REPORT_READ = "report.read"
    INVESTIGATION_RUN = "investigation.run"
    REVIEW_WRITE = "review.write"
    INCIDENT_MANAGE = "incident.manage"
    REPOSITORY_MANAGE = "repository.manage"
    INTEGRATION_MANAGE = "integration.manage"
    API_TOKEN_MANAGE = "api_token.manage"
    PROJECT_MANAGE = "project.manage"
    MEMBER_MANAGE = "member.manage"
    PROJECT_DELETE = "project.delete"
    OWNERSHIP_MANAGE = "ownership.manage"


class BuiltinRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    DEVELOPER = "developer"
    VIEWER = "viewer"


class TokenScope(StrEnum):
    """Что разрешено API-токену проекта. Токен — не участник: роли у него нет."""

    ALERT_INGEST = "alert.ingest"
    DEPLOYMENT_INGEST = "deployment.ingest"


class InvitationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    REVOKED = "revoked"
    # истёкшее ждущее приглашение помечается, когда его касаются: освобождает место новому
    EXPIRED = "expired"
