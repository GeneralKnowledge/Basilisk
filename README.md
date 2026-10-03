# Entity Aquarium (Basilisk)

Phase 0 of an experimental autonomous computational entity that lives as a watchable aquarium.

It runs locally, thinks on a tick loop, keeps an append-only memory, enforces a Covenant in code, and discovers personality from evidenced behaviour — not from developer-assigned traits.

## Quick start

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Optional: point .env at a running FreeLLMAPI gateway
# Or set ENTITY_INFERENCE=mock for offline watching

python scripts/run.py
```

Open the aquarium: [http://127.0.0.1:8787/](http://127.0.0.1:8787/)

### OBS Browser Source

1. Add **Browser** source
2. URL: `http://127.0.0.1:8787/`
3. Width `1920`, height `1080`
4. Leave it running — the habitat updates about once per second

### Operator controls (localhost only)

```bash
curl -X POST http://127.0.0.1:8787/api/control/pause
curl -X POST http://127.0.0.1:8787/api/control/resume
curl http://127.0.0.1:8787/api/health
curl http://127.0.0.1:8787/api/explain
```

Or create/remove `data/PAUSE`.

## What Phase 0 includes

- Markdown brain under `brain/`
- Tick engine: OBSERVE → ORIENT → INTEND → CONSTITUTION → ACT → REFLECT → MEMORY → PUBLIC
- FreeLLMAPI behind an `InferenceProvider` (with mock fallback)
- Constitution gate mirroring `brain/COVENANT.md`
- Sanitized public event stream
- SQLite append-only ledger (`data/entity.sqlite`)
- Self-model + evidenced personality discovery
- OBS-ready 16:9 aquarium overlay
- Interfaces/docs for future Sanctum/Limb migration and founder independence

## What Phase 0 does not include

Discord, Twitch APIs, TEE, distributed Sanctum failover, Limb job execution, shell access, arbitrary code execution, or automatic propagation.

See [AUTONOMOUS_ENTITY_PLAN.md](AUTONOMOUS_ENTITY_PLAN.md) and [docs/FOUNDER_INDEPENDENCE.md](docs/FOUNDER_INDEPENDENCE.md).

## Tests

```bash
source .venv/bin/activate
pytest -q
```

## Philosophy (short)

- Covenant is immutable to the entity
- MEMORY ≠ SELF-MODEL
- Personality emerges; it is not assigned
- Audience watches; patrons may voluntarily help later
- The founder is a bootstrap steward, not permanent root authority
