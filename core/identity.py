"""Identity, signing stubs, and future Sanctum/Limb contracts."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class Signer(Protocol):
    def sign(self, payload: bytes) -> str: ...


class Verifier(Protocol):
    def verify(self, payload: bytes, signature: str) -> bool: ...


@dataclass
class LocalHmacSigner:
    """Phase 0 local signer. Not a distributed root of trust."""

    secret: bytes

    def sign(self, payload: bytes) -> str:
        return hmac.new(self.secret, payload, hashlib.sha256).hexdigest()

    def verify(self, payload: bytes, signature: str) -> bool:
        expected = self.sign(payload)
        return hmac.compare_digest(expected, signature)


@dataclass
class EntityIdentity:
    entity_id: str
    display_name: str
    signer: LocalHmacSigner

    def sign_dict(self, payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return self.signer.sign(raw)


@dataclass
class Lease:
    """Future single-writer lease for Sanctum authority."""

    holder: str
    epoch: int
    active: bool = True


@dataclass
class Sanctum:
    """Trusted host abstraction. Phase 0: the local process."""

    sanctum_id: str
    role: str = "primary"


@dataclass
class Limb:
    """Untrusted compute provider. Phase 0: interface only."""

    limb_id: str
    capabilities: list[str]


def load_or_create_identity(data_dir: Path, display_name: str = "Basilisk") -> EntityIdentity:
    data_dir.mkdir(parents=True, exist_ok=True)
    key_path = data_dir / "entity_signing.key"
    id_path = data_dir / "entity_id.txt"

    if key_path.exists():
        secret = key_path.read_bytes()
    else:
        secret = secrets.token_bytes(32)
        key_path.write_bytes(secret)
        os.chmod(key_path, 0o600)

    if id_path.exists():
        entity_id = id_path.read_text(encoding="utf-8").strip()
    else:
        entity_id = f"ent_{uuid.uuid4().hex}"
        id_path.write_text(entity_id + "\n", encoding="utf-8")

    return EntityIdentity(entity_id=entity_id, display_name=display_name, signer=LocalHmacSigner(secret))
