"""
GitHub integration endpoints.
Read operations are direct. Write operations require approval.
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.config import settings

router = APIRouter()
GH_API = "https://api.github.com"


def _gh_headers() -> dict:
    if not settings.github_token:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN не настроен в .env")
    return {
        "Authorization": f"token {settings.github_token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


class RepoCreateRequest(BaseModel):
    name: str
    description: str = ""
    private: bool = True


class CommitPrepareRequest(BaseModel):
    repo: str
    branch: str = "main"
    message: str
    files: dict


@router.get("/github/status")
async def github_status():
    """Check GitHub integration status — calls real API if token set."""
    if not settings.github_token:
        return {
            "configured": False,
            "user": settings.github_user or "не настроен",
            "repo": None,
            "message": "Установи GITHUB_TOKEN в .env",
        }
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{GH_API}/user", headers=_gh_headers(), timeout=8)
            r.raise_for_status()
            data = r.json()
        return {
            "configured": True,
            "user": data.get("login", settings.github_user),
            "name": data.get("name", ""),
            "public_repos": data.get("public_repos", 0),
            "private_repos": data.get("total_private_repos", 0),
            "avatar_url": data.get("avatar_url", ""),
            "profile_url": data.get("html_url", ""),
        }
    except HTTPException:
        raise
    except Exception as e:
        return {"configured": False, "user": settings.github_user, "error": str(e)}


@router.get("/github/repos")
async def list_repos():
    """List all repositories for the authenticated user."""
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{GH_API}/user/repos",
            headers=_gh_headers(),
            params={"per_page": 50, "sort": "updated", "type": "all"},
            timeout=15,
        )
        r.raise_for_status()
    return {
        "repos": [
            {
                "name": repo["name"],
                "full_name": repo["full_name"],
                "description": repo.get("description", ""),
                "private": repo["private"],
                "url": repo["html_url"],
                "default_branch": repo.get("default_branch", "main"),
                "updated_at": repo["updated_at"],
                "language": repo.get("language", ""),
                "stars": repo.get("stargazers_count", 0),
            }
            for repo in r.json()
        ]
    }


@router.post("/github/repos/create")
async def create_repo(body: RepoCreateRequest):
    """Create a GitHub repository (call only after approval)."""
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{GH_API}/user/repos",
            headers=_gh_headers(),
            json={"name": body.name, "description": body.description, "private": body.private, "auto_init": True},
            timeout=15,
        )
        if r.status_code == 422:
            raise HTTPException(status_code=422, detail=f"Репозиторий уже существует: {body.name}")
        r.raise_for_status()
        data = r.json()
    return {"created": True, "name": data["name"], "url": data["html_url"], "clone_url": data["clone_url"]}


@router.get("/github/repos/{repo}/commits")
async def list_commits(repo: str, limit: int = 10):
    """List recent commits in a repository."""
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{GH_API}/repos/{settings.github_user}/{repo}/commits",
            headers=_gh_headers(),
            params={"per_page": limit},
            timeout=15,
        )
        r.raise_for_status()
    return {
        "repo": repo,
        "commits": [
            {
                "sha": c["sha"][:8],
                "message": c["commit"]["message"].split("\n")[0][:80],
                "author": c["commit"]["author"]["name"],
                "date": c["commit"]["author"]["date"],
            }
            for c in r.json()
        ],
    }


@router.post("/github/repos/prepare")
async def prepare_repo_create(body: RepoCreateRequest):
    return {"action": "create_repo", "data": body.model_dump(), "requires_approval": True, "risk_level": "MEDIUM"}


@router.post("/github/commits/prepare")
async def prepare_commit(body: CommitPrepareRequest):
    return {"action": "push_commit", "data": body.model_dump(), "requires_approval": True, "risk_level": "HIGH"}
