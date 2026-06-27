"""
Task management endpoints.
"""
from __future__ import annotations

from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.models import Task

router = APIRouter()


class CreateTaskRequest(BaseModel):
    title: str
    description: Optional[str] = None
    agent: Optional[str] = None
    project_id: Optional[str] = None
    priority: str = "medium"


class UpdateTaskRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    agent: Optional[str] = None


@router.get("/tasks")
async def list_tasks(
    status: Optional[str] = None,
    agent: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Task)
    if status:
        stmt = stmt.where(Task.status == status)
    if agent:
        stmt = stmt.where(Task.agent == agent)
    stmt = stmt.order_by(Task.created_at.desc()).limit(100)
    result = await db.execute(stmt)
    items = result.scalars().all()
    return {"items": [item.to_dict() for item in items], "total": len(items)}


@router.post("/tasks")
async def create_task(
    body: CreateTaskRequest,
    db: AsyncSession = Depends(get_db),
):
    task = Task(
        id=str(uuid4()),
        title=body.title,
        description=body.description,
        agent=body.agent,
        project_id=body.project_id,
        priority=body.priority,
        status="pending",
    )
    db.add(task)
    await db.flush()
    return task.to_dict()


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task.to_dict()


@router.patch("/tasks/{task_id}")
async def update_task(
    task_id: str,
    body: UpdateTaskRequest,
    db: AsyncSession = Depends(get_db),
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if body.title is not None:
        task.title = body.title
    if body.description is not None:
        task.description = body.description
    if body.status is not None:
        task.status = body.status
    if body.priority is not None:
        task.priority = body.priority
    if body.agent is not None:
        task.agent = body.agent
    await db.flush()
    return task.to_dict()


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.delete(task)
    return {"deleted": task_id}
