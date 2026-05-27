import base64
import json
import threading
import time
from typing import Callable, Optional


class TokenRefreshError(RuntimeError):
    pass


class TokenManager:
    def __init__(self, refresh_client: Callable[[str], dict], margin_seconds: int = 300):
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._refresh_client = refresh_client
        self._margin_seconds = margin_seconds
        self._lock = threading.Condition()
        self._is_refreshing = False
        self._last_refresh_error: Optional[BaseException] = None
        self._proactive_timer = None

    @staticmethod
    def _decode_base64url(value: str) -> bytes:
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(value + padding)

    def decode_payload(self, token: Optional[str] = None) -> dict:
        # Se lee el payload para UX y expiracion; la firma se valida en el servidor.
        raw_token = token or self._access_token
        if not raw_token:
            raise ValueError("No hay access_token disponible")

        parts = raw_token.split(".")
        if len(parts) != 3:
            raise ValueError("JWT malformado: debe tener exactamente 3 partes")

        try:
            payload_bytes = self._decode_base64url(parts[1])
            return json.loads(payload_bytes.decode("utf-8"))
        except (ValueError, json.JSONDecodeError) as exc:
            raise ValueError("JWT malformado: payload no es JSON valido") from exc

    def minutes_until_expiration(self, token: Optional[str] = None) -> float:
        claims = self.decode_payload(token)
        exp = claims.get("exp")
        if not isinstance(exp, (int, float)):
            return 0.0
        return max(0.0, (exp - time.time()) / 60)

    def is_expiring_soon(self, margin_seconds: Optional[int] = None) -> bool:
        # exp esta en segundos Unix; no se compara contra milisegundos.
        if not self._access_token:
            return True
        try:
            exp = self.decode_payload().get("exp")
        except ValueError:
            return True
        if not isinstance(exp, (int, float)):
            return True
        margin = self._margin_seconds if margin_seconds is None else margin_seconds
        return exp - time.time() <= margin

    def store_tokens(self, access_token: str, refresh_token: Optional[str] = None) -> None:
        # El refresh_token se conserva solo si el servidor envio uno nuevo.
        self._access_token = access_token
        if refresh_token is not None:
            self._refresh_token = refresh_token

    def get_auth_header(self) -> dict:
        # Centralizar el header evita que cada llamada lo construya a mano.
        if not self._access_token:
            return {}
        return {"Authorization": f"Bearer {self._access_token}"}

    def refresh_access_token(self) -> str:
        # El Condition convierte refresh en singleton para llamadas concurrentes.
        with self._lock:
            if self._is_refreshing:
                while self._is_refreshing:
                    self._lock.wait()
                if self._last_refresh_error:
                    raise TokenRefreshError("Refresh compartido fallo") from self._last_refresh_error
                if not self._access_token:
                    raise TokenRefreshError("Refresh compartido no produjo access_token")
                return self._access_token

            if not self._refresh_token:
                raise TokenRefreshError("No hay refresh_token disponible")

            self._is_refreshing = True
            self._last_refresh_error = None
            refresh_token = self._refresh_token

        try:
            response = self._refresh_client(refresh_token)
            new_access = response.get("access_token")
            if not new_access:
                raise TokenRefreshError("El refresh no devolvio access_token")
            self.store_tokens(new_access, response.get("refresh_token"))
            return new_access
        except BaseException as exc:
            self._last_refresh_error = exc
            raise
        finally:
            with self._lock:
                self._is_refreshing = False
                self._lock.notify_all()

    def logout(self) -> None:
        # Logout debe limpiar tokens, timer y estado de refresh para evitar tokens fantasma.
        if self._proactive_timer:
            self._proactive_timer.cancel()
            self._proactive_timer = None
        with self._lock:
            self._access_token = None
            self._refresh_token = None
            self._is_refreshing = False
            self._last_refresh_error = None
            self._lock.notify_all()
