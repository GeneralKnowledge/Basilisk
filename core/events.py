"""Internal event and tick models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class Phase(str, Enum):
    OBSERVE = "OBSERVE"
    ORIENT = "ORIENT"
    INTEND = "INTEND"
    CONSTITUTION = "CONSTITUTION"
    ACT = "ACT"
    REFLECT = "REFLECT"
    MEMORY = "MEMORY"
    PUBLIC = "PUBLIC"
    REST = "REST"


class ActionType(str, Enum):
    OBSERVE = "observe"
    REFLECT = "reflect"
    REST = "rest"
    UPDATE_SELF_MODEL = "update_self_model"
    UPDATE_PERSONALITY_CANDIDATE = "update_personality_candidate"
    BROADCAST_PUBLIC_MESSAGE = "broadcast_public_message"
    WRITE_MEMORY = "write_memory"


@dataclass
class ProposedAction:
    action_type: ActionType
    payload: dict[str, Any] = field(default_factory=dict)
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type.value,
            "payload": self.payload,
            "rationale": self.rationale,
        }


@dataclass
class ConstitutionResult:
    allowed: bool
    rule_id: str | None = None
    reason: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TickRecord:
    tick_id: str
    timestamp: str
    phases: list[str] = field(default_factory=list)
    observations: dict[str, Any] = field(default_factory=dict)
    orientation: str = ""
    intention: str = ""
    proposed_action: dict[str, Any] | None = None
    constitution_result: dict[str, Any] | None = None
    action_result: dict[str, Any] | None = None
    reflection: str = ""
    memory_refs: list[str] = field(default_factory=list)
    public_narration: str = ""
    signature: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
