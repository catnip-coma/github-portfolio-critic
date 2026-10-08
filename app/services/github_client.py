import asyncio
import base64
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
import httpx
from cachetools import TTLCache

from app.models.schemas import GitHubUserProfile, GitHubRepo, GitHubUserData

logger = logging.getLogger(__name__)


class GitHubClientError(Exception):
    """Base exception for GitHub client errors."""
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class UserNotFoundError(GitHubClientError):
    """Raised when a specified GitHub username does not exist."""
    def __init__(self, username: str):
        super().__init__(f"GitHub user '{username}' was not found.", status_code=404)
        self.username = username


class RateLimitExceededError(GitHubClientError):
    """Raised when GitHub API rate limit is exceeded."""
    def __init__(self, reset_time: Optional[int] = None):
        msg = "GitHub API rate limit exceeded."
        if reset_time:
            reset_dt = datetime.fromtimestamp(reset_time, timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            msg += f" Rate limit resets at {reset_dt}."
        msg += " Tip: Provide a GITHUB_TOKEN in your .env to increase the limit from 60 to 5,000 requests/hr."
        super().__init__(msg, status_code=429)
        self.reset_time = reset_time


class GitHubClient:
    """Asynchronous client for interacting with the public GitHub REST API with in-memory caching."""

    def __init__(
        self,
        token: Optional[str] = None,
        base_url: str = "https://api.github.com",
        cache_ttl_seconds: int = 600,
        cache_max_size: int = 100,
        timeout: float = 12.0
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token.strip() if token and token.strip() else None
        self.timeout = timeout
        self._cache: TTLCache[str, GitHubUserData] = TTLCache(maxsize=cache_max_size, ttl=cache_ttl_seconds)

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GitGauge-Portfolio-Critic/0.1.0"
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _handle_response_errors(self, response: httpx.Response, username: str) -> None:
        if response.status_code == 404:
            raise UserNotFoundError(username=username)

        if response.status_code == 403:
            remaining = response.headers.get("x-ratelimit-remaining")
            reset_ts = response.headers.get("x-ratelimit-reset")
            if remaining == "0" or "rate limit" in response.text.lower():
                reset_int = int(reset_ts) if reset_ts and reset_ts.isdigit() else None
                raise RateLimitExceededError(reset_time=reset_int)
            raise GitHubClientError(f"GitHub access forbidden: {response.text}", status_code=403)

        if response.status_code >= 400:
            raise GitHubClientError(
                f"GitHub API error ({response.status_code}): {response.text[:200]}",
                status_code=response.status_code
            )

    async def get_user_profile(self, client: httpx.AsyncClient, username: str) -> Tuple[GitHubUserProfile, Dict[str, Any]]:
        url = f"{self.base_url}/users/{username}"
        try:
            resp = await client.get(url, headers=self._get_headers())
        except httpx.RequestError as exc:
            raise GitHubClientError(f"Network error contacting GitHub: {exc}", status_code=502)

        self._handle_response_errors(resp, username)
        data = resp.json()

        rate_info = {
            "remaining": int(resp.headers.get("x-ratelimit-remaining", 0)) if resp.headers.get("x-ratelimit-remaining") else None,
            "reset": int(resp.headers.get("x-ratelimit-reset", 0)) if resp.headers.get("x-ratelimit-reset") else None,
        }

        profile = GitHubUserProfile(
            login=data["login"],
            id=data["id"],
            name=data.get("name"),
            avatar_url=data.get("avatar_url", ""),
            html_url=data.get("html_url", ""),
            bio=data.get("bio"),
            company=data.get("company"),
            blog=data.get("blog"),
            location=data.get("location"),
            email=data.get("email"),
            public_repos=data.get("public_repos", 0),
            public_gists=data.get("public_gists", 0),
            followers=data.get("followers", 0),
            following=data.get("following", 0),
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")),
        )
        return profile, rate_info

    async def get_user_repos(self, client: httpx.AsyncClient, username: str, max_repos: int = 30) -> List[Dict[str, Any]]:
        # Fetch repos sorted by pushed date (most recently active first)
        url = f"{self.base_url}/users/{username}/repos"
        params = {
            "per_page": min(max_repos, 100),
            "sort": "pushed",
            "direction": "desc",
            "type": "owner"
        }
        try:
            resp = await client.get(url, headers=self._get_headers(), params=params)
        except httpx.RequestError as exc:
            raise GitHubClientError(f"Network error fetching repositories: {exc}", status_code=502)

        self._handle_response_errors(resp, username)
        return resp.json()

    async def get_readme_data(self, client: httpx.AsyncClient, owner: str, repo: str) -> Tuple[bool, int, Optional[str]]:
        """Fetch README for a specific repository. Returns (has_readme, char_count, snippet)."""
        url = f"{self.base_url}/repos/{owner}/{repo}/readme"
        try:
            resp = await client.get(url, headers=self._get_headers())
            if resp.status_code == 200:
                data = resp.json()
                content_b64 = data.get("content", "")
                if content_b64:
                    raw_text = base64.b64decode(content_b64).decode("utf-8", errors="replace")
                    clean_text = raw_text.strip()
                    char_count = len(clean_text)
                    snippet = clean_text[:1500] if clean_text else None
                    return True, char_count, snippet
            return False, 0, None
        except Exception:
            return False, 0, None

    async def get_profile_readme(self, client: httpx.AsyncClient, username: str) -> Tuple[bool, Optional[str]]:
        """Check for user profile special repository: username/username."""
        has_readme, _, snippet = await self.get_readme_data(client, username, username)
        return has_readme, snippet

    async def get_full_user_data(self, username: str, max_repos: int = 30) -> GitHubUserData:
        """
        Fetch full user profile, repositories, and README summaries.
        Returns cached data if available.
        """
        cache_key = username.strip().lower()
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            # Create a shallow copy with from_cache=True
            return cached.model_copy(update={"from_cache": True})

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # 1. Fetch Profile
            profile, rate_info = await self.get_user_profile(client, username)

            # 2. Fetch Repositories
            raw_repos = await self.get_user_repos(client, username, max_repos=max_repos)

            # 3. Check for Special Profile README ({username}/{username})
            has_profile_readme, profile_readme_snippet = await self.get_profile_readme(client, profile.login)
            profile.has_profile_readme = has_profile_readme
            profile.profile_readme_snippet = profile_readme_snippet

            # 4. Process Repositories & Select Top 5 for README fetching
            # Prioritize non-forks, highest stars or recent pushes
            parsed_repos: List[GitHubRepo] = []
            for r in raw_repos:
                parsed_repos.append(GitHubRepo(
                    name=r["name"],
                    full_name=r["full_name"],
                    html_url=r["html_url"],
                    description=r.get("description"),
                    homepage=r.get("homepage") or None,
                    is_fork=bool(r.get("fork", False)),
                    is_archived=bool(r.get("archived", False)),
                    created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
                    updated_at=datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00")),
                    pushed_at=datetime.fromisoformat(r["pushed_at"].replace("Z", "+00:00")) if r.get("pushed_at") else None,
                    size_kb=r.get("size", 0),
                    stargazers_count=r.get("stargazers_count", 0),
                    watchers_count=r.get("watchers_count", 0),
                    forks_count=r.get("forks_count", 0),
                    open_issues_count=r.get("open_issues_count", 0),
                    language=r.get("language"),
                    topics=r.get("topics", []),
                    license_name=r.get("license", {}).get("name") if r.get("license") else None,
                ))

            # Pick top 5 featured repos for README inspection (prefer non-forks, sorted by stars desc, then size desc)
            featured_repos = sorted(
                parsed_repos,
                key=lambda x: (not x.is_fork, x.stargazers_count, x.size_kb),
                reverse=True
            )[:5]

            # Fetch READMEs concurrently for featured repos
            readme_tasks = [
                self.get_readme_data(client, profile.login, repo.name)
                for repo in featured_repos
            ]
            readme_results = await asyncio.gather(*readme_tasks, return_exceptions=True)

            for repo, res in zip(featured_repos, readme_results):
                if isinstance(res, tuple) and len(res) == 3:
                    has_readme, char_count, snippet = res
                    repo.has_readme = has_readme
                    repo.readme_char_count = char_count
                    repo.readme_snippet = snippet

            user_data = GitHubUserData(
                profile=profile,
                repositories=parsed_repos,
                fetched_at=datetime.utcnow(),
                from_cache=False,
                rate_limit_remaining=rate_info.get("remaining"),
                rate_limit_reset=rate_info.get("reset"),
            )

            # Store in cache
            self._cache[cache_key] = user_data
            return user_data
