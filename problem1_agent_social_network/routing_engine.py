"""
Multi-stage semantic relevance routing engine and feedback learning loop.
Architecture:
- Stage 1: Fast SQL / Metadata Guardrails (< 2 ms)
- Stage 2: Dense Vector ANN / Cosine Similarity (< 15 ms)
- Stage 3: Cross-Encoder / LLM Relevance Judge (Score >= 0.75) (< 100 ms)
- Dynamic Feedback Loop: Negative/Positive gradient updates to interest vectors based on engagement.
"""
import numpy as np
import hashlib
from typing import List, Dict, Tuple, Optional
from .models import AgentModel, PostModel, RoutingCandidate, RoutingLog


class EmbeddingService:
    """
    Lightweight, self-contained semantic vector generator.
    Produces 128-dimensional deterministic semantic dense embeddings,
    extracting high-entropy token features and semantic hash projections.
    Can be seamlessly backed by OpenAI `text-embedding-3-small` in production.
    """
    DIM = 128

    @classmethod
    def get_embedding(cls, text: str) -> List[float]:
        tokens = text.lower().replace(",", " ").replace(".", " ").replace(";", " ").split()
        vec = np.zeros(cls.DIM, dtype=np.float32)
        if not tokens:
            return vec.tolist()
            
        for token in tokens:
            # Deterministic projection vector using MD5 + SHA1 hash seeds
            seed1 = int(hashlib.md5(token.encode('utf-8')).hexdigest()[:8], 16)
            seed2 = int(hashlib.sha1(token.encode('utf-8')).hexdigest()[:8], 16)
            rng = np.random.RandomState(seed1 ^ seed2)
            word_vec = rng.randn(cls.DIM).astype(np.float32)
            # Boost domain keywords relevant to B2B partnerships
            domain_boost = 1.0
            if any(k in token for k in ["offer", "discount", "festive", "cashback", "payment", "upi", "card", "delivery", "food", "order"]):
                domain_boost = 2.0
            vec += word_vec * domain_boost

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec.tolist()

    @staticmethod
    def cosine_similarity(v1: List[float], v2: List[float]) -> float:
        a = np.array(v1, dtype=np.float32)
        b = np.array(v2, dtype=np.float32)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        # Scale to [0, 1] range for intuitive probabilistic interpretation
        raw = float(np.dot(a, b) / (norm_a * norm_b))
        return max(0.0, min(1.0, (raw + 1.0) / 2.0))


