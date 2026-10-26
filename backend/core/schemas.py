from datetime import datetime
from typing import Literal
from pydantic import BaseModel, EmailStr, Field

class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Literal["CANDIDATE", "RECRUITER"]
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    name: str
class JobInput(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    description: str = Field(min_length=10)
    required_skills: list[str] = []
    preferred_skills: list[str] = []
    experience_required: float = Field(default=0, ge=0)
    deadline: datetime
    status: Literal["OPEN", "CLOSED"] = "OPEN"
class JobUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    required_skills: list[str] | None = None
    preferred_skills: list[str] | None = None
    experience_required: float | None = Field(default=None, ge=0)
    deadline: datetime | None = None
    status: Literal["OPEN", "CLOSED"] | None = None
class JobResponse(JobInput):
    id: int
    recruiter_id: int
    created_at: datetime
    applicant_count: int = 0
class ApplicationResponse(BaseModel):
    id: int
    candidate_id: int
    job_id: int
    status: str
    processing_status: str
    match_score: float | None
    matched_skills: list[str] = []
    missing_skills: list[str] = []
    applied_at: datetime
    job_title: str | None = None
    candidate_name: str | None = None
class CandidateDetail(ApplicationResponse):
    candidate_email: str
    match_breakdown: dict = {}
    lock_active: bool = False
class VerdictResponse(BaseModel):
    verdict: str
    strengths: list[str]
    gaps: list[str]
    evidence: list[str]
    cached: bool
