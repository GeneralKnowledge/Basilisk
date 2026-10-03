"""Local aquarium HTTP server for OBS Browser Source."""

from __future__ import annotations

import json
import logging
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from core.entity import Entity

logger = logging.getLogger("overlay")


class AquariumHandler(SimpleHTTPRequestHandler):
    entity: Entity
    static_dir: Path

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(self.static_dir), **kwargs)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        logger.debug("%s - %s", self.address_string(), format % args)

    def _is_local(self) -> bool:
        host = self.client_address[0]
        return host in {"127.0.0.1", "::1", "localhost"}

    def _json(self, code: int, payload: object) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/state":
            self._json(200, self.entity.public_state())
            return
        if path == "/api/explain":
            self._json(200, self.entity.explain_last())
            return
        if path == "/api/health":
            state = self.entity.public_state()
            self._json(
                200,
                {
                    "ok": True,
                    "paused": state["state"]["paused"],
                    "tick_count": state["identity"]["tick_count"],
                    "inference": state["quota"]["inference"],
                    "db": str(self.entity.memory.db_path),
                },
            )
            return
        if path in {"/", "/index.html"}:
            self.path = "/index.html"
        return SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in {"/api/control/pause", "/api/control/resume"}:
            if not self._is_local():
                self._json(403, {"ok": False, "error": "local only"})
                return
            if path.endswith("pause"):
                self.entity.pause()
            else:
                self.entity.resume()
            self._json(200, {"ok": True, "paused": self.entity.paused})
            return
        self._json(404, {"ok": False, "error": "not found"})


def make_handler(entity: Entity, static_dir: Path):
    return type(
        "BoundAquariumHandler",
        (AquariumHandler,),
        {"entity": entity, "static_dir": static_dir},
    )


def serve(entity: Entity, host: str = "127.0.0.1", port: int = 8787) -> ThreadingHTTPServer:
    static_dir = Path(__file__).resolve().parent / "static"
    handler = make_handler(entity, static_dir)
    server = ThreadingHTTPServer((host, port), handler)
    logger.info("Aquarium overlay at http://%s:%s/", host, port)
    return server
