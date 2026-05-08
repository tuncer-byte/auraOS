"""
AuraOS - Finansal AI Agent Framework
"""

from auraos.config import AuraOSConfig
from auraos.core.agent import Agent
from auraos.core.autonomous_agent import AutonomousAgent
from auraos.core.task import Task
from auraos.core.response import AgentResponse
from auraos.exceptions import (
    AuraOSError,
    AgentError,
    LLMError,
    ToolError,
    ToolApprovalRequired,
    SessionError,
    GuardrailError,
    RateLimitExceededError,
)
from auraos.guardrails import Guardrails
from auraos.knowledge.base import KnowledgeBase
from auraos.knowledge.embeddings import (
    EmbeddingProvider,
    HashEmbedding,
    OpenAIEmbedding,
    GeminiEmbedding,
    SentenceTransformerEmbedding,
    get_embedding_provider,
)
from auraos.llm.factory import get_llm
from auraos.llm.base import LLMResponse, StreamChunk
from auraos.memory.base import Memory
from auraos.memory.conversation import ConversationMemory
from auraos.memory.session import (
    Session,
    SessionManager,
    InMemorySessionStore,
    RedisSessionStore,
)
from auraos.team.team import Team, TeamMode
from auraos.tools.decorator import tool
from auraos.tools.registry import ToolRegistry, ApprovalCallback, AlwaysApprove
from auraos.utils.cache import InMemoryCache, RedisCache, get_default_cache
from auraos.utils.rate_limit import RateLimiter, TokenBucket, get_rate_limiter

from auraos.observability.audit import AuditLog, AuditRecord
from auraos.observability.cost import CostTracker, DEFAULT_PRICING
from auraos.observability.metrics import METRICS, MetricsRegistry, Counter, Gauge, Histogram, Timer
from auraos.observability.structured_logger import (
    configure_json_logging,
    new_correlation_id,
    set_correlation_id,
    get_correlation_id,
    set_session_id,
    set_tenant_id,
)
from auraos.security.rbac import (
    AuthorizationError,
    Principal,
    RBACGuard,
    set_principal,
    get_principal,
)
from auraos.utils.circuit_breaker import CircuitBreaker, CircuitOpenError, CircuitState
from auraos.utils.idempotency import IdempotencyStore, make_idempotency_key

__version__ = "0.2.0"
__all__ = [
    "Agent",
    "AutonomousAgent",
    "Task",
    "AgentResponse",
    "AuraOSConfig",
    "tool",
    "ToolRegistry",
    "ApprovalCallback",
    "AlwaysApprove",
    "Memory",
    "ConversationMemory",
    "Session",
    "SessionManager",
    "InMemorySessionStore",
    "RedisSessionStore",
    "KnowledgeBase",
    "EmbeddingProvider",
    "HashEmbedding",
    "OpenAIEmbedding",
    "GeminiEmbedding",
    "SentenceTransformerEmbedding",
    "get_embedding_provider",
    "Team",
    "TeamMode",
    "get_llm",
    "LLMResponse",
    "StreamChunk",
    "Guardrails",
    "InMemoryCache",
    "RedisCache",
    "get_default_cache",
    "RateLimiter",
    "TokenBucket",
    "get_rate_limiter",
    # Enterprise
    "AuditLog",
    "AuditRecord",
    "CostTracker",
    "DEFAULT_PRICING",
    "METRICS",
    "MetricsRegistry",
    "Counter",
    "Gauge",
    "Histogram",
    "Timer",
    "configure_json_logging",
    "new_correlation_id",
    "set_correlation_id",
    "get_correlation_id",
    "set_session_id",
    "set_tenant_id",
    "Principal",
    "RBACGuard",
    "set_principal",
    "get_principal",
    "AuthorizationError",
    "CircuitBreaker",
    "CircuitOpenError",
    "CircuitState",
    "IdempotencyStore",
    "make_idempotency_key",
    # Exceptions
    "AuraOSError",
    "AgentError",
    "LLMError",
    "ToolError",
    "ToolApprovalRequired",
    "SessionError",
    "GuardrailError",
    "RateLimitExceededError",
]
