#!/usr/bin/env python3
"""Stream the aquarium headlessly via Playwright + ffmpeg.

No physical desktop and no OBS required.

Typical use:
  1. python scripts/run.py          # entity + aquarium HTTP
  2. python scripts/stream.py       # headless capture → RTMP/file
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from core.stream import (  # noqa: E402
    build_ffmpeg_command,
    describe_destination,
    load_stream_config,
    redact_secrets,
)

logger = logging.getLogger("stream")


def setup_logging() -> None:
    log_path = ROOT / "data" / "stream.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def wait_for_aquarium(url: str, timeout: float = 60.0) -> None:
    import urllib.error
    import urllib.request

    health = url.rstrip("/") + "/api/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(health, timeout=2) as resp:
                if resp.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.5)
    raise RuntimeError(
        f"Aquarium not reachable at {health}. Start it first with: python scripts/run.py"
    )


def run_stream(*, duration: float | None, output_mode: str | None) -> int:
    setup_logging()
    if output_mode:
        os.environ["STREAM_OUTPUT"] = output_mode
    config = load_stream_config(ROOT)

    wait_for_aquarium(config.aquarium_url)
    cmd = build_ffmpeg_command(config)
    if duration is not None and config.output_mode == "file":
        # Help ffmpeg finalize a bounded preview encode.
        cmd = cmd[:-1] + ["-t", str(duration), cmd[-1]]

    safe_cmd = [redact_secrets(part, config.stream_key) for part in cmd]
    logger.info("Destination: %s", describe_destination(config))
    logger.info("ffmpeg: %s", " ".join(safe_cmd))
    logger.info(
        "Capture %sx%s @ %sfps from %s",
        config.width,
        config.height,
        config.fps,
        config.aquarium_url,
    )

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "playwright is required for headless streaming. "
            "pip install playwright && playwright install chromium"
        ) from exc

    stderr_path = ROOT / "data" / "ffmpeg_stderr.log"
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_file = stderr_path.open("wb")

    ffmpeg = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=stderr_file,
    )
    assert ffmpeg.stdin is not None

    stop = False

    def _stop(*_args: object) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    frames = 0
    started = time.time()
    frame_interval = 1.0 / config.fps
    pipe_broken = False

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
            )
            page = browser.new_page(
                viewport={"width": config.width, "height": config.height},
                device_scale_factor=1,
            )
            page.goto(config.aquarium_url, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(750)

            while not stop:
                loop_start = time.time()
                if duration is not None and (loop_start - started) >= duration:
                    break

                jpeg = page.screenshot(type="jpeg", quality=85, full_page=False)
                try:
                    ffmpeg.stdin.write(jpeg)
                    ffmpeg.stdin.flush()
                except BrokenPipeError:
                    pipe_broken = True
                    logger.error("ffmpeg pipe broke early; see data/ffmpeg_stderr.log")
                    break

                frames += 1
                if frames == 1 or frames % max(1, config.fps * 10) == 0:
                    logger.info("frames=%s elapsed=%.1fs", frames, time.time() - started)

                if frames % max(1, config.fps * 30) == 0:
                    page.evaluate("() => { if (window.poll) window.poll(); }")

                slept = time.time() - loop_start
                delay = frame_interval - slept
                if delay > 0:
                    time.sleep(delay)

            browser.close()
    finally:
        try:
            if ffmpeg.stdin and not ffmpeg.stdin.closed:
                ffmpeg.stdin.close()
        except Exception:
            pass
        try:
            code = ffmpeg.wait(timeout=30)
        except subprocess.TimeoutExpired:
            ffmpeg.kill()
            code = ffmpeg.wait(timeout=10)
        stderr_file.close()

        err_text = stderr_path.read_text(encoding="utf-8", errors="replace")
        if err_text.strip():
            logger.info("ffmpeg: %s", redact_secrets(err_text, config.stream_key)[-1000:])
        logger.info(
            "Stopped after %s frames (exit=%s) → %s",
            frames,
            code,
            describe_destination(config),
        )

    if frames <= 0 or pipe_broken:
        return 1
    if config.output_mode == "file":
        return 0 if config.output_file.exists() and config.output_file.stat().st_size > 0 else 1
    return 0 if code == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Headless aquarium stream via ffmpeg")
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Stop after N seconds (useful for dry-runs)",
    )
    parser.add_argument(
        "--file",
        action="store_true",
        help="Write a local MP4 instead of RTMP (no Twitch key needed)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Alias for --file --duration 8",
    )
    args = parser.parse_args()

    duration = args.duration
    output_mode = None
    if args.dry_run:
        output_mode = "file"
        duration = duration if duration is not None else 8.0
    elif args.file:
        output_mode = "file"

    try:
        return run_stream(duration=duration, output_mode=output_mode)
    except Exception as exc:
        setup_logging()
        logger.error("%s", redact_secrets(str(exc)))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
