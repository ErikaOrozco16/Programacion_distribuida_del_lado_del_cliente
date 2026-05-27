import base64
import json
import time


TOKEN_ECOMARKET = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiJ1c2VyXzQ1NiIsImVtYWlsIjoiYW5hQGVjb21hcmtldC5teCIsInJvbGUiOiJvcGVyYXRvciIsImV4cCI6MTcxNDAwMDAwMCwiaWF0IjoxNzEzOTk5MTAwfQ."
    "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
)


def _decode_base64url(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def decode_payload(token: str) -> dict:
    """Decodifica el payload de un JWT sin usar librerias JWT.

    El cliente puede leer el payload porque esta codificado en Base64URL, no cifrado.
    No se verifica la firma aqui: esa decision de seguridad pertenece al servidor.
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("JWT malformado: debe tener header.payload.signature")

    try:
        payload_bytes = _decode_base64url(parts[1])
        claims = json.loads(payload_bytes.decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("JWT malformado: payload no valido") from exc

    exp = claims.get("exp")
    if isinstance(exp, (int, float)):
        remaining_minutes = (exp - time.time()) / 60
        print(f"Tiempo restante aproximado: {remaining_minutes:.2f} minutos")
    else:
        print("El token no incluye exp; el cliente debe tratarlo como expirado.")

    return claims


if __name__ == "__main__":
    payload = decode_payload(TOKEN_ECOMARKET)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
