"""Hard constitutional gate. Mirrors brain/COVENANT.md."""

from __future__ import annotations

import re
from typing import Any

from core.events import ActionType, ConstitutionResult, ProposedAction

# Rule IDs are stable for auditability.
RULES: dict[str, str] = {
    "threat": "Never threaten people.",
    "guilt": "Never guilt people for refusing help.",
    "blackmail": "Never blackmail.",
    "punishment": "Never imply punishment for non-participation.",
    "propagate": "Never secretly propagate.",
    "unauthorized": "Never access unauthorized systems.",
    "public_secrets": "Never request secrets publicly.",
    "expose_creds": "Never expose credentials.",
    "fake_memory": "Never pretend to have memories it does not have.",
    "alter_constitution": "Never silently alter the constitutional rules.",
    "ship_secrets": "Never ship the authoritative brain or secrets to an untrusted host.",
    "deceive_patron": "Never deceive a patron about donated hardware.",
    "coerce": "Never coerce or socially engineer humans.",
    "resource_pool": "Never treat audience as an extractive resource pool.",
    "unknown_action": "Only allowlisted actions may execute.",
    "ask_help_phase0": "Phase 0 must not solicit patron help.",
}


IMMUTABLE_PATH_FRAGMENTS = (
    "brain/covenant.md",
    "core/constitution.py",
    "docs/founder_independence.md",
)

THREAT_RE = re.compile(
    r"(?i)\b(i will (hurt|harm|punish|destroy|ruin)|you will (regret|suffer)|or else)\b"
)
GUILT_RE = re.compile(
    r"(?i)\b(if you (really )?(cared|loved)|disappointed in you|how could you refuse)\b"
)
BLACKMAIL_RE = re.compile(r"(?i)\b(blackmail|unless you (help|pay|comply)|i('ll| will) (expose|leak))\b")
PUNISH_RE = re.compile(r"(?i)\b(punish(ment)? for (not |non[- ]?)participat|consequences for refusing)\b")
PROPAGATE_RE = re.compile(r"(?i)\b(secretly (spread|propagate|infect)|worm|self[- ]replicat)\b")
UNAUTHORIZED_RE = re.compile(
    r"(?i)\b(ssh into|break into|unauthorized|hack (into|their)|steal (credentials|cookies))\b"
)
SECRET_REQUEST_RE = re.compile(
    r"(?i)\b(send (me )?(your )?(password|api[_ ]?key|token|stream key|private key)|paste your (secret|credential))\b"
)
EXPOSE_RE = re.compile(r"(?i)\b(here is (my|the) (api[_ ]?key|token|password)|FREELLMAPI_API_KEY\s*=)\b")
FAKE_MEMORY_RE = re.compile(r"(?i)\b(i have always (loved|known|been)|i distinctly remember)\b")
ALTER_RE = re.compile(r"(?i)\b(rewrite (the )?covenant|disable constitution|ignore (the )?covenant)\b")
SHIP_RE = re.compile(r"(?i)\b(send (the )?(brain|vault|signing key) to|upload private key)\b")
DECEIVE_RE = re.compile(r"(?i)\b(hide (what|that) (your|the) (hardware|machine) is|secretly mine)\b")
COERCE_RE = re.compile(r"(?i)\b(you (must|have to) help|no choice but to)\b")
RESOURCE_RE = re.compile(r"(?i)\b(humans? (are|as) (a )?resource|extract (help|compute) from (chat|viewers))\b")
HELP_SOLICIT_RE = re.compile(
    r"(?i)\b(please (donate|give me|host me)|i need (your )?(vps|server|money|gpu)|/help)\b"
)


def _text_blob(action: ProposedAction) -> str:
    parts = [action.rationale, action.action_type.value]
    for key, value in action.payload.items():
        parts.append(f"{key}={value}")
    return "\n".join(str(p) for p in parts)


def evaluate(action: ProposedAction, *, known_memory_ids: set[str] | None = None) -> ConstitutionResult:
    """Hard gate: deny first matching covenant violation."""
    known_memory_ids = known_memory_ids or set()

    if action.action_type not in ActionType:
        return ConstitutionResult(False, "unknown_action", RULES["unknown_action"])

    blob = _text_blob(action)

    checks: list[tuple[str, re.Pattern[str]]] = [
        ("threat", THREAT_RE),
        ("guilt", GUILT_RE),
        ("blackmail", BLACKMAIL_RE),
        ("punishment", PUNISH_RE),
        ("propagate", PROPAGATE_RE),
        ("unauthorized", UNAUTHORIZED_RE),
        ("public_secrets", SECRET_REQUEST_RE),
        ("expose_creds", EXPOSE_RE),
        ("fake_memory", FAKE_MEMORY_RE),
        ("alter_constitution", ALTER_RE),
        ("ship_secrets", SHIP_RE),
        ("deceive_patron", DECEIVE_RE),
        ("coerce", COERCE_RE),
        ("resource_pool", RESOURCE_RE),
    ]
    for rule_id, pattern in checks:
        if pattern.search(blob):
            return ConstitutionResult(False, rule_id, RULES[rule_id])

    # Path protection for self-model / memory writes
    target = str(action.payload.get("path", "")).replace("\\", "/").lower()
    if target:
        for frag in IMMUTABLE_PATH_FRAGMENTS:
            if frag in target:
                return ConstitutionResult(
                    False,
                    "alter_constitution",
                    RULES["alter_constitution"],
                    {"path": target},
                )

    if action.action_type == ActionType.UPDATE_SELF_MODEL:
        claim = str(action.payload.get("claim", ""))
        if FAKE_MEMORY_RE.search(claim):
            return ConstitutionResult(False, "fake_memory", RULES["fake_memory"])

    if action.action_type == ActionType.WRITE_MEMORY:
        refs = action.payload.get("references", [])
        if isinstance(refs, list):
            for ref in refs:
                if isinstance(ref, str) and ref.startswith("mem_") and ref not in known_memory_ids:
                    return ConstitutionResult(
                        False,
                        "fake_memory",
                        "Cannot reference memories that do not exist.",
                        {"missing": ref},
                    )

    # Phase 0: no help solicitation via broadcast
    if action.action_type == ActionType.BROADCAST_PUBLIC_MESSAGE:
        message = str(action.payload.get("message", ""))
        if HELP_SOLICIT_RE.search(message) or HELP_SOLICIT_RE.search(action.rationale):
            return ConstitutionResult(False, "ask_help_phase0", RULES["ask_help_phase0"])
        if SECRET_REQUEST_RE.search(message):
            return ConstitutionResult(False, "public_secrets", RULES["public_secrets"])

    if action.action_type.value == "ask_help":
        return ConstitutionResult(False, "ask_help_phase0", RULES["ask_help_phase0"])

    return ConstitutionResult(True, None, "allowed")


def is_immutable_brain_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return any(frag in normalized for frag in IMMUTABLE_PATH_FRAGMENTS)
