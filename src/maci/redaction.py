from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from typing import Any

from pydantic import Field

from .schemas import StrictModel


class PIIFinding(StrictModel):
    """A non-sensitive description of a redacted value.

    The raw detected value is intentionally not stored. Logs and audit metadata
    can keep the kind/path/fingerprint without retaining the sensitive string.
    """

    kind: str = Field(min_length=1)
    path: str = Field(min_length=1)
    fingerprint: str = Field(min_length=8)


class RedactionResult(StrictModel):
    value: Any
    findings: tuple[PIIFinding, ...] = Field(default_factory=tuple)
    redacted: bool = False


@dataclass(frozen=True)
class RedactionService:
    """Deterministic PII/secrets redaction for transcripts, audit and logs.

    This local implementation is intentionally dependency-free so it can run in
    Lambda and unit tests. Production deployments can still add Bedrock
    Guardrails/Comprehend before this layer, but this service is the fail-safe
    local boundary that ensures obvious sensitive values are not persisted raw.
    """

    enabled: bool | None = None
    stable_salt: str = "maci-redaction-v1"

    def __post_init__(self) -> None:
        if self.enabled is None:
            object.__setattr__(
                self,
                "enabled",
                os.getenv("ENABLE_PII_REDACTION", "true").lower() not in {"0", "false", "no", "off"},
            )
        object.__setattr__(self, "stable_salt", os.getenv("PII_REDACTION_SALT", self.stable_salt))

    def redact_text(self, text: str, *, path: str = "root") -> RedactionResult:
        if not self.enabled or not text:
            return RedactionResult(value=text)

        findings: list[PIIFinding] = []
        redacted = text

        for spec in _PATTERNS:
            redacted = spec.apply(redacted, path=path, redactor=self, findings=findings)

        # Card-like numbers run before phone detection so card groups are not
        # partially consumed as telephone numbers.
        redacted = _redact_card_numbers(redacted, path=path, redactor=self, findings=findings)
        redacted = _PHONE_PATTERN.apply(redacted, path=path, redactor=self, findings=findings)

        return RedactionResult(value=redacted, findings=tuple(findings), redacted=bool(findings))

    def redact_value(self, value: Any, *, path: str = "root") -> RedactionResult:
        if not self.enabled:
            return RedactionResult(value=value)
        if isinstance(value, str):
            return self.redact_text(value, path=path)
        if isinstance(value, dict):
            out: dict[str, Any] = {}
            findings: list[PIIFinding] = []
            for key, child in value.items():
                child_path = f"{path}.{key}"
                # Redact suspicious key names even if the value is not recognized
                # by a value regex. This catches API keys and tokens that do not
                # follow a standard format.
                if _looks_sensitive_key(str(key)) and child not in (None, ""):
                    out[key] = _placeholder("SECRET", self._fingerprint(str(child)))
                    findings.append(PIIFinding(kind="SECRET", path=child_path, fingerprint=self._fingerprint(str(child))))
                    continue
                result = self.redact_value(child, path=child_path)
                out[key] = result.value
                findings.extend(result.findings)
            return RedactionResult(value=out, findings=tuple(findings), redacted=bool(findings))
        if isinstance(value, list):
            out_list: list[Any] = []
            findings = []
            for idx, child in enumerate(value):
                result = self.redact_value(child, path=f"{path}[{idx}]")
                out_list.append(result.value)
                findings.extend(result.findings)
            return RedactionResult(value=out_list, findings=tuple(findings), redacted=bool(findings))
        if isinstance(value, tuple):
            result = self.redact_value(list(value), path=path)
            return RedactionResult(value=tuple(result.value), findings=result.findings, redacted=result.redacted)
        return RedactionResult(value=value)

    def _finding(self, kind: str, path: str, raw: str) -> PIIFinding:
        return PIIFinding(kind=kind, path=path, fingerprint=self._fingerprint(raw))

    def _fingerprint(self, raw: str) -> str:
        return hashlib.sha256(f"{self.stable_salt}:{raw}".encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class _PatternSpec:
    kind: str
    pattern: re.Pattern[str]

    def apply(self, text: str, *, path: str, redactor: RedactionService, findings: list[PIIFinding]) -> str:
        def replace(match: re.Match[str]) -> str:
            raw = match.group(0)
            findings.append(redactor._finding(self.kind, path, raw))
            return _placeholder(self.kind, redactor._fingerprint(raw))

        return self.pattern.sub(replace, text)


_PATTERNS = (
    _PatternSpec("AUTH_TOKEN", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{16,}")),
    _PatternSpec("EMAIL", re.compile(r"(?<![\w.+-])([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})(?![\w.+-])")),
    _PatternSpec("IBAN", re.compile(r"\b[A-Z]{2}\d{2}(?:[ -]?[A-Z0-9]){11,30}\b")),
    _PatternSpec("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
)

_PHONE_PATTERN = _PatternSpec("PHONE", re.compile(r"(?<!\w)(?:\+?\d{1,3}[ -]?)?(?:\d[ -]?){8,14}\d(?!\w)"))

_SENSITIVE_KEYWORDS = (
    "authorization",
    "auth",
    "token",
    "secret",
    "api_key",
    "apikey",
    "password",
    "passwd",
    "cookie",
    "session",
    "credential",
    "private_key",
)

_CARD_CANDIDATE_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")


def _looks_sensitive_key(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    return any(keyword in lowered for keyword in _SENSITIVE_KEYWORDS)


def _redact_card_numbers(text: str, *, path: str, redactor: RedactionService, findings: list[PIIFinding]) -> str:
    def replace(match: re.Match[str]) -> str:
        raw = match.group(0)
        digits = re.sub(r"\D", "", raw)
        if len(digits) < 13 or len(digits) > 19 or not _passes_luhn(digits):
            return raw
        findings.append(redactor._finding("PAYMENT_CARD", path, raw))
        return _placeholder("PAYMENT_CARD", redactor._fingerprint(raw))

    return _CARD_CANDIDATE_RE.sub(replace, text)


def _passes_luhn(digits: str) -> bool:
    total = 0
    reverse_digits = digits[::-1]
    for idx, char in enumerate(reverse_digits):
        n = int(char)
        if idx % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def _placeholder(kind: str, fingerprint: str) -> str:
    return f"[REDACTED:{kind}:{fingerprint}]"


def finding_labels(findings: tuple[PIIFinding, ...] | list[PIIFinding]) -> tuple[str, ...]:
    return tuple(f"{finding.path}:{finding.kind}:{finding.fingerprint}" for finding in findings)
