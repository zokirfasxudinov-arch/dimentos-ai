"""
Memory / Obsidian vault endpoints.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

VAULT_PATH = Path("/app/obsidian-vault")


class WriteNoteRequest(BaseModel):
    path: str  # Relative to vault root, e.g. "01_Memory/Current_Context.md"
    content: str
    append: bool = False


@router.get("/memory/notes")
async def list_notes():
    """List all markdown files in the vault."""
    if not VAULT_PATH.exists():
        return {"notes": [], "message": "Vault not mounted"}

    notes = []
    for f in VAULT_PATH.rglob("*.md"):
        notes.append(str(f.relative_to(VAULT_PATH)))
    return {"notes": sorted(notes), "total": len(notes)}


@router.get("/memory/notes/{path:path}")
async def read_note(path: str):
    """Read a specific note from the vault."""
    note_path = VAULT_PATH / path
    if not note_path.exists():
        raise HTTPException(status_code=404, detail=f"Note '{path}' not found")
    if not note_path.is_file():
        raise HTTPException(status_code=400, detail="Path is a directory, not a file")

    content = note_path.read_text(encoding="utf-8")
    return {"path": path, "content": content, "size": len(content)}


@router.post("/memory/notes")
async def write_note(body: WriteNoteRequest):
    """Write or append to a note in the vault."""
    note_path = VAULT_PATH / body.path
    note_path.parent.mkdir(parents=True, exist_ok=True)

    if body.append and note_path.exists():
        existing = note_path.read_text(encoding="utf-8")
        note_path.write_text(existing + "\n" + body.content, encoding="utf-8")
    else:
        note_path.write_text(body.content, encoding="utf-8")

    return {"path": body.path, "status": "written"}


@router.delete("/memory/notes/{path:path}")
async def delete_note(path: str):
    """Delete a note from the vault."""
    note_path = VAULT_PATH / path
    if not note_path.exists():
        raise HTTPException(status_code=404, detail=f"Note '{path}' not found")
    note_path.unlink()
    return {"deleted": path}


@router.get("/memory/search")
async def search_notes(q: str):
    """Simple text search across all vault notes."""
    if not VAULT_PATH.exists():
        return {"results": [], "message": "Vault not mounted"}

    results = []
    for f in VAULT_PATH.rglob("*.md"):
        try:
            content = f.read_text(encoding="utf-8")
            if q.lower() in content.lower():
                # Find context around match
                idx = content.lower().index(q.lower())
                snippet = content[max(0, idx - 50): idx + 100]
                results.append({
                    "path": str(f.relative_to(VAULT_PATH)),
                    "snippet": snippet,
                })
        except Exception:
            pass

    return {"query": q, "results": results, "total": len(results)}
