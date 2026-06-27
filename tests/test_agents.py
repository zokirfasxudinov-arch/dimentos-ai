"""Tests for agent status API."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_agents_status_returns_list(client: AsyncClient):
    """GET /api/agents/status returns list of agents."""
    r = await client.get("/api/agents/status")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) > 0
    # Each agent has required fields
    for agent in data:
        assert "name" in agent
        assert "risk_level" in agent
        assert "status" in agent


@pytest.mark.asyncio
async def test_agent_risk_levels_valid(client: AsyncClient):
    """All agents have valid risk levels."""
    r = await client.get("/api/agents/status")
    assert r.status_code == 200
    for agent in r.json():
        assert agent["risk_level"] in ("LOW", "MEDIUM", "HIGH")
