import pytest
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.mark.asyncio
async def test_root_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert "endpoints" in data


@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "GitGauge"


@pytest.mark.asyncio
async def test_empty_username_validation():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/raw/%20")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_score_empty_username_validation():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/score/%20")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_score_endpoint_with_cached_user():
    from app.api.routes import get_github_client
    from app.models.schemas import GitHubUserProfile, GitHubRepo, GitHubUserData
    from datetime import datetime, timezone

    # Pre-populate cache on the client singleton
    client = get_github_client()
    fake_profile = GitHubUserProfile(
        login="cachedtester",
        id=555,
        name="Cached Dev",
        avatar_url="https://avatar.url",
        html_url="https://github.com/cachedtester",
        bio="Test Bio",
        public_repos=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        has_profile_readme=True,
    )
    fake_repo = GitHubRepo(
        name="hello-world",
        full_name="cachedtester/hello-world",
        html_url="https://github.com/cachedtester/hello-world",
        description="Demo project",
        language="Python",
        size_kb=100,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        pushed_at=datetime.now(timezone.utc),
        has_readme=True,
        readme_char_count=500,
        readme_snippet="## Installation\npip install .",
        license_name="MIT License"
    )
    client._cache["cachedtester"] = GitHubUserData(
        profile=fake_profile,
        repositories=[fake_repo],
        from_cache=False
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/score/cachedtester")
    assert response.status_code == 200
    data = response.json()
    assert "overall_score" in data
    assert "category_scores" in data
    assert "technical_depth" in data["category_scores"]
    assert "project_quality" in data["category_scores"]
    assert "documentation_and_presentation" in data["category_scores"]
    assert "activity_and_consistency" in data["category_scores"]
    assert "recruiter_readiness" in data["category_scores"]
    assert data["overall_score"] > 0

