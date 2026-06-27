"""
Memory Agent - Reads and writes to the Obsidian vault.
Uses pathlib only, no subprocess calls.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from agents.base import BaseAgent, ActionResult, RiskLevel


class MemoryAgent(BaseAgent):
    """
    Memory Agent manages the Obsidian vault.
    Reading is LOW risk. Writing/deleting is MEDIUM risk.
    """

    name = "memory"
    default_risk_level = RiskLevel.LOW
    vault_path: Path = Path("/app/obsidian-vault")

    def __init__(self, vault_path: Optional[Path] = None):
        super().__init__()
        if vault_path:
            self.vault_path = vault_path

    def assess_risk(self, task: str, params: Optional[dict] = None) -> str:
        task_lower = task.lower()
        if any(kw in task_lower for kw in ["delete", "remove", "overwrite", "clear"]):
            return RiskLevel.HIGH
        if any(kw in task_lower for kw in ["write", "save", "update", "append"]):
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    async def execute(self, task: str, params: Optional[dict] = None) -> ActionResult:
        params = params or {}
        task_lower = task.lower()

        if "read" in task_lower or "recall" in task_lower:
            return await self._read_note(params.get("path", "01_Memory/Current_Context.md"))
        elif "write" in task_lower or "save" in task_lower:
            return await self._write_note(
                path=params.get("path", "01_Memory/Current_Context.md"),
                content=params.get("content", ""),
                append=params.get("append", False),
            )
        elif "list" in task_lower:
            return await self._list_notes()
        elif "search" in task_lower:
            return await self._search_notes(params.get("query", ""))
        elif "delete" in task_lower:
            return await self._delete_note(params.get("path", ""))
        else:
            return ActionResult(
                success=False,
                error=f"Unknown memory task: {task}. Use: read, write, list, search, delete",
            )

    async def _read_note(self, path: str) -> ActionResult:
        note_path = self.vault_path / path
        if not note_path.exists():
            return ActionResult(success=False, error=f"Note not found: {path}")
        content = note_path.read_text(encoding="utf-8")
        self.logger.info(f"Read note: {path} ({len(content)} chars)")
        return ActionResult(success=True, data={"path": path, "content": content})

    async def _write_note(self, path: str, content: str, append: bool = False) -> ActionResult:
        if not content:
            return ActionResult(success=False, error="Content cannot be empty")

        note_path = self.vault_path / path
        note_path.parent.mkdir(parents=True, exist_ok=True)

        if append and note_path.exists():
            existing = note_path.read_text(encoding="utf-8")
            note_path.write_text(existing + "\n" + content, encoding="utf-8")
        else:
            note_path.write_text(content, encoding="utf-8")

        self.logger.info(f"{'Appended to' if append else 'Wrote'} note: {path}")
        return ActionResult(success=True, data={"path": path, "action": "append" if append else "write"})

    async def _list_notes(self) -> ActionResult:
        if not self.vault_path.exists():
            return ActionResult(success=False, error="Vault not found")
        notes = [str(f.relative_to(self.vault_path)) for f in self.vault_path.rglob("*.md")]
        return ActionResult(success=True, data={"notes": sorted(notes), "total": len(notes)})

    async def _search_notes(self, query: str) -> ActionResult:
        if not query:
            return ActionResult(success=False, error="Query cannot be empty")
        if not self.vault_path.exists():
            return ActionResult(success=False, error="Vault not found")

        results = []
        for f in self.vault_path.rglob("*.md"):
            try:
                content = f.read_text(encoding="utf-8")
                if query.lower() in content.lower():
                    idx = content.lower().index(query.lower())
                    snippet = content[max(0, idx - 50): idx + 100]
                    results.append({
                        "path": str(f.relative_to(self.vault_path)),
                        "snippet": snippet,
                    })
            except Exception:
                pass

        return ActionResult(success=True, data={"query": query, "results": results})

    async def _delete_note(self, path: str) -> ActionResult:
        if not path:
            return ActionResult(success=False, error="Path required")
        note_path = self.vault_path / path
        if not note_path.exists():
            return ActionResult(success=False, error=f"Note not found: {path}")
        note_path.unlink()
        self.logger.warning(f"Deleted note: {path}")
        return ActionResult(success=True, data={"deleted": path})
