"""Pydantic models for request/response validation."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, validator
import re


class VoteRequest(BaseModel):
    """Vote submission request model."""

    nas: str = Field(..., description="National Administrative Security number (9 digits)")
    code: str = Field(..., description="Voter code (6 characters)")
    law_id: str = Field(..., description="Law identifier")
    vote: Literal["oui", "non"] = Field(..., description="Vote choice: oui or non")

    @validator("nas")
    def validate_nas(cls, v):
        """Validate NAS is exactly 9 digits."""
        # Remove any spaces or dashes
        nas_clean = re.sub(r'[\s\-]', '', v)
        if not re.match(r'^\d{9}$', nas_clean):
            raise ValueError("NAS must be exactly 9 digits")
        return nas_clean

    @validator("code")
    def validate_code(cls, v):
        """Validate code is exactly 6 characters."""
        if len(v) != 6:
            raise ValueError("Code must be exactly 6 characters")
        return v.upper()

    @validator("law_id")
    def validate_law_id(cls, v):
        """Validate law_id is not empty."""
        if not v or not v.strip():
            raise ValueError("Law ID cannot be empty")
        return v.strip()

    class Config:
        json_schema_extra = {
            "example": {
                "nas": "123456789",
                "code": "ABC123",
                "law_id": "LAW-2024-001",
                "vote": "oui"
            }
        }


class VoteResponse(BaseModel):
    """Vote submission response model."""

    request_id: str = Field(..., description="Unique request identifier (vote hash)")
    status: str = Field(..., description="Status of the submission")
    message: str = Field(default="Vote submitted successfully", description="Response message")

    class Config:
        json_schema_extra = {
            "example": {
                "request_id": "a1b2c3d4e5f6...",
                "status": "accepted",
                "message": "Vote submitted successfully"
            }
        }


class ResultsResponse(BaseModel):
    """Vote results response model."""

    law_id: str = Field(..., description="Law identifier")
    oui_count: int = Field(..., description="Count of 'oui' votes")
    non_count: int = Field(..., description="Count of 'non' votes")
    total_votes: int = Field(..., description="Total number of votes")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "law_id": "LAW-2024-001",
                "oui_count": 1523,
                "non_count": 847,
                "total_votes": 2370,
                "updated_at": "2024-01-15T10:30:00"
            }
        }


class HealthResponse(BaseModel):
    """Health check response model."""

    status: Literal["healthy", "unhealthy"] = Field(..., description="Overall health status")
    services: dict = Field(..., description="Status of individual services")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Health check timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "services": {
                    "rabbitmq": "connected",
                    "postgresql": "connected",
                    "redis": "connected"
                },
                "timestamp": "2024-01-15T10:30:00"
            }
        }


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: dict = Field(default_factory=dict, description="Additional error details")

    class Config:
        json_schema_extra = {
            "example": {
                "error": "ValidationError",
                "message": "Invalid vote format",
                "details": {"nas": ["NAS must be exactly 9 digits"]}
            }
        }


# Election Voting Models

class ElectionVoteRequest(BaseModel):
    """Election vote submission request model."""

    nas: str = Field(..., description="National Administrative Security number (9 digits)")
    code: str = Field(..., description="Voter code (6 characters)")
    election_id: int = Field(..., description="Election ID")
    region_id: int = Field(..., description="Region/Circonscription ID")
    candidate_id: int = Field(..., description="Candidate ID (first choice for ranked voting)")
    voting_method: str = Field(default="single_choice", description="Voting method: single_choice or ranked_choice")
    ranked_choices: list[int] = Field(default=None, description="Ranked candidate IDs (for ranked-choice voting)")

    @validator("nas")
    def validate_nas(cls, v):
        """Validate NAS is exactly 9 digits."""
        nas_clean = re.sub(r'[\s\-]', '', v)
        if not re.match(r'^\d{9}$', nas_clean):
            raise ValueError("NAS must be exactly 9 digits")
        return nas_clean

    @validator("code")
    def validate_code(cls, v):
        """Validate code is exactly 6 characters."""
        if len(v) != 6:
            raise ValueError("Code must be exactly 6 characters")
        return v.upper()

    @validator("voting_method")
    def validate_voting_method(cls, v):
        """Validate voting method."""
        if v not in ["single_choice", "ranked_choice"]:
            raise ValueError("Voting method must be 'single_choice' or 'ranked_choice'")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "nas": "123456789",
                "code": "ABC123",
                "election_id": 1,
                "region_id": 1,
                "candidate_id": 5,
                "voting_method": "ranked_choice",
                "ranked_choices": [5, 3, 1, 2]
            }
        }


class CandidateInfo(BaseModel):
    """Candidate information model."""

    id: int
    first_name: str
    last_name: str
    party_code: str
    party_name: str
    party_color: str
    bio: str = None
    photo_url: str = None


class ElectionResultsResponse(BaseModel):
    """Election results response model."""

    election_id: int
    region_id: int
    region_name: str
    candidates: list[dict]  # List of {candidate_id, name, party, votes, percentage}
    total_votes: int
    updated_at: datetime
