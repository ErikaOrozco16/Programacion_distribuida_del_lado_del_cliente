from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import quote, urlencode


@dataclass(frozen=True)
class EndpointCall:
    method: str
    path: str
    requires_auth: bool
    success_status: int


class EcoMarketContractClient:
    base_path = "/v1"

    operations = {
        "listar_productos": EndpointCall("GET", "/productos", False, 200),
        "crear_producto": EndpointCall("POST", "/productos", True, 201),
        "obtener_producto": EndpointCall("GET", "/productos/{id}", False, 200),
        "actualizar_producto_total": EndpointCall("PUT", "/productos/{id}", True, 200),
        "actualizar_producto_parcial": EndpointCall("PATCH", "/productos/{id}", True, 200),
        "eliminar_producto": EndpointCall("DELETE", "/productos/{id}", True, 204),
    }

    def __init__(self, base_url: str, token: str | None = None, transport: Callable[..., Any] | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.transport = transport

    def build_url(self, operation: str, product_id: int | None = None, **query: Any) -> str:
        call = self.operations[operation]
        path = call.path
        if "{id}" in path:
            if not isinstance(product_id, int) or product_id < 0:
                raise ValueError("product_id debe ser entero no negativo")
            path = path.replace("{id}", quote(str(product_id), safe=""))
        clean_query = {key: value for key, value in query.items() if value is not None}
        suffix = f"?{urlencode(clean_query)}" if clean_query else ""
        return f"{self.base_url}{path}{suffix}"

    def headers_for(self, operation: str) -> dict[str, str]:
        headers = {"Accept": "application/json", "X-Request-Id": "semana2-reto9"}
        if self.operations[operation].requires_auth:
            if not self.token:
                raise PermissionError("Operacion protegida sin token")
            headers["Authorization"] = f"Bearer {self.token}"
            headers["Content-Type"] = "application/json"
        return headers
