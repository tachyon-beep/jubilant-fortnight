"""Alert routing helpers for telemetry guardrails."""

from __future__ import annotations

import json
import logging
import os
import smtplib
import threading
import time
import urllib.request
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AlertPayload:
    """Structured payload for alert notifications."""

    event: str
    message: str
    severity: str
    source: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: float = time.time()


class AlertRouter:
    """Routes alert notifications to configured integrations."""

    def __init__(
        self,
        webhook_urls: Optional[List[str]] = None,
        webhook_url: Optional[str] = None,
        *,
        timeout: float = 5.0,
        muted_events: Optional[set[str]] = None,
        email_host: Optional[str] = None,
        email_port: int = 587,
        email_username: Optional[str] = None,
        email_password: Optional[str] = None,
        email_from: Optional[str] = None,
        email_recipients: Optional[List[str]] = None,
        email_use_tls: bool = True,
    ) -> None:
        urls = webhook_urls or []
        if webhook_url:
            urls.append(webhook_url)
        self._webhook_urls = [value for value in urls if value]
        self._timeout = timeout
        self._muted_events = muted_events or set()
        self._lock = threading.Lock()
        self._email_host = email_host
        self._email_port = email_port
        self._email_username = email_username
        self._email_password = email_password
        self._email_from = email_from
        self._email_recipients = email_recipients or []
        self._email_use_tls = email_use_tls

    def notify(
        self,
        *,
        event: str,
        message: str,
        severity: str = "warning",
        source: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Send an alert payload to the configured outputs."""

        if event in self._muted_events:
            logger.debug("Alert event '%s' is muted; skipping notification", event)
            return False

        payload = AlertPayload(
            event=event,
            message=message,
            severity=severity,
            source=source,
            metadata=metadata,
        )

        sent = False

        for webhook in self._webhook_urls:
            sent = self._post_webhook(payload, webhook) or sent

        if self._email_host:
            try:
                email_sent = self._send_email(payload)
                sent = sent or email_sent
            except Exception:  # pragma: no cover - logged in send helper
                sent = sent or False

        if not sent:
            logger.warning(
                "Alert emitted without external routing: %s | %s", event, message
            )
        return sent

    def _post_webhook(self, payload: AlertPayload, webhook_url: str) -> bool:
        """Send the alert payload to the configured webhook endpoint."""

        body = {
            "event": payload.event,
            "severity": payload.severity,
            "message": payload.message,
            "source": payload.source,
            "metadata": payload.metadata or {},
            "timestamp": payload.timestamp,
        }

        # Include generic fields for Slack/Discord compatibility.
        text_message = f"[{payload.severity.upper()}] {payload.message}"
        body.setdefault("text", text_message)
        body.setdefault("content", text_message)
        body.setdefault("username", "Great Work Alerts")

        data = json.dumps(body).encode("utf-8")

        request = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
        )

        try:
            with self._lock:
                with urllib.request.urlopen(request, timeout=self._timeout) as response:
                    logger.debug(
                        "Alert webhook response %s for event %s",
                        response.status,
                        payload.event,
                    )
            return True
        except (
            Exception
        ):  # pragma: no cover - network errors are logged for ops visibility.
            logger.exception(
                "Failed to deliver alert webhook for event %s", payload.event
            )
            return False

    def _send_email(self, payload: AlertPayload) -> bool:
        """Send alert via SMTP email when configured."""

        if not self._email_host or not self._email_from or not self._email_recipients:
            logger.debug("Email alert skipped due to incomplete configuration")
            return False

        msg = EmailMessage()
        msg["Subject"] = f"[{payload.severity.upper()}] {payload.event}"
        msg["From"] = self._email_from
        msg["To"] = ", ".join(self._email_recipients)

        body_lines = [
            f"Event: {payload.event}",
            f"Severity: {payload.severity}",
            f"Message: {payload.message}",
        ]
        if payload.source:
            body_lines.append(f"Source: {payload.source}")
        if payload.metadata:
            body_lines.append(
                f"Metadata: {json.dumps(payload.metadata, ensure_ascii=False)}"
            )
        body_lines.append(
            f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(payload.timestamp))}"
        )
        msg.set_content("\n".join(body_lines))

        try:
            with smtplib.SMTP(
                self._email_host, self._email_port, timeout=self._timeout
            ) as smtp:
                if self._email_use_tls:
                    smtp.starttls()
                if self._email_username and self._email_password:
                    smtp.login(self._email_username, self._email_password)
                smtp.send_message(msg)
            return True
        except Exception:  # pragma: no cover - log and continue
            logger.exception(
                "Failed to deliver alert email for event %s", payload.event
            )
            return False


_alert_router: Optional[AlertRouter] = None


def get_alert_router() -> AlertRouter:
    """Return the lazily instantiated alert router."""

    global _alert_router
    if _alert_router is None:
        webhook_urls_env = os.getenv("GREAT_WORK_ALERT_WEBHOOK_URLS", "")
        webhook_urls = [
            value.strip() for value in webhook_urls_env.split(",") if value.strip()
        ]
        fallback_webhook = os.getenv("GREAT_WORK_ALERT_WEBHOOK_URL")
        timeout = float(os.getenv("GREAT_WORK_ALERT_TIMEOUT", "5") or 5)
        muted = {
            value.strip()
            for value in os.getenv("GREAT_WORK_ALERT_MUTED_EVENTS", "").split(",")
            if value.strip()
        }
        email_host = os.getenv("GREAT_WORK_ALERT_EMAIL_HOST")
        email_port = int(os.getenv("GREAT_WORK_ALERT_EMAIL_PORT", "587") or 587)
        email_username = os.getenv("GREAT_WORK_ALERT_EMAIL_USERNAME")
        email_password = os.getenv("GREAT_WORK_ALERT_EMAIL_PASSWORD")
        email_from = os.getenv("GREAT_WORK_ALERT_EMAIL_FROM")
        recipients_raw = os.getenv("GREAT_WORK_ALERT_EMAIL_TO", "")
        email_recipients = [
            value.strip() for value in recipients_raw.split(",") if value.strip()
        ]
        email_use_tls = os.getenv(
            "GREAT_WORK_ALERT_EMAIL_STARTTLS", "true"
        ).lower() not in {"false", "0", "off"}
        _alert_router = AlertRouter(
            webhook_urls=webhook_urls,
            webhook_url=fallback_webhook,
            timeout=timeout,
            muted_events=muted,
            email_host=email_host,
            email_port=email_port,
            email_username=email_username,
            email_password=email_password,
            email_from=email_from,
            email_recipients=email_recipients,
            email_use_tls=email_use_tls,
        )
    return _alert_router


def set_alert_router(router: Optional[AlertRouter]) -> None:
    """Override the global alert router (primarily for testing)."""

    global _alert_router
    _alert_router = router


__all__ = ["AlertRouter", "AlertPayload", "get_alert_router", "set_alert_router"]
