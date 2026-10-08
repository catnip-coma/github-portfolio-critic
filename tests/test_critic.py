import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from app.models.schemas import (
    GitHubUserData,
    PortfolioScoreResult,
    RecruiterCritique,
    PriorityAction
)
from app.services.scoring import calculate_portfolio_score
from app.services.critic import RecruiterCriticService, RECRUITER_SYSTEM_PROMPT
from tests.test_scoring import make_profile, make_repo, REFERENCE_DATE


@pytest.fixture
def sample_user_data():
    profile = make_profile(
        login="candidate_dev",
        bio="Full stack developer working on developer tooling.",
        blog="https://devtool.app",
        has_profile_readme=True
    )
    repos = [
        make_repo(name="app-core", language="Python", size_kb=300, stars=15, pushed_days_ago=5, homepage="https://demo.app"),
        make_repo(name="frontend-ui", language="TypeScript", size_kb=200, stars=6, pushed_days_ago=12),
        make_repo(name="docs-site", language="Markdown", size_kb=40, stars=1, pushed_days_ago=45),
    ]
    return GitHubUserData(profile=profile, repositories=repos, fetched_at=REFERENCE_DATE)


@pytest.mark.asyncio
async def test_deterministic_fallback_synthesis(sample_user_data):
    score_result = calculate_portfolio_score(sample_user_data, as_of_date=REFERENCE_DATE)
    critic = RecruiterCriticService(api_key=None)

    critique = await critic.generate_critique(sample_user_data, score_result)

    assert isinstance(critique, RecruiterCritique)
    assert critique.is_ai_generated is False
    assert critique.ai_model == "algorithmic-fallback"
    assert len(critique.recruiter_in_30_seconds) > 20
    assert len(critique.strengths) >= 2
    assert len(critique.weaknesses) >= 1
    assert len(critique.top_3_fixes) == 3
    assert len(critique.roadmap) == 3

    # Check that fixes have qualitative impact and actions
    for fix in critique.top_3_fixes:
        assert isinstance(fix, PriorityAction)
        assert fix.priority in ["High", "Medium", "Low"]
        assert len(fix.action) > 10
        assert len(fix.qualitative_impact) > 10
        # No unsupported numerical claims
        assert "3x" not in fix.qualitative_impact
        assert "guarantee" not in fix.qualitative_impact.lower()


@pytest.mark.asyncio
async def test_critic_zero_repository_fallback():
    empty_profile = make_profile(login="empty_candidate", bio="", blog="", has_profile_readme=False)
    user_data = GitHubUserData(profile=empty_profile, repositories=[], fetched_at=REFERENCE_DATE)
    score_result = calculate_portfolio_score(user_data, as_of_date=REFERENCE_DATE)

    critic = RecruiterCriticService(api_key=None)
    critique = await critic.generate_critique(user_data, score_result)

    assert "no public repositories" in critique.recruiter_in_30_seconds.lower()
    assert critique.candidate_level_assessment == "Early Stage / Empty Profile"
    assert len(critique.top_3_fixes) <= 3


def test_sanitizer_removes_unsupported_claims():
    critic = RecruiterCriticService(api_key=None)
    raw_critique = RecruiterCritique(
        recruiter_in_30_seconds="This profile will increase recruiter click-through by 3x and guarantees an interview.",
        candidate_level_assessment="Junior",
        strengths=["Recruiters spend 30 seconds admiring the code."],
        weaknesses=["Lack of license guarantees rejection."],
        top_3_fixes=[
            PriorityAction(
                title="Add Demo",
                priority="High",
                issue="No demo",
                action="Deploy app to guarantee a job.",
                qualitative_impact="Increases interview chance by 2x."
            )
        ],
        roadmap=[],
        is_ai_generated=True
    )

    sanitized = critic._sanitize_critique(raw_critique)

    assert "3x" not in sanitized.recruiter_in_30_seconds
    assert "guarantees an interview" not in sanitized.recruiter_in_30_seconds
    assert "2x" not in sanitized.top_3_fixes[0].qualitative_impact
    assert "guarantee a job" not in sanitized.top_3_fixes[0].action


def test_prompt_includes_scores_and_evidence(sample_user_data):
    score_result = calculate_portfolio_score(sample_user_data, as_of_date=REFERENCE_DATE)
    critic = RecruiterCriticService(api_key="fake-key")

    prompt = critic._build_evaluation_prompt(sample_user_data, score_result)

    # Prompt must contain deterministic scores
    assert str(score_result.overall_score) in prompt
    assert "Technical Depth" in prompt
    assert "Project Quality" in prompt
    assert "Documentation & Presentation" in prompt
    assert "Activity & Consistency" in prompt
    assert "Recruiter Readiness" in prompt

    # Prompt must contain candidate info
    assert "candidate_dev" in prompt
    # Prompt must contain factual evidence items
    assert "analyzed repositories are original" in prompt
