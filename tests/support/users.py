import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import UUID


class UsersDirectory:
    """Профили на месте сервиса users; `available=False` — сервис недоступен (503)."""

    def __init__(self) -> None:
        self.profiles: dict[str, dict[str, Any]] = {}
        self.available = True
        self.tokens: list[str] = []

    def add(self, user_id: UUID, username: str, display_name: str | None = None) -> None:
        self.profiles[str(user_id)] = {
            "id": str(user_id),
            "username": username,
            "display_name": display_name,
            "email": f"{username}@example.com",
        }

    def reset(self) -> None:
        self.profiles.clear()
        self.tokens.clear()
        self.available = True


DIRECTORY = UsersDirectory()


class _UsersHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        url = urlparse(self.path)
        if not DIRECTORY.available or url.path != "/api/v1/users/lookup":
            self.send_response(503 if not DIRECTORY.available else 404)
            self.end_headers()
            return
        DIRECTORY.tokens.append(self.headers.get("Authorization", ""))
        ids = parse_qs(url.query).get("ids", [])
        items = [DIRECTORY.profiles[i] for i in ids if i in DIRECTORY.profiles]
        body = json.dumps({"items": items}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        pass


@contextmanager
def users_server() -> Iterator[str]:
    """Сервис users на localhost: отдаёт профили из DIRECTORY; отдаёт базовый адрес."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _UsersHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
