from __future__ import annotations

from typing import Any, Mapping

from .approval import ApprovalStore
from .authorization import AuthorizationError, ResourceAuthorizer
from .schemas import OperationAuthorizationDecision, ResourceAction, RiskLevel, TenantContext, ToolName
from .mcp_registry import MCPRegistryError, MCPServerRegistry
from .tool_security import ToolSecurityError, enforce_tool_allowed


class MCPGatewayDenied(PermissionError):
    """Raised when an MCP/tool operation is denied before execution."""


class MCPToolGateway:
    """Enterprise MCP gateway pattern for per-operation enforcement.

    This is not an MCP transport implementation. It is the policy boundary that
    a real MCP server adapter should call before exposing a tool operation to an
    agent. The adapter can either pass a precomputed fingerprint from a trusted
    attestation path or pass the concrete manifest so this boundary computes and
    verifies the fingerprint itself.
    """

    def __init__(self, authorizer: ResourceAuthorizer | None = None, approval_store: ApprovalStore | None = None, registry: MCPServerRegistry | None = None) -> None:
        self.authorizer = authorizer or ResourceAuthorizer()
        self.approval_store = approval_store or ApprovalStore()
        self.registry = registry or MCPServerRegistry()

    def authorize_operation(
        self,
        tenant_context: TenantContext,
        *,
        tool_name: ToolName,
        action: ResourceAction,
        resource_id: str,
        risk_level: RiskLevel = RiskLevel.LOW,
        payload: dict | None = None,
        server_id: str | None = None,
        server_fingerprint: str | None = None,
        server_manifest: Mapping[str, Any] | None = None,
    ) -> OperationAuthorizationDecision:
        if server_id is not None:
            if server_fingerprint is None and server_manifest is None:
                raise MCPGatewayDenied("MCP server fingerprint or manifest is required")
            try:
                self.registry.verify_server_for_tool(
                    tenant_context,
                    server_id=server_id,
                    tool_name=tool_name.value,
                    presented_fingerprint=server_fingerprint,
                    presented_manifest=server_manifest,
                )
            except MCPRegistryError as exc:
                raise MCPGatewayDenied(str(exc)) from exc
        try:
            enforce_tool_allowed(tenant_context, tool_name, action=action)
        except ToolSecurityError as exc:
            raise MCPGatewayDenied(str(exc)) from exc
        try:
            return self.authorizer.enforce_customer_action(
                tenant_context,
                tool_name=tool_name,
                customer_id=resource_id,
                action=action,
                risk_level=risk_level,
                payload=payload or {},
            )
        except AuthorizationError as exc:
            raise MCPGatewayDenied(str(exc)) from exc
