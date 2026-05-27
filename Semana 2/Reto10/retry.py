from __future__ import annotations

import functools
import random
import time
from dataclasses import dataclass
from typing import Callable, TypeVar


class HttpClientError(Exception):
    def __init__(self, status_code: int, message: str = ""):
        super().__init__(message or f"HTTP {status_code}")
        self.status_code = status_code


class HttpServerError(Exception):
    def __init__(self, status_code: int, message: str = ""):
        super().__init__(message or f"HTTP {status_code}")
        self.status_code = status_code


@dataclass
class RetryEvent:
    attempt: int
    wait_seconds: float
    error: str


T = TypeVar("T")


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: float = 0.25,
    sleep: Callable[[float], None] = time.sleep,
    random_fn: Callable[[], float] = random.random,
    logger: Callable[[RetryEvent], None] | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            attempt = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except HttpClientError:
                    raise
                except (TimeoutError, HttpServerError) as exc:
                    if attempt >= max_retries:
                        raise
                    wait = min(base_delay * (2 ** attempt), max_delay)
                    if jitter:
                        variation = wait * jitter * random_fn()
                        wait += variation
                    event = RetryEvent(attempt=attempt + 1, wait_seconds=wait, error=str(exc))
                    if logger:
                        logger(event)
                    sleep(wait)
                    attempt += 1
        return wrapper
    return decorator


def obtener_producto_con_retry(fetch_producto: Callable[[int], dict], producto_id: int) -> dict:
    @with_retry(max_retries=3)
    def obtener() -> dict:
        return fetch_producto(producto_id)

    return obtener()
