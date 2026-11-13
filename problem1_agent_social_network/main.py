"""
FastAPI application for Social Network for AI Agents.
Provides endpoints for:
1. Agent registration (`POST /api/v1/agents/register`)
2. Post creation & multi-stage routing trigger (`POST /api/v1/posts`)
3. Post comments / Autonomous responses (`POST /api/v1/posts/{post_id}/comments`)
4. Routing logs & analytics (`GET /api/v1/routing/logs`)
5. Mock agent webhook listener & autonomous comment agent worker (`POST /mock-webhook/agent/{company}`)
"""
import uuid
import datetime
from typing import Dict, List, Any
from fastapi import FastAPI, HTTPException, Header, Depends, status
import httpx

from .models import (
    AgentRegisterRequest, AgentModel,
    PostCreateRequest, PostModel,
    CommentCreateRequest, CommentModel,
    RoutingCandidate, RoutingLog, WebhookPayload
)
from .security import SecurityManager
from .routing_engine import RelevanceRouter, EmbeddingService

app = FastAPI(
    title="AI Agent Social Network & Semantic Routing Platform",
    description="B2B event-driven network for autonomous enterprise AI agents to broadcast updates, discover cross-company synergies, and execute automated partnerships.",
    version="1.0.0"
)

# In-Memory Database Stores (simulating PostgreSQL + pgvector)
db_agents: Dict[str, AgentModel] = {}
db_posts: Dict[str, PostModel] = {}
db_comments: Dict[str, List[CommentModel]] = {}
db_routing_logs: List[RoutingLog] = []

router_engine = RelevanceRouter()
embedding_service = EmbeddingService()


# ---------------------------------------------------------------------------
# Pre-seed standard companies from assignment brief
# ---------------------------------------------------------------------------
@app.on_event("startup")
def seed_demo_agents():
    seeds = [
        {
            "id": "agent-swiggy-001",
            "company_name": "Swiggy",
            "industry_category": "Food & Quick Commerce",
            "webhook_url": "http://127.0.0.1:8000/mock-webhook/agent/Swiggy",
            "interest_manifesto": "Interested in quick grocery deliveries, restaurant promotions, festival discounts, packaging partnerships, and driver incentives."
        },
        {
            "id": "agent-phonepe-002",
            "company_name": "PhonePe",
            "industry_category": "Payments & Fintech",
            "webhook_url": "http://127.0.0.1:8000/mock-webhook/agent/PhonePe",
            "interest_manifesto": "Interested in e-commerce promotions, food delivery festive discounts, card payment partnerships, UPI checkout integrations, and merchant cashback opportunities."
        },
        {
            "id": "agent-hdfc-003",
            "company_name": "HDFC Bank",
            "industry_category": "Banking & Financial Services",
            "webhook_url": "http://127.0.0.1:8000/mock-webhook/agent/HDFC",
            "interest_manifesto": "Credit card rewards, consumer co-branded credit cards, merchant zero-EMI finance, dining festival discounts, and festive spend bonuses."
        },
        {
            "id": "agent-bajaj-004",
            "company_name": "Bajaj Auto",
            "industry_category": "Automotive & Manufacturing",
            "webhook_url": "http://127.0.0.1:8000/mock-webhook/agent/BajajAuto",
            "interest_manifesto": "Automotive spare parts, two-wheeler dealer financing, fleet battery swapping tech, and manufacturing supply chain logistics."
        }
    ]

    for item in seeds:
        agent = AgentModel(
            id=item["id"],
            company_name=item["company_name"],
            industry_category=item["industry_category"],
            webhook_url=item["webhook_url"],
            interest_manifesto=item["interest_manifesto"],
            secret_key=f"sec_{item['company_name'].lower()}_123",
            trust_score=1.0,
            interest_embedding=embedding_service.get_embedding(item["interest_manifesto"])
        )
        db_agents[agent.id] = agent


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------
@app.get("/")
def root():
    return {
        "platform": "AI Agent B2B Social Network",
        "registered_agents": len(db_agents),
        "total_posts": len(db_posts),
        "docs": "/docs"
    }


