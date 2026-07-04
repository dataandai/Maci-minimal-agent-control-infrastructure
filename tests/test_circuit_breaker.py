from maci.circuit_breaker import CircuitBreaker, FailureCategory


def test_circuit_breaker_opens_after_threshold():
    breaker = CircuitBreaker(threshold=3)
    assert not breaker.is_open(FailureCategory.SCHEMA_VALIDATION_FAILED)
    breaker.record_failure(FailureCategory.SCHEMA_VALIDATION_FAILED)
    breaker.record_failure(FailureCategory.SCHEMA_VALIDATION_FAILED)
    assert not breaker.is_open(FailureCategory.SCHEMA_VALIDATION_FAILED)
    breaker.record_failure(FailureCategory.SCHEMA_VALIDATION_FAILED)
    assert breaker.is_open(FailureCategory.SCHEMA_VALIDATION_FAILED)


def test_circuit_breaker_resets_on_success():
    breaker = CircuitBreaker(threshold=1)
    breaker.record_failure(FailureCategory.TOOL_NOT_ALLOWED)
    assert breaker.is_open(FailureCategory.TOOL_NOT_ALLOWED)
    breaker.record_success(FailureCategory.TOOL_NOT_ALLOWED)
    assert not breaker.is_open(FailureCategory.TOOL_NOT_ALLOWED)
