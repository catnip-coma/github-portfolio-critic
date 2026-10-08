from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from app.config import Settings, get_settings
from app.models.schemas import GitHubUserData, PortfolioScoreResult, ErrorResponse
from app.services.github_client import (
    GitHubClient,
    UserNotFoundError,
    RateLimitExceededError,
    GitHubClientError
)

router = APIRouter()

# Client singleton per runtime session
_client_instance: GitHubClient = None


def get_github_client(settings: Settings = Depends(get_settings)) -> GitHubClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = GitHubClient(
            token=settings.GITHUB_TOKEN,
            cache_ttl_seconds=settings.CACHE_TTL_SECONDS
        )
    return _client_instance


@router.get("/health", summary="Health check")
async def health_check():
    """Verify application health and operational status."""
    return {
        "status": "ok",
        "app": "GitGauge",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "0.1.0"
    }


@router.get(
    "/raw/{username}",
    response_model=GitHubUserData,
    summary="Retrieve raw parsed GitHub user profile and repositories",
    responses={
        404: {"model": ErrorResponse, "description": "GitHub user not found"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        500: {"model": ErrorResponse, "description": "External API failure"},
    }
)
async def get_raw_github_data(
    username: str,
    client: GitHubClient = Depends(get_github_client)
):
    """Retrieve public profile, repositories, and README data for a given GitHub username."""
    clean_username = username.strip()
    if not clean_username:
        raise HTTPException(status_code=400, detail="Username cannot be empty.")

    try:
        data = await client.get_full_user_data(clean_username)
        return data
    except UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except RateLimitExceededError as exc:
        raise HTTPException(status_code=429, detail=exc.message)
    except GitHubClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected error retrieving GitHub data: {str(exc)}")


@router.get(
    "/score/{username}",
    response_model=PortfolioScoreResult,
    summary="Calculate deterministic portfolio scores and factual evidence",
    responses={
        404: {"model": ErrorResponse, "description": "GitHub user not found"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        500: {"model": ErrorResponse, "description": "Calculation or data retrieval failure"},
    }
)
async def get_portfolio_score(
    username: str,
    client: GitHubClient = Depends(get_github_client)
):
    """Retrieve user portfolio data and compute deterministic 5-dimension scores and factual evidence."""
    clean_username = username.strip()
    if not clean_username:
        raise HTTPException(status_code=400, detail="Username cannot be empty.")

    try:
        data = await client.get_full_user_data(clean_username)
        from app.services.scoring import calculate_portfolio_score
        score_result = calculate_portfolio_score(data)
        return score_result
    except UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except RateLimitExceededError as exc:
        raise HTTPException(status_code=429, detail=exc.message)
    except GitHubClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Scoring error: {str(exc)}")

