from src.core.errors import NotFoundError, RuleViolationError


class MemberNotFoundError(NotFoundError):
    code = "member.not_found"
    message = "Участник не найден"


class RoleInvalidError(RuleViolationError):
    code = "member.role_invalid"
    message = "Такой роли нет"


class OwnRoleChangeError(RuleViolationError):
    code = "member.own_role"
    message = "Свою роль менять нельзя"


class LastOwnerError(RuleViolationError):
    code = "member.last_owner"
    message = "В проекте должен остаться хотя бы один владелец"
