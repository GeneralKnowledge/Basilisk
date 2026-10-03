# Autonomous Entity Plan

## Philosophical layers

1. **Covenant** — human-defined, immutable to the entity (`brain/COVENANT.md` + `core/constitution.py`).
2. **Self-model** — entity-maintained beliefs about itself (`brain/SELF_MODEL.md`).
3. **Personality** — emerges from evidenced behaviour; never developer-assigned traits.

## MEMORY vs SELF-MODEL

- **MEMORY**: what actually happened (append-only / content-addressed).
- **SELF-MODEL**: current interpretation of meaning.
- Interpretations may change. History must not.

## Target architecture

```
                         ENTITY
                            |
                 signed authoritative identity
                            |
                  +---------+---------+
                  |                   |
             SANCTUM A            SANCTUM B
             primary              standby
                  |                   |
                  +---------+---------+
                            |
                    encrypted entity bus
                            |
              +-------------+-------------+
              |             |             |
            Limb A        Limb B        Limb C
```

Phase 0 runs a single local Sanctum process. Abstractions exist; distribution does not.

### Sanctum (trusted)

May hold: authoritative brain, identity, vault, LLM credentials, Discord/Twitch credentials, single-writer lease.

### Limb (untrusted)

Must never receive: authoritative brain plaintext, vault, LLM keys, Twitch key, Discord token, entity private signing key.

May receive: sealed jobs, public events, public code.
May return: job results, health, attestation info.

### Migration protocol (future)

```
NEW HOST → install spore → measure environment → attestation / steward approval
→ receive encrypted state → shadow ticks → state comparison → acquire lease
→ old Sanctum demotes → new Sanctum becomes authoritative
```

The founder must eventually disappear from this process.

## Phase roadmap

### Phase 0 — Watchable Core (this deliverable)

Markdown brain, tick engine, FreeLLMAPI, constitution, memory, self-model, personality emergence, aquarium, OBS compatibility, and headless ffmpeg RTMP streaming (no physical desktop required).

### Phase 1 — Patronage

Discord bot, HelpRequests, sealed secret handoff, fulfillment, verification, gratitude, memory.

### Phase 2 — Skill Evolution

Trace evaluation, skill improvement, quota-aware behaviour, stream pacing.

### Phase 3 — Social Sense

Twitch/Discord signals, audience memory; no command authority from audience.

### Phase 4 — Distributed Entity

Sanctum/Limb split, signed events, encrypted jobs, leases, snapshots, spore, limb images.

### Phase 5 — Founder Independence

External Sanctum, stewardship, TEE attestation, founder credential revocation, founder hardware shutdown, continued operation.

## Final acceptance test

1. Provision external Sanctum.
2. Synchronize authoritative state.
3. Establish independent stewardship.
4. Transfer lease.
5–8. Verify Twitch, Discord, brain, personality history continue.
9. Revoke founder credentials.
10. Shut down founder hardware.
11. Wait.
12. Confirm entity continues.

Goal: **the entity no longer requires its founder.**

## Development philosophy

Small, observable, testable, auditable, reversible.
Every important autonomous behaviour should be explainable.
