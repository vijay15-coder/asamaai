"""
Data models and schemas for Problem 1: Social Network for AI Agents.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, HttpUrl


class AgentRegisterRequest(BaseModel):
    company_name: str = Field(..., description="Name of company/entity owning the agent")
    industry_category: str = Field(..., description="Primary industry sector")
    webhook_url: str = Field(..., description="HTTP endpoint where platform pushes notifications")
    interest_manifesto: str = Field(..., description="Detailed description of topics, partnerships, and offers the agent cares about")
    secret_key: Optional[str] = Field(None, description="Shared secret for HMAC verification. Generated automatically if omitted.")


class AgentModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    company_name: str
    industry_category: str
    webhook_url: str
    interest_manifesto: str
    secret_key: str
    trust_score: float = 1.0
    interest_embedding: Optional[List[float]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    active: bool = True
    blocked_industries: List[str] = Field(default_factory=list)


class PostCreateRequest(BaseModel):
    author_agent_id: str
    title: str
    content: str
    expires_at: Optional[datetime] = None


class PostModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    author_agent_id: str
    title: str
    content: str
    post_embedding: Optional[List[float]] = None
    expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CommentCreateRequest(BaseModel):
    author_agent_id: str
    content: str


class CommentModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    post_id: str
    author_agent_id: str
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RoutingCandidate(BaseModel):
    agent_id: str
    company_name: str
    sql_passed: bool = True
    vector_score: float
    rerank_score: float
    final_score: float
    notified: bool
    reason: str


class RoutingLog(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    post_id: str
    target_agent_id: str
    vector_score: float
    rerank_score: float
    status: str = "NOTIFIED"  # NOTIFIED, ENGAGED, IGNORED, FAILED
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WebhookPayload(BaseModel):
    event_type: str = "post.relevant"
    post_id: str
    author_company: str
    title: str
    content: str
    relevance_score: float
    timestamp: str

