from src.core.errors import ConflictError, GoneError, NotFoundError, RuleViolationError


class InvitationNotFoundError(NotFoundError):
    """Приглашения нет или оно не тебе: чужое не отличить от несуществующего."""

    code = "invitation.not_found"
    message = "Приглашение не найдено"


class InvitationGoneError(GoneError):
    code = "invitation.gone"
    message = "Приглашение отозвано, отклонено или истекло"


class InvitationPendingError(ConflictError):
    code = "invitation.already_pending"
    message = "Этого пользователя уже пригласили в проект"


class AlreadyMemberError(ConflictError):
    code = "invitation.already_member"
    message = "Пользователь уже участник проекта"


class InviteeInvalidError(RuleViolationError):
    code = "invitation.user_invalid"
    message = "Пользователь не найден"


class InvitationRoleInvalidError(RuleViolationError):
    code = "invitation.role_invalid"
    message = "Такой роли нет"
