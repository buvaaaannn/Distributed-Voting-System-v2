"""
FastAPI application for vote ingestion API.

Author: David Marleau
Project: Distributed Voting System - Demo Version
Description: Production-grade distributed voting system for 8M+ concurrent voters
"""
import hashlib
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
from pydantic import ValidationError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from config import settings
from models import (
    VoteRequest,
    VoteResponse,
    ResultsResponse,
    HealthResponse,
    ErrorResponse,
    ElectionVoteRequest,
    CandidateInfo,
    ElectionResultsResponse
)
from publisher import publisher
from database import database

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Prometheus metrics
vote_counter = Counter(
    "votes_submitted_total",
    "Total number of votes submitted",
    ["law_id", "vote_choice"]
)
vote_errors = Counter(
    "vote_errors_total",
    "Total number of vote submission errors",
    ["error_type"]
)
request_duration = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint", "status"]
)

# Redis client for rate limiting
redis_client: redis.Redis = None

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    logger.info(f"Starting {settings.SERVICE_NAME} service...")

    try:
        # Initialize Redis
        global redis_client
        redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        await redis_client.ping()
        logger.info("Redis connection established")

        # Initialize RabbitMQ publisher
        await publisher.initialize()

        # Initialize database
        await database.initialize()

        logger.info(f"{settings.SERVICE_NAME} started successfully")

    except Exception as e:
        logger.error(f"Failed to start {settings.SERVICE_NAME}: {e}")
        raise

    yield

    # Shutdown
    logger.info(f"Shutting down {settings.SERVICE_NAME} service...")

    try:
        if redis_client:
            await redis_client.close()
        await publisher.close()
        await database.close()
        logger.info(f"{settings.SERVICE_NAME} shut down successfully")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# Create FastAPI app
app = FastAPI(
    title="Vote Ingestion API",
    description="API for submitting and retrieving votes",
    version=settings.API_VERSION,
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    """Middleware to track request duration."""
    with request_duration.labels(
        method=request.method,
        endpoint=request.url.path,
        status="processing"
    ).time():
        response = await call_next(request)

    request_duration.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).observe(0)  # Time already recorded above

    return response


