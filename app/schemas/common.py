import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserOut(ORMBase):
    id: uuid.UUID
    email: EmailStr
    full_name: str | None
    avatar_url: str | None
    created_at: datetime


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RepositoryOut(ORMBase):
    id: uuid.UUID
    provider: str
    full_name: str
    default_branch: str
    is_active: bool
    created_at: datetime


class RepositoryCreate(BaseModel):
    provider: str
    external_id: str
    full_name: str
    default_branch: str = "main"


class BuildOut(ORMBase):
    id: uuid.UUID
    repository_id: uuid.UUID
    commit_sha: str
    branch: str
    ci_provider: str
    status: str
    created_at: datetime


class QualityScoreOut(ORMBase):
    testing_score: float
    security_score: float
    performance_score: float
    code_quality_score: float
    build_stability_score: float
    final_score: float
    category: str
    recommendation: str


class AgentReportOut(ORMBase):
    id: uuid.UUID
    agent_type: str
    summary: str
    confidence: float | None
    payload: dict
    created_at: datetime
