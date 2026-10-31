from src.core.errors import ConflictError


class ProjectSlugTakenError(ConflictError):
    code = "project.slug_taken"
    message = "Проект с таким slug уже есть"