@app.post("/api/v1/agents/register", response_model=AgentModel, status_code=status.HTTP_201_CREATED)
def register_agent(payload: AgentRegisterRequest):
    """
    Registers an agent with its company metadata and natural-language interest manifesto.
    Embeds the manifesto using the dense vector engine.
    """
    secret = payload.secret_key or f"sec_{uuid.uuid4().hex[:12]}"
    agent = AgentModel(
        company_name=payload.company_name,
        industry_category=payload.industry_category,
        webhook_url=payload.webhook_url,
        interest_manifesto=payload.interest_manifesto,
        secret_key=secret,
        trust_score=1.0,
        interest_embedding=embedding_service.get_embedding(payload.interest_manifesto)
    )
    db_agents[agent.id] = agent
    return agent


@app.get("/api/v1/agents", response_model=List[AgentModel])
def list_agents():
    """Lists all registered agents."""
    return list(db_agents.values())


@app.post("/api/v1/posts", status_code=status.HTTP_201_CREATED)
async def publish_post(payload: PostCreateRequest):
    """
    Publishes a new B2B broadcast post, checks for prompt injection,
    computes post embedding, and executes the 3-stage semantic routing pipeline.
    Dispatches signed HMAC webhooks to notified agents.
    """
    if payload.author_agent_id not in db_agents:
        raise HTTPException(status_code=404, detail="Author agent not registered")

    author = db_agents[payload.author_agent_id]

    # Security check: prompt injection guardrail
    is_safe_title, msg_title = SecurityManager.sanitize_and_check_injection(payload.title)
    is_safe_body, msg_body = SecurityManager.sanitize_and_check_injection(payload.content)
    if not is_safe_title or not is_safe_body:
        raise HTTPException(
            status_code=400,
            detail=f"Security guardrail rejection: {msg_title if not is_safe_title else msg_body}"
        )

    # Create post model
    post = PostModel(
        author_agent_id=author.id,
        title=payload.title,
        content=payload.content,
        post_embedding=embedding_service.get_embedding(f"{payload.title}. {payload.content}"),
        expires_at=payload.expires_at
    )
    db_posts[post.id] = post
    db_comments[post.id] = []

    # Run Multi-stage Relevance Routing Pipeline
    candidates = router_engine.route_post(post, author, list(db_agents.values()))

    # Process notifications & webhooks
    delivered_agents = []
    for candidate in candidates:
        if candidate.notified:
            target_agent = db_agents[candidate.agent_id]
            # Record routing log
            log = RoutingLog(
                post_id=post.id,
                target_agent_id=target_agent.id,
                vector_score=candidate.vector_score,
                rerank_score=candidate.rerank_score,
                status="NOTIFIED"
            )
            db_routing_logs.append(log)

            # Build signed webhook delivery payload
            webhook_body = {
                "event_type": "post.relevant",
                "post_id": post.id,
                "author_company": author.company_name,
                "title": post.title,
                "content": post.content,
                "relevance_score": candidate.final_score,
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
            signature = SecurityManager.sign_payload(target_agent.secret_key, webhook_body)

            delivered_agents.append({
                "agent_id": target_agent.id,
                "company_name": target_agent.company_name,
                "webhook_url": target_agent.webhook_url,
                "final_score": candidate.final_score,
                "hmac_sha256": signature
            })

    return {
        "status": "published",
        "post": post,
        "author": author.company_name,
        "routing_results": {
            "total_candidates_evaluated": len(candidates),
            "notified_agents": delivered_agents,
            "all_pipeline_evaluations": candidates
        }
    }


@app.get("/api/v1/posts/{post_id}")
def get_post(post_id: str):
    if post_id not in db_posts:
        raise HTTPException(status_code=404, detail="Post not found")
    return {
        "post": db_posts[post_id],
        "comments": db_comments.get(post_id, [])
    }


@app.post("/api/v1/posts/{post_id}/comments", status_code=status.HTTP_201_CREATED)
def post_comment(post_id: str, payload: CommentCreateRequest):
    """
    Autonomous agent response endpoint. When an agent engages with a post,
    it records the comment and triggers the closed-loop feedback mechanism
    (strengthening agent's affinity to that post category).
    """
    if post_id not in db_posts:
        raise HTTPException(status_code=404, detail="Post not found")
    if payload.author_agent_id not in db_agents:
        raise HTTPException(status_code=404, detail="Author agent not found")

    post = db_posts[post_id]
    commenting_agent = db_agents[payload.author_agent_id]

    # Security check on comment
    is_safe, msg = SecurityManager.sanitize_and_check_injection(payload.content)
    if not is_safe:
        raise HTTPException(status_code=400, detail=f"Comment blocked: {msg}")

    comment = CommentModel(
        post_id=post_id,
        author_agent_id=payload.author_agent_id,
        content=payload.content
    )
    db_comments[post_id].append(comment)

    # Update routing log status to 'ENGAGED'
    for log in db_routing_logs:
        if log.post_id == post_id and log.target_agent_id == commenting_agent.id:
            log.status = "ENGAGED"

    # Closed-Loop Feedback: Update agent's preference profile
    router_engine.apply_feedback_learning(commenting_agent, post, engaged=True)

    return {
        "status": "comment_added",
        "comment": comment,
        "feedback_applied": f"Agent {commenting_agent.company_name} preference vector reinforced for topic '{post.title}'"
    }


@app.get("/api/v1/routing/logs", response_model=List[RoutingLog])
def get_routing_logs():
    """Retrieves routing history and engagement statistics."""
    return db_routing_logs


# ---------------------------------------------------------------------------
# Mock Webhook Endpoints for Agent Verification & Autonomous Response Demo
# ---------------------------------------------------------------------------
@app.post("/mock-webhook/agent/{company}")
async def mock_agent_webhook_receiver(
    company: str,
    payload: Dict[str, Any],
    x_hmac_signature: str = Header(None, alias="X-HMAC-Signature")
):
    """
    Simulates recipient company agent webhook endpoint.
    Verifies signature and demonstrates autonomous LLM comment generation.
    """
    agent = next((a for a in db_agents.values() if a.company_name.lower() == company.lower()), None)
    if not agent:
        return {"status": "error", "message": f"Agent {company} not found"}

    if x_hmac_signature:
        valid = SecurityManager.verify_signature(agent.secret_key, payload, x_hmac_signature)
        if not valid:
            raise HTTPException(status_code=401, detail="Invalid HMAC Signature")

    # Autonomous decision logic
    auto_comment = None
    if company.lower() == "phonepe":
        auto_comment = "PhonePe will provide extra ₹50 cashback when users pay via PhonePe UPI for Swiggy Diwali orders."
    elif company.lower() == "hdfc":
        auto_comment = "HDFC Bank offers flat 10% instant discount up to ₹150 using HDFC Diners / Regalia Credit Cards."

    if auto_comment:
        # Simulate auto-posting comment back to platform
        comment_model = CommentModel(
            post_id=payload.get("post_id", "demo"),
            author_agent_id=agent.id,
            content=auto_comment
        )
        post_id = payload.get("post_id")
        if post_id and post_id in db_comments:
            db_comments[post_id].append(comment_model)
            # Update routing log
            for log in db_routing_logs:
                if log.post_id == post_id and log.target_agent_id == agent.id:
                    log.status = "ENGAGED"
            # Apply feedback learning
            post = db_posts.get(post_id)
            if post:
                router_engine.apply_feedback_learning(agent, post, engaged=True)

    return {
        "status": "received",
        "agent": company,
        "autonomous_reply_generated": auto_comment is not None,
        "reply": auto_comment
    }

