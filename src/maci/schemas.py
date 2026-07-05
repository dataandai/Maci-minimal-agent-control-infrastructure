from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, PositiveInt


class StrictModel(BaseModel):
    """Base model that rejects unknown fields to prevent schema drift."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class TaskType(str, Enum):
    SUPPORT_ANSWER = "support_answer"
    RAG = "rag"
    TOOL_ACTION = "tool_action"
    WORKFLOW = "workflow"


class TenantContext(StrictModel):
    """Identity-derived context.

    This object must be built from trusted infrastructure claims, for example
    API Gateway JWT/Cognito authorizer claims or Bedrock Agent sessionAttributes.
    It must not be built from model-generated tool parameters.
    """

    tenant_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    roles: tuple[str, ...] = Field(default_factory=tuple)
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str | None = None
    conversation_id: str | None = None


class AgentRequest(StrictModel):
    """User request body.

    tenant_id/user_id are optional compatibility fields. They are never trusted
    as identity. The router compares them with authorizer claims and rejects a
    mismatch to catch client bugs or impersonation attempts.
    """

    tenant_id: str | None = Field(default=None, min_length=1)
    user_id: str | None = Field(default=None, min_length=1)
    task_type: TaskType
    input: str = Field(min_length=1, max_length=12000)
    requested_model: str | None = None
    requested_knowledge_base_id: str | None = None
    requested_tools: tuple[str, ...] = Field(default_factory=tuple)
    max_output_tokens: PositiveInt = 1024
    conversation_id: str | None = Field(default=None, min_length=1)


class GovernedRequest(StrictModel):
    """Policy evaluation input that binds request intent to trusted identity."""

    tenant_context: TenantContext
    task_type: TaskType
    input: str = Field(min_length=1, max_length=12000)
    requested_model: str | None = None
    requested_knowledge_base_id: str | None = None
    requested_tools: tuple[str, ...] = Field(default_factory=tuple)
    max_output_tokens: PositiveInt = 1024
    conversation_id: str | None = Field(default=None, min_length=1)


class AgentResponse(StrictModel):
    request_id: str
    tenant_id: str
    conversation_id: str | None = None
    answer: str
    model_id: str | None = None
    tool_calls: tuple[str, ...] = Field(default_factory=tuple)
    knowledge_base_id: str | None = None
    policy_decision_id: str
    circuit_breaker_open: bool = False
    mode: Literal["direct", "rag", "agent", "workflow"] = "direct"
    trace: dict[str, Any] = Field(default_factory=dict)


class ToolName(str, Enum):
    CUSTOMER_LOOKUP = "customer_lookup"
    TICKET_CREATION = "ticket_creation"
    BILLING_CHECK = "billing_check"
    ACCOUNT_CREDIT = "account_credit"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ResourceAction(str, Enum):
    READ_CUSTOMER = "read_customer"
    CREATE_TICKET = "create_ticket"
    READ_BILLING = "read_billing"
    ISSUE_CREDIT = "issue_credit"
    DELETE_DATA = "delete_data"


class AgentStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class CustomerLookupInput(StrictModel):
    """Model-controlled arguments for customer lookup.

    The tenant_id is intentionally absent. Tenant scope comes from Bedrock Agent
    sessionAttributes, not from the model-generated tool parameters.
    """

    customer_id: str = Field(min_length=1)
    reason: str = Field(min_length=3, max_length=500)


class CustomerLookupOutput(StrictModel):
    tenant_id: str
    customer_id: str
    status: Literal["active", "suspended", "unknown"]
    support_tier: Literal["standard", "premium", "enterprise"]


class TicketPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TicketCreationInput(StrictModel):
    """Model-controlled arguments for ticket creation.

    The tenant_id is intentionally absent. Tenant scope comes from Bedrock Agent
    sessionAttributes, not from the model-generated tool parameters.
    """

    customer_id: str = Field(min_length=1)
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=10, max_length=5000)
    priority: TicketPriority = TicketPriority.MEDIUM


class TicketCreationOutput(StrictModel):
    tenant_id: str
    ticket_id: str
    priority: TicketPriority
    created: bool


class BillingCheckInput(StrictModel):
    customer_id: str = Field(min_length=1)
    reason: str = Field(min_length=3, max_length=500)


class BillingCheckOutput(StrictModel):
    tenant_id: str
    customer_id: str
    account_status: Literal["current", "past_due", "suspended", "unknown"]
    outstanding_balance_usd: float = Field(ge=0)
    last_invoice_id: str | None = None


class AccountCreditInput(StrictModel):
    customer_id: str = Field(min_length=1)
    amount_usd: float = Field(gt=0, le=10000)
    reason: str = Field(min_length=10, max_length=1000)
    approval_id: str | None = Field(default=None, min_length=1)


class AccountCreditOutput(StrictModel):
    tenant_id: str
    customer_id: str
    amount_usd: float
    status: Literal["pending_approval", "approved", "rejected", "executed"]
    approval_id: str
    executed: bool = False


class AgentIdentity(StrictModel):
    agent_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    owner_user_id: str = Field(min_length=1)
    human_custodian: str = Field(min_length=1)
    status: AgentStatus = AgentStatus.ACTIVE
    allowed_tools: tuple[str, ...] = Field(default_factory=tuple)
    allowed_actions: tuple[ResourceAction, ...] = Field(default_factory=tuple)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    revoked_at: datetime | None = None


class ResourceOwnerRecord(StrictModel):
    resource_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    resource_type: Literal["customer", "account", "ticket"] = "customer"
    status: Literal["active", "suspended", "deleted"] = "active"


class ApprovalRecord(StrictModel):
    approval_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    request_id: str
    requested_by_user_id: str
    tool_name: str
    resource_id: str
    action: ResourceAction
    risk_level: RiskLevel
    payload: dict[str, Any] = Field(default_factory=dict)
    payload_hash: str = Field(min_length=16)
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    decided_at: datetime | None = None
    decided_by_user_id: str | None = None
    decision_reason: str | None = None


class OperationAuthorizationRequest(StrictModel):
    tenant_context: TenantContext
    tool_name: ToolName
    action: ResourceAction
    resource_id: str
    risk_level: RiskLevel = RiskLevel.LOW
    payload: dict[str, Any] = Field(default_factory=dict)


class OperationAuthorizationDecision(StrictModel):
    allowed: bool
    reason: str
    approval_required: bool = False
    approval_id: str | None = None


class PolicyDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


class PolicyDecisionRecord(StrictModel):
    decision_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    decision: PolicyDecision
    reason: str
    model_id: str | None = None
    knowledge_base_id: str | None = None
    tools: tuple[str, ...] = Field(default_factory=tuple)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TenantPolicy(StrictModel):
    tenant_id: str
    allowed_models: tuple[str, ...]
    allowed_knowledge_base_ids: tuple[str, ...] = Field(default_factory=tuple)
    allowed_tools: tuple[str, ...] = Field(default_factory=tuple)
    max_input_chars: PositiveInt = 12000
    max_output_tokens: PositiveInt = 2048
    monthly_budget_usd: float = Field(ge=0)
    current_month_spend_usd: float = Field(ge=0, default=0)
    allowed_customer_id_prefixes: tuple[str, ...] = Field(default_factory=tuple)
    allowed_resource_actions: tuple[ResourceAction, ...] = Field(default_factory=tuple)
    high_risk_tools: tuple[str, ...] = Field(default_factory=tuple)
    human_approval_required_tools: tuple[str, ...] = Field(default_factory=tuple)
    approver_roles: tuple[str, ...] = ("risk-approver", "admin")
    allowed_agent_ids: tuple[str, ...] = Field(default_factory=tuple)
    guardrail_identifier: str | None = None
    guardrail_version: str | None = None


class BedrockInvocationRequest(StrictModel):
    tenant_context: TenantContext
    model_id: str
    prompt: str
    max_output_tokens: PositiveInt
    guardrail_identifier: str | None = None
    guardrail_version: str | None = None


class BedrockInvocationResponse(StrictModel):
    model_id: str
    output_text: str
    input_tokens: int = Field(ge=0, default=0)
    output_tokens: int = Field(ge=0, default=0)
    raw: dict[str, Any] = Field(default_factory=dict)


class BedrockRetrieveRequest(StrictModel):
    tenant_context: TenantContext
    knowledge_base_id: str
    query: str
    number_of_results: PositiveInt = 5
    guardrail_identifier: str | None = None
    guardrail_version: str | None = None


class BedrockRetrieveResponse(StrictModel):
    knowledge_base_id: str
    retrieved_text: str
    source_count: int = Field(ge=0, default=0)
    raw: dict[str, Any] = Field(default_factory=dict)


class BedrockAgentInvocationRequest(StrictModel):
    tenant_context: TenantContext
    agent_id: str
    agent_alias_id: str
    session_id: str
    input_text: str
    enable_trace: bool = True


class BedrockAgentInvocationResponse(StrictModel):
    agent_id: str
    agent_alias_id: str
    output_text: str
    raw: dict[str, Any] = Field(default_factory=dict)


class WorkflowInvocationRequest(StrictModel):
    request_id: str
    tenant_id: str
    user_id: str
    input: str
    model_id: str
    max_output_tokens: PositiveInt
    guardrail_identifier: str | None = None
    guardrail_version: str | None = None
