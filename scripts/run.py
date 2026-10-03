#!/usr/bin/env python3
"""Start the Entity Aquarium (tick loop + OBS overlay)."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from core.entity import Entity
from overlay.server import serve


def setup_logging(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    log_path = data_dir / "entity.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def main() -> int:
    tick_seconds = float(os.getenv("ENTITY_TICK_SECONDS", "8"))
    host = os.getenv("OVERLAY_HOST", "127.0.0.1")
    port = int(os.getenv("OVERLAY_PORT", "8787"))

    setup_logging(ROOT / "data")
    logging.getLogger("entity").info("Starting Entity Aquarium Phase 0")

    entity = Entity(root=ROOT, tick_seconds=tick_seconds)
    entity.start_background()

    server = serve(entity, host=host, port=port)
    print(f"Aquarium: http://{host}:{port}/")
    print("OBS Browser Source: use that URL at 1920x1080")
    print("Pause:  curl -X POST http://127.0.0.1:%s/api/control/pause" % port)
    print("Resume: curl -X POST http://127.0.0.1:%s/api/control/resume" % port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        entity.stop()
        server.shutdown()
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