@app.post(
    f"/api/{settings.API_VERSION}/vote",
    response_model=VoteResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid vote format"},
        429: {"description": "Rate limit exceeded"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
@limiter.limit(settings.RATE_LIMIT)
async def submit_vote(request: Request, vote: VoteRequest) -> VoteResponse:
    """
    Submit a vote for a law.

    - **nas**: National Administrative Security number (9 digits)
    - **code**: Voter code (6 characters)
    - **law_id**: Law identifier
    - **vote**: Vote choice (oui or non)

    Returns a request_id (vote hash) and acceptance status.
    """
    try:
        # Generate hash: sha256(f"{nas_clean}|{code.upper()}|{law_id}")
        hash_input = f"{vote.nas}|{vote.code}|{vote.law_id}"
        vote_hash = hashlib.sha256(hash_input.encode()).hexdigest()

        # Prepare vote data for publishing
        vote_data = {
            "hash": vote_hash,
            "nas": vote.nas,
            "code": vote.code,
            "law_id": vote.law_id,
            "vote": vote.vote,
            "submitted_at": datetime.utcnow().isoformat()
        }

        # Publish to RabbitMQ
        success = await publisher.publish_vote(vote_data)

        if not success:
            vote_errors.labels(error_type="publish_failed").inc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to publish vote to message queue"
            )

        # Update metrics
        vote_counter.labels(law_id=vote.law_id, vote_choice=vote.vote).inc()

        logger.info(
            f"Vote submitted: hash={vote_hash}, law_id={vote.law_id}, vote={vote.vote}"
        )

        return VoteResponse(
            request_id=vote_hash,
            status="accepted",
            message="Vote submitted successfully"
        )

    except ValidationError as e:
        vote_errors.labels(error_type="validation_error").inc()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        vote_errors.labels(error_type="internal_error").inc()
        logger.error(f"Error submitting vote: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@app.get(
    f"/api/{settings.API_VERSION}/results/{{law_id}}",
    response_model=ResultsResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Law not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def get_results(law_id: str) -> ResultsResponse:
    """
    Get vote results for a specific law.

    - **law_id**: Law identifier

    Returns vote counts (oui, non) and last update timestamp.
    """
    try:
        results = await database.get_results(law_id)

        if results is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Law {law_id} not found"
            )

        return ResultsResponse(**results)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting results for law {law_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@app.get(
    f"/api/{settings.API_VERSION}/results",
    response_model=list[ResultsResponse],
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def get_all_results() -> list[ResultsResponse]:
    """
    Get vote results for all laws.

    Returns a list of vote counts for all laws.
    """
    try:
        results = await database.get_all_results()
        return [ResultsResponse(**result) for result in results]

    except Exception as e:
        logger.error(f"Error getting all results: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@app.get(
    f"/api/{settings.API_VERSION}/health",
    response_model=HealthResponse,
    responses={
        503: {"model": HealthResponse, "description": "Service unhealthy"}
    }
)
async def health_check() -> HealthResponse:
    """
    Check health of the service and its dependencies.

    Verifies connections to:
    - RabbitMQ
    - PostgreSQL
    - Redis

    Returns overall health status and individual service statuses.
    """
    services = {}

    # Check RabbitMQ
    try:
        rabbitmq_healthy = await publisher.check_health()
        services["rabbitmq"] = "connected" if rabbitmq_healthy else "disconnected"
    except Exception as e:
        logger.error(f"RabbitMQ health check error: {e}")
        services["rabbitmq"] = "error"

    # Check PostgreSQL
    try:
        postgres_healthy = await database.check_health()
        services["postgresql"] = "connected" if postgres_healthy else "disconnected"
    except Exception as e:
        logger.error(f"PostgreSQL health check error: {e}")
        services["postgresql"] = "error"

    # Check Redis
    try:
        await redis_client.ping()
        services["redis"] = "connected"
    except Exception as e:
        logger.error(f"Redis health check error: {e}")
        services["redis"] = "disconnected"

    # Determine overall status
    all_healthy = all(
        status == "connected" for status in services.values()
    )

    overall_status = "healthy" if all_healthy else "unhealthy"
    status_code = status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    response = HealthResponse(
        status=overall_status,
        services=services,
        timestamp=datetime.utcnow()
    )

    return JSONResponse(
        status_code=status_code,
        content=response.model_dump(mode="json")
    )


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


# ═══════════════════════════════════════════════════════════════════
# ELECTION VOTING ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@app.get(
    f"/api/{settings.API_VERSION}/elections",
    response_model=list[dict]
)
async def get_elections():
    """Get all active elections."""
    try:
        elections = await database.get_elections()
        return elections
    except Exception as e:
        logger.error(f"Error getting elections: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@app.get(
    f"/api/{settings.API_VERSION}/regions",
    response_model=list[dict]
)
async def get_regions():
    """Get all regions."""
    try:
        regions = await database.get_regions()
        return regions
    except Exception as e:
        logger.error(f"Error getting regions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@app.get(
    f"/api/{settings.API_VERSION}/elections/{{election_id}}/regions/{{region_id}}/candidates",
    response_model=list[dict]
)
async def get_candidates(election_id: int, region_id: int):
    """Get candidates for a specific election and region."""
    try:
        candidates = await database.get_candidates(election_id, region_id)
        return candidates
    except Exception as e:
        logger.error(f"Error getting candidates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@app.post(
    f"/api/{settings.API_VERSION}/elections/vote",
    response_model=VoteResponse,
    status_code=status.HTTP_202_ACCEPTED
)
@limiter.limit(settings.RATE_LIMIT)
async def submit_election_vote(request: Request, vote: ElectionVoteRequest) -> VoteResponse:
    """
    Submit a vote for a candidate in an election.

    - **nas**: National Administrative Security number (9 digits)
    - **code**: Voter code (6 characters)
    - **election_id**: Election ID
    - **region_id**: Region/Circonscription ID
    - **candidate_id**: Candidate ID

    Returns a request_id (vote hash) and acceptance status.
    """
    try:
        # Check election timing (start_datetime and end_datetime)
        election_timing = await database.get_election_timing(vote.election_id)
        if election_timing:
            start_dt, end_dt = election_timing
            now = datetime.utcnow()

            if start_dt and now < start_dt:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Voting has not started yet. Opens at {start_dt.isoformat()}"
                )

            if end_dt and now > end_dt:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Voting has ended. Closed at {end_dt.isoformat()}"
                )

        # Generate hash from NAS+code only (one vote per person across all elections)
        vote_hash = hashlib.sha256(f"{vote.nas}{vote.code}".encode()).hexdigest()

        # Check if hash is valid
        is_valid = await redis_client.sismember('valid_hashes', vote_hash)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid voting credentials"
            )

        # Check if already voted
        has_voted = await redis_client.sismember('voted_hashes', vote_hash)
        if has_voted:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You have already voted"
            )

        # Mark as voted in Redis
        await redis_client.sadd('voted_hashes', vote_hash)

        # Submit vote to database with ranked choices if provided
        metadata = {
            'submitted_at': datetime.utcnow().isoformat(),
            'source': 'web_ui',
            'voting_method': vote.voting_method
        }

        # Add ranked choices to metadata if using ranked-choice voting
        if vote.voting_method == 'ranked_choice' and vote.ranked_choices:
            metadata['ranked_choices'] = vote.ranked_choices
            logger.info(f"Ranked choice vote: {vote.ranked_choices}")

        success = await database.submit_election_vote(
            vote_hash, vote.election_id, vote.region_id,
            vote.candidate_id, metadata
        )

        if not success:
            # Rollback Redis on database failure
            await redis_client.srem('voted_hashes', vote_hash)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to record vote"
            )

        logger.info(
            f"Election vote submitted: hash={vote_hash}, "
            f"election={vote.election_id}, region={vote.region_id}, "
            f"candidate={vote.candidate_id}"
        )

        return VoteResponse(
            request_id=vote_hash,
            status="accepted",
            message="Vote recorded successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting election vote: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@app.get(
    f"/api/{settings.API_VERSION}/elections/{{election_id}}/regions/{{region_id}}/results"
)
async def get_election_results(election_id: int, region_id: int):
    """Get election results for a specific region."""
    try:
        results = await database.get_election_results(election_id, region_id)
        if results is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Election or region not found"
            )
        return results
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting election results: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "service": settings.SERVICE_NAME,
        "version": settings.API_VERSION,
        "status": "running",
        "endpoints": {
            "submit_vote": f"/api/{settings.API_VERSION}/vote",
            "get_results": f"/api/{settings.API_VERSION}/results/{{law_id}}",
            "get_all_results": f"/api/{settings.API_VERSION}/results",
            "health": f"/api/{settings.API_VERSION}/health",
            "metrics": "/metrics"
        }
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )
