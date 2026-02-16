from communication.core.retry_engine import RetryEngine


def test_retry_exponential_backoff_progresses_forward():
    retry = RetryEngine(base_seconds=1)
    first = retry.next_attempt(0)
    second = retry.next_attempt(1)
    third = retry.next_attempt(2)
    assert second > first
    assert third > second
    assert retry.should_retry(0) is True
    assert retry.should_retry(4) is False
