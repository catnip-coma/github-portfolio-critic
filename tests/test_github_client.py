import pytest
import httpx
from datetime import datetime, timezone
from app.services.github_client import (
    GitHubClient,
    UserNotFoundError,
    RateLimitExceededError,
    GitHubClientError,
)
from app.models.schemas import GitHubUserProfile, GitHubRepo, GitHubUserData


@pytest.fixture
def client():
    return GitHubClient(token=None, cache_ttl_seconds=60)


@pytest.mark.asyncio
async def test_client_init_and_headers():
    c_no_token = GitHubClient(token=None)
    headers = c_no_token._get_headers()
    assert "Authorization" not in headers
    assert "Accept" in headers

    c_with_token = GitHubClient(token="ghp_test123")
    headers_with_token = c_with_token._get_headers()
    assert headers_with_token["Authorization"] == "Bearer ghp_test123"


@pytest.mark.asyncio
async def test_user_not_found():
    client = GitHubClient()
    mock_response = httpx.Response(404, json={"message": "Not Found"})

    with pytest.raises(UserNotFoundError) as exc_info:
        client._handle_response_errors(mock_response, "nonexistentuser_999999")
    assert "nonexistentuser_999999" in str(exc_info.value)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_rate_limit_exceeded():
    client = GitHubClient()
    headers = {
        "x-ratelimit-remaining": "0",
        "x-ratelimit-reset": "1700000000"
    }
    mock_response = httpx.Response(403, headers=headers, json={"message": "API rate limit exceeded"})

    with pytest.raises(RateLimitExceededError) as exc_info:
        client._handle_response_errors(mock_response, "anyuser")
    assert exc_info.value.status_code == 429
    assert exc_info.value.reset_time == 1700000000


@pytest.mark.asyncio
async def test_cache_functionality(client):
    test_user = "testdev"
    fake_profile = GitHubUserProfile(
        login="testdev",
        id=123,
        name="Test Developer",
        avatar_url="https://example.com/avatar.png",
        html_url="https://github.com/testdev",
        bio="Full stack developer",
        public_repos=5,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        has_profile_readme=True
    )
    fake_data = GitHubUserData(
        profile=fake_profile,
        repositories=[],
        from_cache=False
    )

    # Insert into client cache
    client._cache[test_user.lower()] = fake_data

    # Retrieve from cache
    cached_result = await client.get_full_user_data(test_user)
    assert cached_result.from_cache is True
    assert cached_result.profile.login == "testdev"
    assert cached_result.profile.bio == "Full stack developer"
