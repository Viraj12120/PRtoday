"""Tests for PR Today V2 API."""

import pytest
from httpx import AsyncClient, ASGITransport
from pr_today.api.main import app
from pr_today.config import settings
from pr_today.database import init_db

import pytest_asyncio

@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    from unittest.mock import patch
    with patch("pr_today.database._resolve_database_url", return_value="sqlite+aiosqlite:///:memory:"):
        await init_db()
        yield

@pytest_asyncio.fixture
async def async_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

@pytest.mark.asyncio
async def test_health_endpoint(async_client):
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["ok", "degraded"]  # degraded if redis is down

@pytest.mark.asyncio
async def test_history_unauthorized(async_client):
    settings.API_AUTH_TOKEN = "secret123"
    response = await async_client.get("/history")
    assert response.status_code == 401
    assert "Invalid or missing API Key" in response.text

@pytest.mark.asyncio
async def test_history_authorized(async_client):
    settings.API_AUTH_TOKEN = "secret123"
    headers = {"X-API-Key": "secret123"}
    response = await async_client.get("/history", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert data["count"] == 0

@pytest.mark.asyncio
async def test_analyze_unauthorized(async_client):
    settings.API_AUTH_TOKEN = "secret123"
    response = await async_client.post("/analyze", json={
        "repo": "org/repo",
        "pr_number": 1,
        "user_id": "test"
    })
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_request_id_middleware(async_client):
    settings.API_AUTH_TOKEN = "secret123"
    headers = {"X-API-Key": "secret123"}
    response = await async_client.get("/health", headers=headers)
    assert "X-Request-ID" in response.headers
