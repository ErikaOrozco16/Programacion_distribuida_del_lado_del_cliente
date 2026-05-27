from pathlib import Path
import sys
from typing import Callable

sys.path.append(str(Path(__file__).resolve().parents[1] / "Reto IA 3"))

from token_manager import TokenManager, TokenRefreshError


class MockResponse:
    def __init__(self, status_code: int, json_body=None, text: str = ""):
        self.status_code = status_code
        self._json_body = json_body or {}
        self.text = text

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self) -> dict:
        return self._json_body


def auth_request(
    request_func: Callable[..., MockResponse],
    token_manager: TokenManager,
    method: str,
    url: str,
    *,
    retry: bool = True,
    **kwargs,
) -> MockResponse:
    headers = dict(kwargs.pop("headers", {}) or {})
    headers.update(token_manager.get_auth_header())
    response = request_func(method, url, headers=headers, **kwargs)

    if response.status_code != 401:
        return response

    if "/api/auth/refresh" in url or not retry:
        token_manager.logout()
        return response

    try:
        token_manager.refresh_access_token()
    except TokenRefreshError:
        token_manager.logout()
        return response

    headers = dict(kwargs.pop("headers", {}) or {})
    headers.update(token_manager.get_auth_header())
    retry_response = request_func(method, url, headers=headers, **kwargs)

    if retry_response.status_code == 401:
        token_manager.logout()

    return retry_response
