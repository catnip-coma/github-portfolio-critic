import pytest
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.mark.asyncio
async def test_root_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


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


@pytest.mark.asyncio
async def test_analyze_empty_username_validation():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/analyze/%20")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_analyze_endpoint_with_cached_user():
    from app.api.routes import get_github_client
    from app.models.schemas import GitHubUserProfile, GitHubRepo, GitHubUserData
    from datetime import datetime, timezone

    client = get_github_client()
    fake_profile = GitHubUserProfile(
        login="analyzetester",
        id=777,
        name="Analyze Dev",
        avatar_url="https://avatar.url/dev.png",
        html_url="https://github.com/analyzetester",
        bio="Backend systems engineer",
        public_repos=2,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        has_profile_readme=True,
    )
    fake_repo = GitHubRepo(
        name="distributed-queue",
        full_name="analyzetester/distributed-queue",
        html_url="https://github.com/analyzetester/distributed-queue",
        description="High throughput queue engine",
        language="Go",
        size_kb=350,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        pushed_at=datetime.now(timezone.utc),
        has_readme=True,
        readme_char_count=1200,
        readme_snippet="## Installation\ngo get .\n## Usage\nqueue run",
        license_name="Apache-2.0"
    )
    client._cache["analyzetester"] = GitHubUserData(
        profile=fake_profile,
        repositories=[fake_repo],
        from_cache=False
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/analyze/analyzetester")
    assert response.status_code == 200
    report = response.json()

    assert report["username"] == "analyzetester"
    assert "scores" in report
    assert "critique" in report
    assert report["scores"]["overall_score"] > 0

    critique = report["critique"]
    assert "recruiter_in_30_seconds" in critique
    assert "candidate_level_assessment" in critique
    assert len(critique["strengths"]) > 0
    assert len(critique["weaknesses"]) > 0
    assert len(critique["top_3_fixes"]) == 3
    assert len(critique["roadmap"]) == 3


