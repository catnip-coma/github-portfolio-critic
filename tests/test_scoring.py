import pytest
from datetime import datetime, timezone, timedelta
from typing import List

from app.models.schemas import GitHubUserProfile, GitHubRepo, GitHubUserData, PortfolioScoreResult
from app.services.scoring import (
    calculate_portfolio_score,
    PortfolioScorer,
    WEIGHT_TECHNICAL_DEPTH,
    WEIGHT_PROJECT_QUALITY,
    WEIGHT_DOCUMENTATION,
    WEIGHT_ACTIVITY,
    WEIGHT_RECRUITER_READINESS,
)

# Reference anchor time for deterministic calculations
REFERENCE_DATE = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)


def make_profile(
    login: str = "testuser",
    bio: str = "Full-stack developer building open source tools.",
    blog: str = "https://portfolio.dev",
    has_profile_readme: bool = True
) -> GitHubUserProfile:
    return GitHubUserProfile(
        login=login,
        id=1001,
        name="Test Builder",
        avatar_url="https://github.com/images/avatar.png",
        html_url=f"https://github.com/{login}",
        bio=bio,
        blog=blog,
        public_repos=10,
        created_at=datetime(2022, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        has_profile_readme=has_profile_readme,
    )


def make_repo(
    name: str,
    is_fork: bool = False,
    language: str = "Python",
    size_kb: int = 150,
    stars: int = 5,
    pushed_days_ago: int = 10,
    has_readme: bool = True,
    readme_chars: int = 1000,
    snippet: str = "## Installation\npip install .\n## Usage\npython main.py\n![Architecture](arch.png)",
    has_license: bool = True,
    homepage: str = "https://demo.app",
    topics: List[str] = None
) -> GitHubRepo:
    pushed_at = REFERENCE_DATE - timedelta(days=pushed_days_ago)
    return GitHubRepo(
        name=name,
        full_name=f"testuser/{name}",
        html_url=f"https://github.com/testuser/{name}",
        description=f"A solid project named {name}",
        homepage=homepage,
        is_fork=is_fork,
        created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
        updated_at=pushed_at,
        pushed_at=pushed_at,
        size_kb=size_kb,
        stargazers_count=stars,
        language=language,
        topics=topics if topics is not None else ["fastapi", "python"],
        license_name="MIT License" if has_license else None,
        has_readme=has_readme,
        readme_char_count=readme_chars if has_readme else 0,
        readme_snippet=snippet if has_readme else None
    )


# =============================================================================
# 1. Edge Case: Zero-Repository Profile
# =============================================================================
def test_zero_repository_profile():
    profile = make_profile(login="emptyuser", bio=None, blog=None, has_profile_readme=False)
    user_data = GitHubUserData(profile=profile, repositories=[], fetched_at=REFERENCE_DATE)

    result = calculate_portfolio_score(user_data, as_of_date=REFERENCE_DATE)

    assert result.overall_score == 0.0
    for name, cat in result.category_scores.items():
        assert cat.score == 0.0
        assert cat.weighted_score == 0.0
    
    # Evidence is strictly factual
    assert any("0 public repositories found" in item.evidence for item in result.all_evidence)


# =============================================================================
# 2. Edge Case: Fork-Heavy Profile
# =============================================================================
def test_fork_heavy_profile():
    profile = make_profile(login="forker")
    forks = [
        make_repo(name=f"forked-project-{i}", is_fork=True, language="TypeScript", size_kb=2000)
        for i in range(6)
    ]
    user_data = GitHubUserData(profile=profile, repositories=forks, fetched_at=REFERENCE_DATE)

    result = calculate_portfolio_score(user_data, as_of_date=REFERENCE_DATE)

    # Technical depth & project quality should penalize lack of original code
    tech_cat = result.category_scores["technical_depth"]
    qual_cat = result.category_scores["project_quality"]

    assert tech_cat.score < 50.0
    # Original ratio should be 0%
    orig_ratio_item = next(e for e in qual_cat.evidence if e.metric == "original_ratio_percent")
    assert orig_ratio_item.value == 0.0
    assert "0% of analyzed repositories are original projects" in orig_ratio_item.evidence


# =============================================================================
# 3. Documentation-Heavy Profile
# =============================================================================
def test_documentation_heavy_profile():
    profile = make_profile(
        bio="Full stack engineer passionate about developer experience.",
        blog="https://dev.blog",
        has_profile_readme=True
    )
    rich_repos = [
        make_repo(
            name=f"core-app-{i}",
            has_readme=True,
            readme_chars=1800,
            snippet="## Installation\nnpm install\n## Quickstart & Usage\nnpm run dev\n![Screenshot](demo.gif)",
            has_license=True,
            homepage="https://live-app.vercel.app"
        )
        for i in range(4)
    ]
    user_data = GitHubUserData(profile=profile, repositories=rich_repos, fetched_at=REFERENCE_DATE)

    result = calculate_portfolio_score(user_data, as_of_date=REFERENCE_DATE)
    doc_cat = result.category_scores["documentation_and_presentation"]

    assert doc_cat.score >= 80.0
    # Check verifiable evidence items
    setup_ev = next(e for e in doc_cat.evidence if e.metric == "readme_setup_instructions_detected")
    usage_ev = next(e for e in doc_cat.evidence if e.metric == "readme_usage_instructions_detected")
    visual_ev = next(e for e in doc_cat.evidence if e.metric == "readme_visuals_detected")
    assert setup_ev.value is True
    assert usage_ev.value is True
    assert visual_ev.value is True


# =============================================================================
# 4. Activity & Consistency: Recently Active Profile
# =============================================================================
def test_recently_active_profile():
    profile = make_profile()
    active_repos = [
        make_repo(name="active-1", pushed_days_ago=3),
        make_repo(name="active-2", pushed_days_ago=12),
        make_repo(name="active-3", pushed_days_ago=25),
        make_repo(name="active-4", pushed_days_ago=75),
    ]
    user_data = GitHubUserData(profile=profile, repositories=active_repos, fetched_at=REFERENCE_DATE)

    result = calculate_portfolio_score(user_data, as_of_date=REFERENCE_DATE)
    act_cat = result.category_scores["activity_and_consistency"]

    assert act_cat.score >= 80.0
    p30_ev = next(e for e in act_cat.evidence if e.metric == "repositories_pushed_last_30_days")
    p90_ev = next(e for e in act_cat.evidence if e.metric == "repositories_pushed_last_90_days")
    dist_ev = next(e for e in act_cat.evidence if e.metric == "activity_distributed_across_repositories")

    assert p30_ev.value == 3
    assert p90_ev.value == 4
    assert dist_ev.value is True
    assert "Recent activity is distributed across 4 separate repositories" in dist_ev.evidence


# =============================================================================
# 5. Activity & Consistency: Inactive Profile
# =============================================================================
def test_inactive_profile():
    profile = make_profile()
    stale_repos = [
        make_repo(name="stale-1", pushed_days_ago=350),
        make_repo(name="stale-2", pushed_days_ago=420),
    ]
    user_data = GitHubUserData(profile=profile, repositories=stale_repos, fetched_at=REFERENCE_DATE)

    result = calculate_portfolio_score(user_data, as_of_date=REFERENCE_DATE)
    act_cat = result.category_scores["activity_and_consistency"]

    assert act_cat.score == 0.0
    recency_ev = next(e for e in act_cat.evidence if e.metric == "days_since_latest_push")
    assert recency_ev.value == 350
    assert "Most recent repository activity was 350 days ago." in recency_ev.evidence


# =============================================================================
# 6. Weighted Overall Score & Category Bounds
# =============================================================================
def test_weighted_overall_score_calculation():
    profile = make_profile()
    repos = [
        make_repo(name="project-a", language="Python", pushed_days_ago=5, size_kb=300),
        make_repo(name="project-b", language="TypeScript", pushed_days_ago=20, size_kb=150),
        make_repo(name="project-c", language="Go", pushed_days_ago=60, size_kb=80),
        make_repo(name="project-d", language="Rust", pushed_days_ago=120, size_kb=500),
    ]
    user_data = GitHubUserData(profile=profile, repositories=repos, fetched_at=REFERENCE_DATE)

    result = calculate_portfolio_score(user_data, as_of_date=REFERENCE_DATE)

    # Verify all categories stay within [0, 100]
    for cat_name, cat in result.category_scores.items():
        assert 0.0 <= cat.score <= 100.0
        assert cat.weighted_score == round(cat.score * cat.weight, 2)

    # Check exact weighted sum formula
    expected_sum = (
        result.category_scores["technical_depth"].score * WEIGHT_TECHNICAL_DEPTH +
        result.category_scores["project_quality"].score * WEIGHT_PROJECT_QUALITY +
        result.category_scores["documentation_and_presentation"].score * WEIGHT_DOCUMENTATION +
        result.category_scores["activity_and_consistency"].score * WEIGHT_ACTIVITY +
        result.category_scores["recruiter_readiness"].score * WEIGHT_RECRUITER_READINESS
    )
    assert result.overall_score == round(expected_sum, 1)
    assert 0.0 <= result.overall_score <= 100.0


# =============================================================================
# 7. Evidence Items Structure (Anti-Hallucination)
# =============================================================================
def test_evidence_structure_and_anti_hallucination():
    profile = make_profile()
    repos = [make_repo(name="test-repo", language="Python")]
    user_data = GitHubUserData(profile=profile, repositories=repos, fetched_at=REFERENCE_DATE)

    result = calculate_portfolio_score(user_data, as_of_date=REFERENCE_DATE)

    assert len(result.all_evidence) > 0
    for item in result.all_evidence:
        assert isinstance(item.metric, str) and len(item.metric) > 0
        assert item.value is not None or "push" in item.metric or "bio" in item.metric
        assert isinstance(item.evidence, str) and len(item.evidence) > 0
        # No subjective or outcome hallucinations
        assert "3x" not in item.evidence
        assert "guaranteed" not in item.evidence.lower()
        assert "strong candidate" not in item.evidence.lower()


# =============================================================================
# 8. Determinism Check
# =============================================================================
def test_scoring_determinism():
    profile = make_profile()
    repos = [
        make_repo(name="repo-1", language="Python", pushed_days_ago=10),
        make_repo(name="repo-2", language="JavaScript", pushed_days_ago=40),
    ]
    user_data = GitHubUserData(profile=profile, repositories=repos, fetched_at=REFERENCE_DATE)

    run_1 = calculate_portfolio_score(user_data, as_of_date=REFERENCE_DATE)
    run_2 = calculate_portfolio_score(user_data, as_of_date=REFERENCE_DATE)

    assert run_1.overall_score == run_2.overall_score
    for key in run_1.category_scores:
        assert run_1.category_scores[key].score == run_2.category_scores[key].score
        assert run_1.category_scores[key].weighted_score == run_2.category_scores[key].weighted_score
        assert len(run_1.category_scores[key].evidence) == len(run_2.category_scores[key].evidence)
