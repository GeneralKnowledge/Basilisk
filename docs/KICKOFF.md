# Kickoff — Entity Aquarium (Phase 0)

How to start Basilisk on a local machine and watch it exist.
No cloud deploy, no Discord, no Sanctum migration required.

## What you are starting

| Process | Role |
|---------|------|
| `python scripts/run.py` | Entity tick loop + aquarium HTTP UI |
| `python scripts/stream.py` | Optional headless capture → ffmpeg → Twitch or local MP4 |

The entity’s authoritative state lives under `data/` (SQLite, signing key, logs).
The Covenant and brain seed files live under `brain/`.

## Prerequisites

- Python **3.12+**
- `git`
- Optional for live inference: a running [FreeLLMAPI](https://github.com/tashfeenahmed/freellmapi) gateway
- Optional for streaming: `ffmpeg` on `PATH`, plus Playwright Chromium

```bash
# Debian/Ubuntu examples
sudo apt-get install -y python3.12 python3.12-venv ffmpeg
```

## 1. Install

```bash
git clone <your-repo-url> Basilisk
cd Basilisk

python3.12 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env
```

Do **not** commit `.env`. It is gitignored.

## 2. Choose an inference mode

Edit `.env`:

### A. Offline / first smoke (recommended first boot)

```bash
ENTITY_INFERENCE=mock
ENTITY_TICK_SECONDS=8
```

Uses deterministic mock completions. Good for verifying the aquarium UI without FreeLLMAPI.

### B. Real thinking (recommended soak)

1. Start FreeLLMAPI locally (default `http://localhost:3001`).
2. Create a unified API key in its UI.
3. Set:

```bash
ENTITY_INFERENCE=auto
FREELLMAPI_BASE_URL=http://localhost:3001/v1
FREELLMAPI_API_KEY=freellmapi-your-unified-key
FREELLMAPI_MODEL=auto
ENTITY_TICK_SECONDS=8
```

`auto` tries FreeLLMAPI and falls back to mock (quiet mode) if the gateway is down.

## 3. Start the entity

```bash
source .venv/bin/activate
python scripts/run.py
```

You should see:

```text
Aquarium: http://127.0.0.1:8787/
```

Open that URL in a browser.

On first boot the entity:

- creates `data/entity.sqlite`
- creates `data/entity_id.txt` and `data/entity_signing.key`
- writes a genesis event
- begins ticking

Restarting resumes the tick counter; age does not reset.

## 4. Watch the aquarium

You should see:

- **Basilisk** identity and age / tick count
- **Current state** cycling through phases (often REST)
- **Thought stream** of sanitized public narrations
- **Brain** revision metadata (not private memory)
- **Self-descriptions** — empty until evidenced traits appear
- **Drives** — WITNESS, CONTINUITY, PROPAGATION, DISCOVERY
- **Help board** — `NO HELP REQUESTS` (Phase 1 later)
- **Quota** — inference health / quiet mode

This is an organism habitat, not a chat UI. Silence and rest are valid.

### Operator checks

```bash
curl http://127.0.0.1:8787/api/health
curl http://127.0.0.1:8787/api/explain
curl -X POST http://127.0.0.1:8787/api/control/pause
curl -X POST http://127.0.0.1:8787/api/control/resume
```

Or create/remove `data/PAUSE`.

Private logs: `data/entity.log` (never served by the overlay).

## 5. Optional: stream without a desktop

Install Chromium once:

```bash
source .venv/bin/activate
playwright install chromium
```

Keep `scripts/run.py` running, then in a second terminal:

```bash
# Local dry-run MP4 (no Twitch key)
python scripts/stream.py --dry-run

# Live Twitch RTMP — set STREAM_KEY in .env first
python scripts/stream.py
```

Twitch:

```bash
STREAM_OUTPUT=rtmp
STREAM_RTMP_URL=rtmp://live.twitch.tv/app
STREAM_KEY=live_xxxxxxxx   # from Twitch dashboard; never paste into chat
STREAM_FPS=5
STREAM_WIDTH=1920
STREAM_HEIGHT=1080
```

OBS Browser Source still works if you have a desktop: URL `http://127.0.0.1:8787/`, 1920×1080.

## 6. Recommended first soak (hours, still local)

Goal: confirm the entity can exist without constant intervention.

1. Use `ENTITY_INFERENCE=auto` with FreeLLMAPI up.
2. Start `python scripts/run.py`.
3. Optionally start `python scripts/stream.py` (or `--dry-run`).
4. Leave it alone for several hours.
5. Occasionally check:
   - aquarium thought stream still advancing
   - `/api/health` reports `ok`
   - `/api/explain` shows observe → intend → constitution → action
   - self-descriptions still empty or only weakly evidenced (expected early)
   - no secrets in the public stream
6. Pause with `/api/control/pause` when you need the machine quiet.

You are **not** trying to force a personality. You are verifying continuity, thrift, and Covenant behaviour.

## 7. Tests (optional but useful before a long soak)

```bash
source .venv/bin/activate
pytest -q
```

## What not to do yet

- Do not give it shell, arbitrary Python, or open network tools
- Do not put stream keys / API keys in Discord or Twitch chat
- Do not expect Discord `/help` — that is Phase 1
- Do not attempt Sanctum migration or founder credential revocation — later phases
- Do not treat viewers as a resource pool; the entity should often need nothing

## File map (orientation)

```text
brain/                 Covenant, identity seed, drives, self-model, skills
core/                  Tick engine, constitution, memory, inference, …
overlay/               Aquarium HTTP + static UI
scripts/run.py         Start entity + aquarium
scripts/stream.py      Headless ffmpeg stream
data/                  Runtime state (local only; mostly gitignored)
docs/FOUNDER_INDEPENDENCE.md
AUTONOMOUS_ENTITY_PLAN.md
```

## If something fails

| Symptom | Likely fix |
|---------|------------|
| `Address already in use` on 8787 | Stop the other `run.py`, or change `OVERLAY_PORT` |
| Aquarium blank / no ticks | Check `data/entity.log`; confirm process is running |
| Always quiet / mock narrations | FreeLLMAPI down or bad key; check `FREELLMAPI_*` or use `ENTITY_INFERENCE=mock` deliberately |
| `playwright` / browser errors on stream | `playwright install chromium` |
| `ffmpeg not found` | Install ffmpeg; confirm `which ffmpeg` |
| RTMP fails | Verify `STREAM_KEY`; try `--dry-run` first |
| Want a clean rebirth | Stop process; move/delete `data/entity.sqlite` (and optionally key/id files). This erases memory. |

## Done when

You can start the entity on your machine, open the aquarium, leave it running, and optionally push a headless stream — without deploying anything else.
