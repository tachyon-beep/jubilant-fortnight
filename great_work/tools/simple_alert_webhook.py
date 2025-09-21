"""Lightweight webhook receiver for alert testing.

Run with:

    python -m great_work.tools.simple_alert_webhook --port 8085

The server logs incoming JSON payloads to stdout so you can confirm alert routing
without relying on a third-party provider.
"""

from __future__ import annotations

import argparse
import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

logger = logging.getLogger(__name__)


class AlertWebhookHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler that logs JSON payloads and responds OK."""

    server_version = "GreatWorkAlertWebhook/1.0"

    def do_POST(self) -> None:  # noqa: N802 (http.server API)
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except json.JSONDecodeError:
            payload = {"raw": raw_body.decode("utf-8", errors="ignore")}

        logger.info("Received alert payload: %s", json.dumps(payload, indent=2))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "ok"}')

    def log_message(
        self, message_format: str, *args
    ) -> None:  # BaseHTTPRequestHandler calls this with positional args
        logger.debug("HTTP: " + message_format, *args)


def run_server(host: str, port: int) -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    server = HTTPServer((host, port), AlertWebhookHandler)
    logger.info("Listening for alerts on http://%s:%s", host, port)
    logger.info("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down webhook server")
    finally:
        server.server_close()


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Run a simple alert webhook receiver.")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host interface to bind (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port", type=int, default=8085, help="Port to listen on (default: 8085)"
    )
    args = parser.parse_args(argv)
    run_server(args.host, args.port)


if __name__ == "__main__":
    main()
