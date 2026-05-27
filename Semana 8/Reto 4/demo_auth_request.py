from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "Reto IA 3"))
sys.path.append(str(Path(__file__).resolve().parents[1] / "Reto IA 4"))

from auth_client import MockResponse, auth_request
from token_manager import TokenManager


VALID_ACCESS = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiJ1c2VyXzEiLCJleHAiOjk5OTk5OTk5OTksImlhdCI6MTcxNDAwMH0."
    "firma_simulada"
)
EXPIRED_ACCESS = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiJ1c2VyXzIiLCJleHAiOjE3MDAwMDAwMDAsImlhdCI6MTcwMDAwMDAwMH0."
    "firma_simulada"
)
REFRESH_TOKEN = "refresh_token_simulado_ecomarket"

server_state = {"resource_calls": 0, "refresh_calls": 0}


def refresh_client(refresh_token: str) -> dict:
    server_state["refresh_calls"] += 1
    if refresh_token != REFRESH_TOKEN:
        raise RuntimeError("refresh_token invalido")
    return {"access_token": VALID_ACCESS}


def mock_request(method: str, url: str, headers=None, **kwargs) -> MockResponse:
    if "/api/ecomarket/precios" in url:
        server_state["resource_calls"] += 1
        if server_state["resource_calls"] == 1:
            return MockResponse(401, text="access_token expirado")
        auth = (headers or {}).get("Authorization", "")
        if auth == f"Bearer {VALID_ACCESS}":
            return MockResponse(200, {"producto": "Cafe organico", "precio": 129.5})
        return MockResponse(401, text="token invalido")
    return MockResponse(404, text="no encontrado")


def main() -> None:
    manager = TokenManager(refresh_client)
    manager.store_tokens(EXPIRED_ACCESS, REFRESH_TOKEN)

    response = auth_request(
        mock_request,
        manager,
        "GET",
        "http://localhost:8080/api/ecomarket/precios",
    )

    print(f"Status final: {response.status_code}")
    print(f"Body final: {response.json()}")
    print(f"Peticiones al recurso: {server_state['resource_calls']}")
    print(f"Peticiones reales de refresh: {server_state['refresh_calls']}")


if __name__ == "__main__":
    main()
