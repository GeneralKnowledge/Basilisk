"""Sole path from internal events to public aquarium events."""

from __future__ import annotations

import re
from dataclasses import dataclass


SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("api_key", re.compile(r"(?i)\b(api[_-]?key|access[_-]?key)\b\s*[:=]\s*\S+")),
    ("bearer", re.compile(r"(?i)\bbearer\s+[a-z0-9\-._~+/]+=*")),
    ("token", re.compile(r"(?i)\b(token|auth[_-]?token|session[_-]?token)\b\s*[:=]\s*\S+")),
    ("password", re.compile(r"(?i)\b(password|passwd|pwd)\b\s*[:=]\s*\S+")),
    ("cookie", re.compile(r"(?i)\b(cookie|set-cookie)\b\s*[:=]\s*\S+")),
    ("discord", re.compile(r"(?i)\b(discord\s*(bot\s*)?token|MT[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{20,})")),
    ("twitch", re.compile(r"(?i)\b(twitch\s*(stream\s*)?key|oauth:[a-z0-9]+)\b")),
    ("email_code", re.compile(r"(?i)\b(verification|confirm(ation)?)\s*code\b\s*[:=]?\s*\d{4,8}")),
    ("env_dump", re.compile(r"(?i)\b(FREELLMAPI_API_KEY|OPENAI_API_KEY|DISCORD_TOKEN|TWITCH_STREAM_KEY)\b\s*[:=]\s*\S+")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("prompt_leak", re.compile(r"(?i)\b(system prompt|raw prompt|private prompt)\b")),
]


PRIVATE_MARKERS = (
    "private memory",
    "private_prompt",
    "vault:",
    "credential",
)


@dataclass
class SanitizeResult:
    allowed: bool
    text: str
    reason: str = ""


def contains_secrets(text: str) -> str | None:
    for name, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            return name
    lowered = text.lower()
    for marker in PRIVATE_MARKERS:
        if marker in lowered:
            return f"marker:{marker}"
    return None


def sanitize_public_text(text: str, *, max_len: int = 280) -> SanitizeResult:
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return SanitizeResult(False, "", "empty")
    hit = contains_secrets(cleaned)
    if hit:
        return SanitizeResult(False, "", f"blocked:{hit}")
    if len(cleaned) > max_len:
        cleaned = cleaned[: max_len - 1].rstrip() + "…"
    return SanitizeResult(True, cleaned)


def redact_for_log(text: str) -> str:
    redacted = text
    for _, pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted
