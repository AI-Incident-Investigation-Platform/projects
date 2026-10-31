from fastapi import Response


def forbid_caching(response: Response) -> None:
    """Ответ с секретом не сохраняется ни браузером, ни прокси."""
    response.headers["Cache-Control"] = "no-store"
