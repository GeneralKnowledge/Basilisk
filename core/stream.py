"""Headless aquarium streaming helpers (ffmpeg RTMP, no desktop/OBS required)."""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlparse


STREAM_KEY_ENV = "STREAM_KEY"
RTMP_URL_ENV = "STREAM_RTMP_URL"


@dataclass(frozen=True)
class StreamConfig:
    aquarium_url: str
    rtmp_base: str
    stream_key: str
    fps: int
    width: int
    height: int
    video_bitrate: str
    output_mode: str  # rtmp | file
    output_file: Path
    ffmpeg_bin: str

    @property
    def rtmp_url(self) -> str:
        base = self.rtmp_base.rstrip("/")
        key = self.stream_key.strip()
        if not key:
            return base
        # Avoid double-appending if operator pasted a full URL with key.
        if key in base:
            return base
        return f"{base}/{key}"


def load_stream_config(root: Path | None = None) -> StreamConfig:
    root = root or Path.cwd()
    mode = os.getenv("STREAM_OUTPUT", "rtmp").strip().lower()
    if mode not in {"rtmp", "file"}:
        mode = "rtmp"
    return StreamConfig(
        aquarium_url=os.getenv("AQUARIUM_URL", "http://127.0.0.1:8787/"),
        rtmp_base=os.getenv(RTMP_URL_ENV, "rtmp://live.twitch.tv/app"),
        stream_key=os.getenv(STREAM_KEY_ENV, ""),
        fps=max(1, int(os.getenv("STREAM_FPS", "5"))),
        width=int(os.getenv("STREAM_WIDTH", "1920")),
        height=int(os.getenv("STREAM_HEIGHT", "1080")),
        video_bitrate=os.getenv("STREAM_VIDEO_BITRATE", "2500k"),
        output_mode=mode,
        output_file=Path(os.getenv("STREAM_FILE", str(root / "data" / "stream_preview.mp4"))),
        ffmpeg_bin=os.getenv("FFMPEG_BIN", "ffmpeg"),
    )


def redact_secrets(text: str, stream_key: str = "") -> str:
    """Remove stream keys / RTMP secrets from operator-facing strings."""
    redacted = text
    key = stream_key or os.getenv(STREAM_KEY_ENV, "")
    if key:
        redacted = redacted.replace(key, "[REDACTED_STREAM_KEY]")
        redacted = redacted.replace(quote(key, safe=""), "[REDACTED_STREAM_KEY]")
    # Common RTMP app/key suffix patterns
    redacted = re.sub(
        r"(rtmp[s]?://[^\s]+/app/)([A-Za-z0-9_\-]+)",
        r"\1[REDACTED_STREAM_KEY]",
        redacted,
        flags=re.IGNORECASE,
    )
    redacted = re.sub(
        r"(?i)\b(STREAM_KEY|TWITCH_STREAM_KEY)\s*[:=]\s*\S+",
        r"\1=[REDACTED]",
        redacted,
    )
    return redacted


def require_ffmpeg(ffmpeg_bin: str) -> str:
    path = shutil.which(ffmpeg_bin)
    if not path:
        raise RuntimeError(
            f"ffmpeg not found ({ffmpeg_bin}). Install ffmpeg to stream without OBS/desktop."
        )
    return path


def build_ffmpeg_command(config: StreamConfig) -> list[str]:
    """Build ffmpeg argv that reads MJPEG frames on stdin."""
    ffmpeg = require_ffmpeg(config.ffmpeg_bin)
    common_input = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "warning",
        "-y",
        "-thread_queue_size",
        "512",
        "-f",
        "image2pipe",
        "-vcodec",
        "mjpeg",
        "-framerate",
        str(config.fps),
        "-i",
        "-",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-tune",
        "zerolatency",
        "-pix_fmt",
        "yuv420p",
        "-b:v",
        config.video_bitrate,
        "-maxrate",
        config.video_bitrate,
        "-bufsize",
        "5000k",
        "-g",
        str(config.fps * 2),
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-shortest",
    ]

    if config.output_mode == "file":
        config.output_file.parent.mkdir(parents=True, exist_ok=True)
        return common_input + [
            "-movflags",
            "+faststart",
            str(config.output_file),
        ]

    if not config.stream_key and "live.twitch.tv" in config.rtmp_base:
        raise RuntimeError("STREAM_KEY is required for RTMP output")

    url = config.rtmp_url
    parsed = urlparse(url)
    if parsed.scheme not in {"rtmp", "rtmps"}:
        raise RuntimeError("STREAM_RTMP_URL must be rtmp:// or rtmps://")

    return common_input + [
        "-f",
        "flv",
        url,
    ]


def describe_destination(config: StreamConfig) -> str:
    if config.output_mode == "file":
        return f"file:{config.output_file}"
    return redact_secrets(config.rtmp_url, config.stream_key)
