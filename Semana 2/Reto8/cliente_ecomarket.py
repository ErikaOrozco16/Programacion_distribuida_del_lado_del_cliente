from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import quote, urlencode


class ApiError(Exception):
    pass


class ValidationError(ApiError):
    pass


class NotFoundError(ApiError):
    pass


class UnauthorizedError(ApiError):
    pass


class ConflictError(ApiError):
    pass


@dataclass
class Response:
    status: int
    body: Any = None
    content_type: str = "application/json"


Transport = Callable[[str, str, dict[str, str], Any], Response]


VALID_CATEGORIES = {"frutas", "verduras", "lacteos", "miel", "conservas"}


def validate_product(product: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(product, dict):
        raise ValidationError("El producto debe ser un objeto")
    required = {
        "id": int,
        "nombre": str,
        "descripcion": str,
        "precio": (int, float),
        "categoria": str,
        "productor_id": int,
        "disponible": bool,
        "creado_en": str,
    }
    for field, expected_type in required.items():
        if field not in product:
            raise ValidationError(f"Falta {field}")
        if not isinstance(product[field], expected_type):
            raise ValidationError(f"Tipo invalido para {field}")
    if product["precio"] <= 0:
        raise ValidationError("El precio debe ser positivo")
    if product["categoria"] not in VALID_CATEGORIES:
        raise ValidationError("Categoria invalida")
    return product


def validate_product_input(product: dict[str, Any], partial: bool = False) -> dict[str, Any]:
    if not isinstance(product, dict) or not product:
        raise ValidationError("Los datos deben ser un objeto no vacio")
    required = {"nombre", "descripcion", "precio", "categoria", "productor_id"}
    if not partial:
        missing = required - product.keys()
        if missing:
            raise ValidationError(f"Faltan campos: {', '.join(sorted(missing))}")
    if "precio" in product and (not isinstance(product["precio"], (int, float)) or product["precio"] <= 0):
        raise ValidationError("Precio invalido")
    if "categoria" in product and product["categoria"] not in VALID_CATEGORIES:
        raise ValidationError("Categoria invalida")
    if "productor_id" in product and not isinstance(product["productor_id"], int):
        raise ValidationError("productor_id invalido")
    return product


class EcoMarketClient:
    def __init__(self, base_url: str, token: str | None = None, transport: Transport | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.transport = transport or self._missing_transport

    def listar_productos(self, categoria: str | None = None, productor_id: int | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if categoria is not None:
            if categoria not in VALID_CATEGORIES:
                raise ValidationError("Categoria invalida")
            params["categoria"] = categoria
        if productor_id is not None:
            if not isinstance(productor_id, int):
                raise ValidationError("productor_id debe ser entero")
            params["productor_id"] = productor_id
        path = "/productos"
        if params:
            path += "?" + urlencode(params)
        body = self._send("GET", path, expected={200})
        if not isinstance(body, list):
            raise ValidationError("La respuesta no es una lista")
        return [validate_product(item) for item in body]

    def crear_producto(self, data: dict[str, Any]) -> dict[str, Any]:
        validate_product_input(data)
        return validate_product(self._send("POST", "/productos", body=data, expected={201}, auth=True))

    def obtener_producto(self, product_id: int) -> dict[str, Any]:
        return validate_product(self._send("GET", f"/productos/{self._id(product_id)}", expected={200}))

    def actualizar_producto_total(self, product_id: int, data: dict[str, Any]) -> dict[str, Any]:
        validate_product_input(data)
        return validate_product(self._send("PUT", f"/productos/{self._id(product_id)}", body=data, expected={200}, auth=True))

    def actualizar_producto_parcial(self, product_id: int, data: dict[str, Any]) -> dict[str, Any]:
        validate_product_input(data, partial=True)
        return validate_product(self._send("PATCH", f"/productos/{self._id(product_id)}", body=data, expected={200}, auth=True))

    def eliminar_producto(self, product_id: int) -> bool:
        self._send("DELETE", f"/productos/{self._id(product_id)}", expected={204}, auth=True)
        return True

    def _send(self, method: str, path: str, expected: set[int], body: Any = None, auth: bool = False) -> Any:
        headers = {"Accept": "application/json", "X-Request-Id": "semana2-reto8"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if auth:
            if not self.token:
                raise UnauthorizedError("Operacion protegida sin token")
            headers["Authorization"] = f"Bearer {self.token}"
        response = self.transport(method, self.base_url + path, headers, body)
        if response.status in expected:
            if response.status == 204:
                return None
            if "application/json" not in response.content_type:
                raise ValidationError("La respuesta no es JSON")
            return response.body
        if response.status == 401:
            raise UnauthorizedError("No autorizado")
        if response.status == 404:
            raise NotFoundError("Producto no encontrado")
        if response.status == 409:
            raise ConflictError("Conflicto")
        raise ApiError(f"Error HTTP {response.status}")

    def _id(self, product_id: int) -> str:
        if not isinstance(product_id, int) or product_id < 0:
            raise ValidationError("id invalido")
        return quote(str(product_id), safe="")

    def _missing_transport(self, *_: Any) -> Response:
        raise ApiError("No se configuro transporte HTTP")
