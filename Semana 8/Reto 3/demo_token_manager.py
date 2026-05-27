import json
import time
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "Reto IA 3"))

from token_manager import TokenManager


ACCESS_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiJ1c2VyXzEiLCJleHAiOjk5OTk5OTk5OTksImlhdCI6MTcxNDAwMH0."
    "firma_simulada"
)
REFRESH_TOKEN = "refresh_token_simulado_ecomarket"


def refresh_client(refresh_token: str) -> dict:
    if refresh_token != REFRESH_TOKEN:
        raise RuntimeError("refresh_token invalido")
    return {"access_token": ACCESS_TOKEN, "expires_in": 900}


def main() -> None:
    manager = TokenManager(refresh_client)
    print("Login simulado correcto")
    manager.store_tokens(ACCESS_TOKEN, REFRESH_TOKEN)

    payload = manager.decode_payload()
    print("Payload decodificado:")
    print(json.dumps(payload, indent=2))
    print(f"Minutos restantes: {manager.minutes_until_expiration():.2f}")
    print(f"Header auth: {manager.get_auth_header()}")

    nuevo_token = manager.refresh_access_token()
    print(f"Refresh correcto: {nuevo_token[:30]}...")

    manager.logout()
    print(f"Header despues de logout: {manager.get_auth_header()}")


if __name__ == "__main__":
    main()
