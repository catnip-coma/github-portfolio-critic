from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class GitHubUserProfile(BaseModel):
    """Normalized GitHub User Profile."""
    login: str
    id: int
    name: Optional[str] = None
    avatar_url: str
    html_url: str
    bio: Optional[str] = None
    company: Optional[str] = None
    blog: Optional[str] = None
    location: Optional[str] = None
    email: Optional[str] = None
    public_repos: int = 0
    public_gists: int = 0
    followers: int = 0
    following: int = 0
    created_at: datetime
    updated_at: datetime
    has_profile_readme: bool = False
    profile_readme_snippet: Optional[str] = None


class GitHubRepo(BaseModel):
    """Normalized GitHub Repository Information."""
    name: str
    full_name: str
    html_url: str
    description: Optional[str] = None
    homepage: Optional[str] = None
    is_fork: bool = False
    is_archived: bool = False
    created_at: datetime
    updated_at: datetime
    pushed_at: Optional[datetime] = None
    size_kb: int = 0
    stargazers_count: int = 0
    watchers_count: int = 0
    forks_count: int = 0
    open_issues_count: int = 0
    language: Optional[str] = None
    topics: List[str] = Field(default_factory=list)
    license_name: Optional[str] = None
    has_readme: bool = False
    readme_char_count: int = 0
    readme_snippet: Optional[str] = None


class GitHubUserData(BaseModel):
    """Complete aggregated GitHub data for a user."""
    profile: GitHubUserProfile
    repositories: List[GitHubRepo]
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    from_cache: bool = False
    rate_limit_remaining: Optional[int] = None
    rate_limit_reset: Optional[int] = None


class ErrorResponse(BaseModel):
    """Standardized API error response."""
    error: str
    detail: Optional[str] = None
    status_code: int


class EvidenceItem(BaseModel):
    """Factual, verifiable evidence item behind a score."""
    metric: str
    value: Any
    total: Optional[Any] = None
    evidence: str


class CategoryScore(BaseModel):
    """Detailed score for one of the five portfolio dimensions."""
    name: str
    weight: float
    score: float
    weighted_score: float
    evidence: List[EvidenceItem] = Field(default_factory=list)


class PortfolioScoreResult(BaseModel):
    """Complete deterministic scoring output for a GitHub portfolio."""
    overall_score: float
    category_scores: Dict[str, CategoryScore]
    metric_values: Dict[str, Any]
    all_evidence: List[EvidenceItem]

