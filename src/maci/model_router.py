from __future__ import annotations

from .schemas import TaskType, TenantPolicy


class ModelRouter:
    """Cost-aware deterministic model routing.

    Expensive models are reserved for RAG/workflow/high-value tasks unless the
    caller explicitly requested an allowlisted model. This keeps routing outside
    the model and auditable.
    """

    def __init__(self, default_model_id: str) -> None:
        self.default_model_id = default_model_id

    def choose_model(self, *, task_type: TaskType, requested_model: str | None, policy: TenantPolicy, input_chars: int) -> str:
        if requested_model:
            return requested_model
        if task_type in {TaskType.SUPPORT_ANSWER, TaskType.TOOL_ACTION}:
            for candidate in policy.allowed_models:
                if "nova-lite" in candidate or "haiku" in candidate:
                    return candidate
        if task_type == TaskType.RAG and input_chars < 3000:
            for candidate in policy.allowed_models:
                if "nova-pro" in candidate or "sonnet" in candidate:
                    return candidate
        return self.default_model_id if self.default_model_id in policy.allowed_models else policy.allowed_models[0]
