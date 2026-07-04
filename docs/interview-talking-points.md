# Interview Talking Points

## One-liner

I use Bedrock as the managed model layer and build deterministic governance around it: identity, tenant policy, schema validation, guardrails, tool allowlists, auditability, observability, and circuit breakers.

## Business framing

The hard part is not calling an LLM. The hard part is letting an AI agent touch customer data and business tools without breaking tenant isolation, auditability, compliance, or cost controls.

## Technical framing

The model remains probabilistic, but the platform boundary is deterministic.

I would not let the model decide security-sensitive routing. The model may propose an action, but Lambda-side policy decides whether the model, tool, knowledge base, and token budget are allowed.

## Why Lambda and Step Functions

Lambda is ideal for short, isolated control-plane and tool-execution steps. Step Functions is better for multi-step workflows, retries, explicit state, and failure branches.

## Why not own GPU serving here

For this business case I would not operate a GPU pool unless there is a specific latency, cost, data-residency, or custom-model requirement. Bedrock reduces operational burden, while the differentiating engineering work is the control plane around it.

## Strong sentence

I don't wrap models; I constrain them with deterministic software boundaries.
