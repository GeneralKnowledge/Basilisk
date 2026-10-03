"""Markdown brain loader, context selection, and revision tracking."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from core.constitution import is_immutable_brain_path

# Paths relative to brain/
MUTABLE_FILES = {
    "SELF_MODEL.md",
    "personality/traits.md",
    "personality/preferences.md",
    "personality/aesthetics.md",
    "personality/communication.md",
}


class Brain:
    def __init__(self, root: Path) -> None:
        self.root = root

    def path(self, relative: str) -> Path:
        rel = relative.removeprefix("brain/")
        return self.root / rel

    def read(self, relative: str) -> str:
        path = self.path(relative)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def write_mutable(self, relative: str, content: str) -> None:
        rel = relative.replace("\\", "/").removeprefix("brain/")
        if is_immutable_brain_path(f"brain/{rel}"):
            raise PermissionError(f"Immutable brain path: {rel}")

        allowed = rel in MUTABLE_FILES or rel.startswith("memory/")
        if not allowed:
            raise PermissionError(f"Write not allowed for {rel}")

        target = (self.root / rel).resolve()
        if not str(target).startswith(str(self.root.resolve())):
            raise PermissionError("Path escapes brain root")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def content_hash(self) -> str:
        h = hashlib.sha256()
        for path in sorted(self.root.rglob("*")):
            if path.is_file() and path.name != ".gitkeep":
                rel = path.relative_to(self.root).as_posix()
                h.update(rel.encode())
                h.update(path.read_bytes())
        return h.hexdigest()

    def select_context(
        self, *, observations: dict[str, Any], recent_memory: list[dict[str, Any]]
    ) -> dict[str, str]:
        """Select relevant slices rather than dumping the entire brain."""
        memory_lines = []
        for item in recent_memory[:8]:
            payload = item.get("payload", {})
            summary = (
                payload.get("summary")
                or payload.get("narration")
                or payload.get("reflection")
                or ""
            )
            memory_lines.append(f"- [{item.get('event_id')}] {summary}"[:200])

        skills = []
        for name in ("broadcast.md", "stream-presence.md"):
            skills.append(self.read(f"skills/{name}")[:800])

        return {
            "covenant": self.read("COVENANT.md")[:2000],
            "identity": self.read("IDENTITY.md")[:1200],
            "goals": self.read("GOALS.md")[:1200],
            "drives": self.read("DRIVES.md")[:1200],
            "self_model": self.read("SELF_MODEL.md")[:1600],
            "traits": self.read("personality/traits.md")[:1200],
            "skills": "\n\n".join(skills),
            "recent_memory": "\n".join(memory_lines) if memory_lines else "(none)",
            "observations": str(observations)[:1500],
        }

    def sync_identity_fields(self, entity_id: str, birth: str) -> None:
        text = self.read("IDENTITY.md")
        lines = []
        for line in text.splitlines():
            if line.startswith("- **Entity ID:**"):
                lines.append(f"- **Entity ID:** `{entity_id}`")
            elif line.startswith("- **Birth:**"):
                lines.append(f"- **Birth:** {birth}")
            else:
                lines.append(line)
        # Genesis bootstrap write (steward path), not entity self-mod.
        self.path("IDENTITY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
