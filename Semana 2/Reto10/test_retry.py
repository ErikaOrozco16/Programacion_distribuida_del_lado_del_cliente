import pytest

from retry import HttpClientError, HttpServerError, RetryEvent, with_retry


def test_retry_succeeds_after_two_503_errors():
    calls = {"count": 0}
    waits = []
    events: list[RetryEvent] = []

    @with_retry(max_retries=3, base_delay=1, jitter=0, sleep=waits.append, logger=events.append)
    def flaky():
        calls["count"] += 1
        if calls["count"] <= 2:
            raise HttpServerError(503)
        return {"id": 1}

    assert flaky() == {"id": 1}
    assert calls["count"] == 3
    assert waits == [1, 2]
    assert [event.attempt for event in events] == [1, 2]


def test_retry_stops_after_max_retries():
    waits = []

    @with_retry(max_retries=2, base_delay=1, jitter=0, sleep=waits.append)
    def always_fails():
        raise HttpServerError(503)

    with pytest.raises(HttpServerError):
        always_fails()
    assert waits == [1, 2]


def test_retry_does_not_retry_4xx():
    calls = {"count": 0}

    @with_retry(max_retries=3, sleep=lambda _: None)
    def bad_request():
        calls["count"] += 1
        raise HttpClientError(400)

    with pytest.raises(HttpClientError):
        bad_request()
    assert calls["count"] == 1


def test_retry_handles_timeout():
    calls = {"count": 0}
    waits = []

    @with_retry(max_retries=1, base_delay=0.5, jitter=0, sleep=waits.append)
    def timeout_once():
        calls["count"] += 1
        if calls["count"] == 1:
            raise TimeoutError("lento")
        return "ok"

    assert timeout_once() == "ok"
    assert waits == [0.5]


def test_retry_adds_jitter():
    waits = []

    @with_retry(max_retries=1, base_delay=10, jitter=0.2, random_fn=lambda: 0.5, sleep=waits.append)
    def fail_then_ok():
        if not waits:
            raise HttpServerError(500)
        return "ok"

    assert fail_then_ok() == "ok"
    assert waits == [11.0]


def test_retry_caps_delay():
    waits = []
    calls = {"count": 0}

    @with_retry(max_retries=3, base_delay=10, max_delay=15, jitter=0, sleep=waits.append)
    def fail_three_times():
        calls["count"] += 1
        if calls["count"] <= 3:
            raise HttpServerError(503)
        return "ok"

    assert fail_three_times() == "ok"
    assert waits == [10, 15, 15]
