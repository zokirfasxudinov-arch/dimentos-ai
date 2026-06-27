"""
Project management endpoints.
"""
from __future__ import annotations

from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.models import Project

router = APIRouter()


class CreateProjectRequest(BaseModel):
    name: str
    description: Optional[str] = None
    status: str = "active"


@router.get("/projects")
async def list_projects(db: AsyncSession = Depends(get_db)):
    stmt = select(Project).order_by(Project.created_at.desc())
    result = await db.execute(stmt)
    items = result.scalars().all()
    return {"items": [item.to_dict() for item in items]}


@router.post("/projects")
async def create_project(
    body: CreateProjectRequest,
    db: AsyncSession = Depends(get_db),
):
    project = Project(
        id=str(uuid4()),
        name=body.name,
        description=body.description,
        status=body.status,
    )
    db.add(project)
    await db.flush()
    return project.to_dict()


@router.get("/projects/{project_id}")
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.to_dict()


@router.patch("/projects/{project_id}/status")
async def update_project_status(
    project_id: str,
    status: str,
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project.status = status
    await db.flush()
    return project.to_dict()
