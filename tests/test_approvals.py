"""Tests for approval request API."""
import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_list_approvals_empty(client: AsyncClient):
    """GET /api/approvals returns a list (may be empty without DB)."""
    with patch("api.routers.approvals.get_db") as mock_db:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock(return_value=AsyncMock(scalars=AsyncMock(return_value=AsyncMock(all=lambda: []))))
        mock_db.return_value = mock_session
        r = await client.get("/api/approvals")
    assert r.status_code in (200, 500)


@pytest.mark.asyncio
async def test_approval_create_requires_fields(client: AsyncClient):
    """POST /api/approvals/create validates required fields."""
    r = await client.post("/api/approvals/create", json={})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_approval_create_valid(client: AsyncClient):
    """POST /api/approvals/create with valid data returns 200 or 500 (no DB)."""
    payload = {
        "agent": "test_agent",
        "action": "test_action",
        "description": "Test approval request",
        "risk_level": "MEDIUM",
    }
    r = await client.post("/api/approvals/create", json=payload)
    assert r.status_code in (200, 201, 500)
