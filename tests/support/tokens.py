import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from uuid import UUID

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

SIGNING_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
KEY_ID = "test-key"


def issue_access_token(user_id: UUID, session_id: UUID, **overrides: Any) -> str:
    """Access-токен, как его выпускает auth; `overrides` подменяет claims и `kid`."""
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "iss": "auth",
        "aud": "aiip",
        "sub": str(user_id),
        "sid": str(session_id),
        "iat": now,
        "exp": now + timedelta(minutes=15),
    }
    kid = overrides.pop("kid", KEY_ID)
    key = overrides.pop("key", SIGNING_KEY)
    payload.update(overrides)
    return jwt.encode(payload, key, algorithm="RS256", headers={"kid": kid})


def jwks_document() -> bytes:
    jwk = RSAAlgorithm.to_jwk(SIGNING_KEY.public_key(), as_dict=True)
    return json.dumps({"keys": [{**jwk, "kid": KEY_ID, "use": "sig", "alg": "RS256"}]}).encode()


class _JwksHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = jwks_document()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        pass


@contextmanager
def jwks_server() -> Iterator[str]:
    """JWKS тестового ключа на localhost на месте сервиса auth; отдаёт адрес документа."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _JwksHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/.well-known/jwks.json"
    finally:
        server.shutdown()
        server.server_close()
