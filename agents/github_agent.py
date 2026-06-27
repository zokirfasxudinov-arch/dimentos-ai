"""
GitHub Agent - Manages repositories and commits.
All push operations require HIGH approval.
No credentials are hardcoded here.
"""
from __future__ import annotations

from typing import Optional

import httpx
from loguru import logger

from agents.base import BaseAgent, ActionResult, RiskLevel
from core.config import settings


class GitHubAgent(BaseAgent):
    """
    GitHub Agent prepares and stages git operations.
    Actual pushes always require HIGH approval.
    """

    name = "github"
    default_risk_level = RiskLevel.HIGH  # GitHub actions are always high-stakes
    api_base = "https://api.github.com"

    def assess_risk(self, task: str, params: Optional[dict] = None) -> str:
        task_lower = task.lower()
        if any(kw in task_lower for kw in ["delete", "force", "drop", "destroy"]):
            return RiskLevel.HIGH
        if any(kw in task_lower for kw in ["push", "commit", "create", "merge"]):
            return RiskLevel.HIGH
        if any(kw in task_lower for kw in ["read", "list", "status", "info"]):
            return RiskLevel.LOW
        return RiskLevel.MEDIUM

    async def execute(self, task: str, params: Optional[dict] = None) -> ActionResult:
        params = params or {}
        task_lower = task.lower()

        if "list" in task_lower and "repo" in task_lower:
            return await self._list_repos()
        elif "repo" in task_lower and "info" in task_lower:
            return await self._get_repo_info(params.get("repo", ""))
        elif "prepare" in task_lower or "stage" in task_lower:
            return await self._prepare_commit(
                repo=params.get("repo", ""),
                message=params.get("message", ""),
                files=params.get("files", {}),
            )
        elif "push" in task_lower or "commit" in task_lower:
            return await self._push_commit(
                repo=params.get("repo", ""),
                branch=params.get("branch", "main"),
                message=params.get("message", ""),
                files=params.get("files", {}),
            )
        else:
            return ActionResult(
                success=False,
                error=f"Unknown GitHub task: {task}",
            )

    async def _list_repos(self) -> ActionResult:
        if not settings.github_token:
            return ActionResult(
                success=False,
                error="GITHUB_TOKEN not configured. Set it in .env",
            )
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self.api_base}/user/repos",
                headers={"Authorization": f"token {settings.github_token}"},
                params={"per_page": 30, "sort": "updated"},
                timeout=15,
            )
            r.raise_for_status()
            repos = [
                {
                    "name": repo["name"],
                    "full_name": repo["full_name"],
                    "private": repo["private"],
                    "url": repo["html_url"],
                    "updated_at": repo["updated_at"],
                }
                for repo in r.json()
            ]
        return ActionResult(success=True, data={"repos": repos, "total": len(repos)})

    async def _get_repo_info(self, repo: str) -> ActionResult:
        if not repo:
            return ActionResult(success=False, error="Repo name required")
        if not settings.github_token:
            return ActionResult(success=False, error="GITHUB_TOKEN not configured")

        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self.api_base}/repos/{settings.github_user}/{repo}",
                headers={"Authorization": f"token {settings.github_token}"},
                timeout=15,
            )
            r.raise_for_status()
            data = r.json()

        return ActionResult(success=True, data={
            "name": data["name"],
            "description": data.get("description"),
            "private": data["private"],
            "stars": data["stargazers_count"],
            "forks": data["forks_count"],
            "default_branch": data["default_branch"],
            "url": data["html_url"],
        })

    async def _prepare_commit(self, repo: str, message: str, files: dict) -> ActionResult:
        """Stage a commit locally - does NOT push."""
        self.logger.info(f"Preparing commit for {repo}: {message} ({len(files)} files)")
        return ActionResult(success=True, data={
            "status": "staged",
            "repo": repo,
            "message": message,
            "files": list(files.keys()),
            "note": "Commit prepared. Submit approval request to push.",
        })

    async def _push_commit(
        self, repo: str, branch: str, message: str, files: dict
    ) -> ActionResult:
        """
        Actually push to GitHub via API.
        This method is only reached after HIGH approval.
        """
        if not settings.github_token:
            return ActionResult(success=False, error="GITHUB_TOKEN not configured")
        if not all([repo, message, files]):
            return ActionResult(success=False, error="repo, message, and files are required")

        self.logger.warning(f"Pushing to {repo}/{branch}: {message}")

        # For each file, use GitHub Contents API
        pushed = []
        errors = []

        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"token {settings.github_token}"}

            for filename, content in files.items():
                import base64
                encoded = base64.b64encode(content.encode()).decode()

                # Check if file exists (to get SHA for update)
                sha = None
                try:
                    check = await client.get(
                        f"{self.api_base}/repos/{settings.github_user}/{repo}/contents/{filename}",
                        headers=headers,
                        params={"ref": branch},
                        timeout=10,
                    )
                    if check.status_code == 200:
                        sha = check.json().get("sha")
                except Exception:
                    pass

                payload = {
                    "message": message,
                    "content": encoded,
                    "branch": branch,
                    "committer": {
                        "name": settings.github_user,
                        "email": settings.github_email,
                    },
                }
                if sha:
                    payload["sha"] = sha

                r = await client.put(
                    f"{self.api_base}/repos/{settings.github_user}/{repo}/contents/{filename}",
                    headers=headers,
                    json=payload,
                    timeout=15,
                )
                if r.status_code in (200, 201):
                    pushed.append(filename)
                else:
                    errors.append(f"{filename}: {r.text}")

        if errors:
            return ActionResult(success=False, data={"pushed": pushed}, error="; ".join(errors))
        return ActionResult(success=True, data={"pushed": pushed, "repo": repo, "branch": branch})