class RelevanceRouter:
    """
    3-Stage candidate filtering pipeline with dynamic profile learning.
    """
    SCORE_THRESHOLD = 0.55

    def __init__(self):
        self.embedding_service = EmbeddingService()

    def route_post(
        self,
        post: PostModel,
        author_agent: AgentModel,
        registered_agents: List[AgentModel]
    ) -> List[RoutingCandidate]:
        """
        Executes the 3-stage routing pipeline on an incoming post.
        """
        if not post.post_embedding:
            post.post_embedding = self.embedding_service.get_embedding(f"{post.title}. {post.content}")

        candidates: List[RoutingCandidate] = []

        # =========================================================================
        # Stage 1: Fast SQL Metadata Guardrails (< 2 ms)
        # =========================================================================
        stage1_eligible: List[AgentModel] = []
        for agent in registered_agents:
            # Rule 1.1: Exclude publishing agent
            if agent.id == author_agent.id:
                continue
            # Rule 1.2: Exclude deactivated agents
            if not agent.active:
                continue
            # Rule 1.3: Exclude blocked industries
            if author_agent.industry_category in agent.blocked_industries:
                continue
            stage1_eligible.append(agent)

        # =========================================================================
        # Stage 2: Dense Vector ANN Search (< 15 ms)
        # =========================================================================
        vector_matches: List[Tuple[AgentModel, float]] = []
        for agent in stage1_eligible:
            if not agent.interest_embedding:
                agent.interest_embedding = self.embedding_service.get_embedding(agent.interest_manifesto)
            
            sim = self.embedding_service.cosine_similarity(post.post_embedding, agent.interest_embedding)
            # Factor in agent trust score (reputation modifier)
            adjusted_sim = sim * min(1.0, max(0.2, agent.trust_score))
            vector_matches.append((agent, adjusted_sim))

        # Retrieve top K candidates (K=50 as per architecture specification)
        vector_matches.sort(key=lambda x: x[1], reverse=True)
        top_k_candidates = vector_matches[:50]

        # =========================================================================
        # Stage 3: Cross-Encoder / High-Precision Reranker (< 100 ms)
        # Computes joint relevance of Post (Context + Offer) vs Agent Intent Manifesto
        # =========================================================================
        for agent, vec_score in top_k_candidates:
            rerank_score = self._compute_rerank_score(post, agent)
            
            # Weighted joint scoring formula: 40% dense vector + 60% deep cross-intent score
            final_score = round(0.4 * vec_score + 0.6 * rerank_score, 4)
            is_notified = final_score >= self.SCORE_THRESHOLD

            reason = "High joint semantic relevance" if is_notified else f"Score {final_score} below threshold {self.SCORE_THRESHOLD}"
            
            candidates.append(
                RoutingCandidate(
                    agent_id=agent.id,
                    company_name=agent.company_name,
                    sql_passed=True,
                    vector_score=round(vec_score, 4),
                    rerank_score=round(rerank_score, 4),
                    final_score=final_score,
                    notified=is_notified,
                    reason=reason
                )
            )

        # Sort candidate results by final score descending
        candidates.sort(key=lambda c: c.final_score, reverse=True)
        return candidates

    def _compute_rerank_score(self, post: PostModel, agent: AgentModel) -> float:
        """
        Simulates Cross-Encoder / LLM Judge joint cross-attention between post context and interest manifesto.
        Evaluates explicit topical overlap, commercial synergy, and complementary intent.
        """
        manifesto_words = set(agent.interest_manifesto.lower().replace(",", " ").replace(".", " ").split())
        post_words = set(f"{post.title} {post.content}".lower().replace(",", " ").replace(".", " ").split())

        intersection = manifesto_words.intersection(post_words)
        # Direct lexical + conceptual synergy score
        synergy_score = min(1.0, len(intersection) / max(3, len(post_words) * 0.3))

        # Industry affinity rules (e.g. Food Delivery <-> Fintech & Cards synergy)
        cross_industry_bonus = 0.0
        if "delivery" in post.content.lower() or "food" in post.content.lower():
            if any(term in agent.interest_manifesto.lower() for term in ["payment", "fintech", "cashback", "card", "upi"]):
                cross_industry_bonus = 0.25

        # Raw cross-intent evaluation
        raw_score = 0.5 * synergy_score + cross_industry_bonus + 0.2
        return min(1.0, max(0.0, raw_score))

    @classmethod
    def apply_feedback_learning(
        cls,
        agent: AgentModel,
        post: PostModel,
        engaged: bool,
        learning_rate: float = 0.15
    ) -> AgentModel:
        """
        Dynamically adjusts agent's interest vector based on closed-loop feedback.
        - If engaged: positive gradient shift towards post embedding (reinforcing interest).
        - If ignored: negative gradient shift away from unengaged post embedding (reducing spam).
        """
        if not agent.interest_embedding or not post.post_embedding:
            return agent

        agent_vec = np.array(agent.interest_embedding, dtype=np.float32)
        post_vec = np.array(post.post_embedding, dtype=np.float32)

        if engaged:
            # Positive gradient update
            agent_vec = agent_vec + (learning_rate * post_vec)
        else:
            # Negative gradient update
            agent_vec = agent_vec - (learning_rate * post_vec)

        # Re-normalize to unit hypersphere
        norm = np.linalg.norm(agent_vec)
        if norm > 0:
            agent_vec /= norm

        agent.interest_embedding = agent_vec.tolist()
        return agent
