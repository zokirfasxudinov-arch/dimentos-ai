"""
GitHub integration endpoints.
GitHub Agent prepares actions but never auto-pushes without approval.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.config import settings

router = APIRouter()


class RepoCreateRequest(BaseModel):
    name: str
    description: str = ""
    private: bool = True


class CommitPrepareRequest(BaseModel):
    repo: str
    branch: str = "main"
    message: str
    files: dict  # {filename: content}


@router.get("/github/status")
async def github_status():
    """Check GitHub integration status."""
    return {
        "configured": bool(settings.github_token),
        "user": settings.github_user if settings.github_user else "not configured",
        "note": "GitHub token must be set in .env to enable full functionality",
    }


@router.post("/github/repos/prepare")
async def prepare_repo_create(body: RepoCreateRequest):
    """
    Prepare a repository creation request.
    Requires MEDIUM approval before actual GitHub API call is made.
    """
    return {
        "action": "create_repo",
        "data": body.model_dump(),
        "requires_approval": True,
        "risk_level": "MEDIUM",
        "message": "Submit this to /api/approvals/create to request approval",
    }


@router.post("/github/commits/prepare")
async def prepare_commit(body: CommitPrepareRequest):
    """
    Prepare a commit. Staged locally, requires HIGH approval to push.
    """
    return {
        "action": "push_commit",
        "data": body.model_dump(),
        "requires_approval": True,
        "risk_level": "HIGH",
        "message": "Submit this to /api/approvals/create to request approval",
    }


@router.get("/github/repos")
async def list_repos():
    """List repos (requires GitHub token)."""
    if not settings.github_token:
        raise HTTPException(
            status_code=503,
            detail="GitHub token not configured. Set GITHUB_TOKEN in .env",
        )
    return {
        "message": "Use GitHub API with configured token",
        "user": settings.github_user,
        "api_endpoint": f"https://api.github.com/users/{settings.github_user}/repos",
    }
