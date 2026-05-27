import pytest

from cliente_ecomarket import (
    ApiError,
    ConflictError,
    EcoMarketClient,
    NotFoundError,
    Response,
    UnauthorizedError,
    ValidationError,
    validate_product,
)


def producto(**overrides):
    base = {
        "id": 1,
        "nombre": "Miel organica",
        "descripcion": "Frasco de 500g",
        "precio": 150.0,
        "categoria": "miel",
        "productor_id": 7,
        "disponible": True,
        "creado_en": "2026-05-22T10:00:00Z",
    }
    base.update(overrides)
    return base


class FakeTransport:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url, headers, body))
        return self.response


def client_for(response, token="abc"):
    transport = FakeTransport(response)
    return EcoMarketClient("https://api.ecomarket.local/v1", token=token, transport=transport), transport


def test_validate_product_accepts_valid_product():
    assert validate_product(producto())["id"] == 1


def test_validate_product_rejects_missing_field():
    with pytest.raises(ValidationError):
        validate_product({"id": 1})


def test_validate_product_rejects_negative_price():
    with pytest.raises(ValidationError):
        validate_product(producto(precio=-1))


def test_validate_product_rejects_unknown_category():
    with pytest.raises(ValidationError):
        validate_product(producto(categoria="electronica"))


def test_listar_productos_returns_validated_list():
    client, _ = client_for(Response(200, [producto()]))
    assert len(client.listar_productos()) == 1


def test_listar_productos_adds_filters():
    client, transport = client_for(Response(200, [producto()]))
    client.listar_productos(categoria="miel", productor_id=7)
    assert transport.calls[0][1].endswith("/productos?categoria=miel&productor_id=7")


def test_listar_productos_rejects_invalid_filter_category():
    client, _ = client_for(Response(200, []))
    with pytest.raises(ValidationError):
        client.listar_productos(categoria="ropa")


def test_listar_productos_rejects_non_list_response():
    client, _ = client_for(Response(200, producto()))
    with pytest.raises(ValidationError):
        client.listar_productos()


def test_crear_producto_uses_post_and_auth_header():
    client, transport = client_for(Response(201, producto(id=2)))
    result = client.crear_producto({"nombre": "Cafe", "descripcion": "250g", "precio": 90, "categoria": "conservas", "productor_id": 4})
    assert result["id"] == 2
    assert transport.calls[0][0] == "POST"
    assert transport.calls[0][2]["Authorization"] == "Bearer abc"


def test_crear_producto_rejects_missing_required_input():
    client, _ = client_for(Response(201, producto()))
    with pytest.raises(ValidationError):
        client.crear_producto({"nombre": "Cafe"})


def test_crear_producto_requires_token():
    client, _ = client_for(Response(201, producto()), token=None)
    with pytest.raises(UnauthorizedError):
        client.crear_producto({"nombre": "Cafe", "descripcion": "250g", "precio": 90, "categoria": "conservas", "productor_id": 4})


def test_obtener_producto_uses_safe_id():
    client, transport = client_for(Response(200, producto()))
    client.obtener_producto(10)
    assert transport.calls[0][1].endswith("/productos/10")


def test_obtener_producto_rejects_negative_id():
    client, _ = client_for(Response(200, producto()))
    with pytest.raises(ValidationError):
        client.obtener_producto(-1)


def test_obtener_producto_raises_not_found():
    client, _ = client_for(Response(404, {"mensaje": "no existe"}))
    with pytest.raises(NotFoundError):
        client.obtener_producto(99)


def test_actualizar_producto_total_uses_put():
    client, transport = client_for(Response(200, producto(nombre="Nuevo")))
    client.actualizar_producto_total(1, {"nombre": "Nuevo", "descripcion": "x", "precio": 10, "categoria": "miel", "productor_id": 7})
    assert transport.calls[0][0] == "PUT"


def test_actualizar_producto_parcial_uses_patch():
    client, transport = client_for(Response(200, producto(precio=80)))
    client.actualizar_producto_parcial(1, {"precio": 80})
    assert transport.calls[0][0] == "PATCH"


def test_actualizar_producto_parcial_rejects_empty_body():
    client, _ = client_for(Response(200, producto()))
    with pytest.raises(ValidationError):
        client.actualizar_producto_parcial(1, {})


def test_eliminar_producto_returns_true_on_204():
    client, transport = client_for(Response(204))
    assert client.eliminar_producto(1) is True
    assert transport.calls[0][0] == "DELETE"


def test_conflict_status_raises_conflict_error():
    client, _ = client_for(Response(409, {"mensaje": "duplicado"}))
    with pytest.raises(ConflictError):
        client.crear_producto({"nombre": "Cafe", "descripcion": "250g", "precio": 90, "categoria": "conservas", "productor_id": 4})


def test_unexpected_status_raises_api_error():
    client, _ = client_for(Response(500, {"mensaje": "fallo"}))
    with pytest.raises(ApiError):
        client.obtener_producto(1)


def test_rejects_non_json_success_response():
    client, _ = client_for(Response(200, "<html>Error</html>", "text/html"))
    with pytest.raises(ValidationError):
        client.obtener_producto(1)
