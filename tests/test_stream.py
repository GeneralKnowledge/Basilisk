from pathlib import Path

import pytest

from core.sanitizer import sanitize_public_text
from core.stream import build_ffmpeg_command, load_stream_config, redact_secrets


def test_redact_stream_key(monkeypatch):
    monkeypatch.setenv("STREAM_KEY", "live_secret_key_abc123")
    text = "pushing to rtmp://live.twitch.tv/app/live_secret_key_abc123"
    out = redact_secrets(text, "live_secret_key_abc123")
    assert "live_secret_key_abc123" not in out
    assert "[REDACTED_STREAM_KEY]" in out


def test_sanitizer_blocks_rtmp_key_in_public_text():
    result = sanitize_public_text(
        "tune in rtmp://live.twitch.tv/app/live_1234567890abcdef"
    )
    assert not result.allowed


def test_sanitizer_blocks_stream_key_env():
    result = sanitize_public_text("STREAM_KEY=live_1234567890abcdef")
    assert not result.allowed


def test_build_ffmpeg_file_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("STREAM_OUTPUT", "file")
    monkeypatch.setenv("STREAM_FILE", str(tmp_path / "out.mp4"))
    monkeypatch.setenv("STREAM_KEY", "")
    cfg = load_stream_config(tmp_path)
    cmd = build_ffmpeg_command(cfg)
    assert cmd[0].endswith("ffmpeg") or cmd[0] == "ffmpeg" or "ffmpeg" in cmd[0]
    assert str(tmp_path / "out.mp4") in cmd
    assert "flv" not in cmd


def test_build_ffmpeg_rtmp_requires_key(monkeypatch, tmp_path):
    monkeypatch.setenv("STREAM_OUTPUT", "rtmp")
    monkeypatch.setenv("STREAM_RTMP_URL", "rtmp://live.twitch.tv/app")
    monkeypatch.setenv("STREAM_KEY", "")
    cfg = load_stream_config(tmp_path)
    with pytest.raises(RuntimeError, match="STREAM_KEY"):
        build_ffmpeg_command(cfg)
