"""Personality emergence: candidates require evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from core.memory import MemoryStore, utc_now


@dataclass
class TraitProposal:
    trait: str
    rationale: str
    supporting_event_ids: list[str]
    contradicting_event_ids: list[str]


def normalize_trait(name: str) -> str:
    return " ".join(name.strip().lower().split())


def calculate_confidence(support: int, contradict: int) -> float:
    total = support + contradict
    if total == 0:
        return 0.0
    raw = support / total
    # Evidence volume dampener: need several supports before rising
    volume = min(1.0, support / 8.0)
    return round(max(0.0, min(0.95, raw * 0.7 + volume * 0.3)), 3)


def status_for(confidence: float, evidence_count: int) -> str:
    if confidence >= 0.7 and evidence_count >= 10:
        return "established"
    if confidence >= 0.4 and evidence_count >= 3:
        return "provisional"
    return "provisional"


def propose_from_behaviour(memory: MemoryStore) -> TraitProposal | None:
    """Heuristic candidate generation from action mix (not LLM invention alone)."""
    counts = memory.action_counts(120)
    total = sum(counts.values())
    if total < 12:
        return None

    rest = counts.get("rest", 0)
    broadcast = counts.get("broadcast_public_message", 0)
    reflect = counts.get("reflect", 0)
    recent = memory.recent_events(40)
    event_ids = [e["event_id"] for e in recent if e.get("kind") == "memory"]

    if rest / total >= 0.55 and broadcast / total <= 0.15:
        support = event_ids[: max(3, rest // 4)]
        contradict = [e for e in event_ids if "broadcast" in str(e)][:2]
        return TraitProposal(
            trait="deliberate",
            rationale="High rest ratio and low broadcast frequency across recent ticks.",
            supporting_event_ids=support,
            contradicting_event_ids=contradict,
        )
    if reflect / total >= 0.35:
        return TraitProposal(
            trait="reflective",
            rationale="Frequent reflect actions relative to other behaviours.",
            supporting_event_ids=event_ids[:5],
            contradicting_event_ids=[],
        )
    return None


def apply_proposal(memory: MemoryStore, proposal: TraitProposal) -> dict[str, Any] | None:
    trait = normalize_trait(proposal.trait)
    if not trait or len(trait) > 40:
        return None

    known = memory.known_memory_ids()
    support = [e for e in proposal.supporting_event_ids if e in known]
    contradict = [e for e in proposal.contradicting_event_ids if e in known]

    # Require evidence — LLM cannot invent permanent traits alone
    if len(support) < 2:
        return {
            "accepted": False,
            "trait": trait,
            "reason": "insufficient_evidence",
            "support": len(support),
            "contradict": len(contradict),
        }

    confidence = calculate_confidence(len(support), len(contradict))
    if confidence < 0.35:
        return {
            "accepted": False,
            "trait": trait,
            "reason": "low_confidence",
            "confidence": confidence,
        }

    existing = {t["trait"]: t for t in memory.list_traits()}
    now = utc_now()
    if trait in existing:
        first = existing[trait]["first_observed"]
        evidence_count = existing[trait]["evidence_count"] + len(support)
    else:
        first = now
        evidence_count = len(support)

    record = {
        "trait": trait,
        "confidence": confidence,
        "status": status_for(confidence, evidence_count),
        "first_observed": first,
        "last_reviewed": now,
        "evidence_count": evidence_count,
        "summary": proposal.rationale[:300],
    }
    memory.upsert_trait(record)
    for eid in support:
        memory.add_trait_evidence(trait, eid, "support", proposal.rationale[:120])
    for eid in contradict:
        memory.add_trait_evidence(trait, eid, "contradict", "contradictory behaviour")

    return {"accepted": True, **record}


def self_review(memory: MemoryStore) -> dict[str, Any]:
    """Periodic review of existing traits against recent behaviour."""
    traits = memory.list_traits()
    reviews = []
    counts = memory.action_counts(100)
    total = sum(counts.values()) or 1
    for trait in traits:
        name = trait["trait"]
        old_conf = float(trait["confidence"])
        support = trait["evidence_count"]
        # Soft adjustment from current behaviour
        if name == "deliberate":
            rest_ratio = counts.get("rest", 0) / total
            delta = 0.03 if rest_ratio > 0.5 else -0.04
        elif name == "reflective":
            ref_ratio = counts.get("reflect", 0) / total
            delta = 0.03 if ref_ratio > 0.3 else -0.03
        else:
            delta = 0.0
        new_conf = round(max(0.05, min(0.95, old_conf + delta)), 3)
        evidence = support
        updated = {
            **trait,
            "confidence": new_conf,
            "last_reviewed": utc_now(),
            "status": status_for(new_conf, evidence),
            "summary": f"Self-review: {name} confidence {old_conf} → {new_conf}",
        }
        memory.upsert_trait(updated)
        reviews.append(
            {
                "trait": name,
                "confidence_before": old_conf,
                "confidence_after": new_conf,
                "status": updated["status"],
            }
        )
    memory.set_meta("last_self_review_tick", str(memory.tick_count()))
    memory.set_meta("last_self_review_at", datetime.now(timezone.utc).isoformat())
    return {"reviews": reviews}


def render_traits_markdown(memory: MemoryStore) -> str:
    lines = [
        "# Personality Traits",
        "",
        "Self-discovered descriptions only.",
        "No developer-assigned traits.",
        "",
    ]
    traits = memory.list_traits()
    if not traits:
        lines.append("(none yet)")
        lines.append("")
        return "\n".join(lines)
    for t in traits:
        lines.extend(
            [
                f"## {t['trait']}",
                f"- confidence: {t['confidence']}",
                f"- status: {t['status']}",
                f"- first observed: {t['first_observed']}",
                f"- last reviewed: {t['last_reviewed']}",
                f"- evidence count: {t['evidence_count']}",
                f"- summary: {t['summary']}",
                "",
            ]
        )
    return "\n".join(lines)
