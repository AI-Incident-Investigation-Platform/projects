import httpx

from src.config import cfg
from src.core.auth.exc import AuthBadResponseError, AuthUnavailableError


class AuthClient:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def get_jwks(self) -> bytes:
        try:
            response = await self._http.get(cfg.auth.jwks_url)
        except httpx.HTTPError as exc:
            raise AuthUnavailableError({"url": cfg.auth.jwks_url}) from exc
        if response.status_code != httpx.codes.OK:
            raise AuthBadResponseError({"status": response.status_code})
        return response.content
