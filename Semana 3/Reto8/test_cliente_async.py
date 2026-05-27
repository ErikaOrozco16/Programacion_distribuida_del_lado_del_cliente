"""
test_cliente_async.py
Reto IA 8 — Diseñador de Suite de Pruebas Asíncronas
Semana 3: Programación Asíncrona y Concurrencia en el Cliente

Suite de 22 pruebas usando pytest + pytest-asyncio + aioresponses.
NO necesita servidor real; todas las respuestas HTTP son simuladas.

Ejecutar:
    pytest test_cliente_async.py -v
    pytest test_cliente_async.py -v --tb=short

Dependencias:
    pip install pytest pytest-asyncio aioresponses
"""

import sys
import os

# Agregar el directorio Reto3 al path para importar el cliente
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Reto3'))

from cliente_async_ecomarket import (
    listar_productos,
    obtener_producto,
    crear_producto,
    actualizar_producto_total,
    actualizar_producto_parcial,
    eliminar_producto,
    obtener_categorias,
    obtener_perfil,
    cargar_dashboard,
    crear_multiples_productos,
    ValidationError,
    ServerError,
)

import pytest
import asyncio
import aiohttp
from aioresponses import aioresponses

# ──────────────────────────────────────────────────────────────────────────────
# Datos de prueba compartidos (fixtures de datos, no de pytest)
# ──────────────────────────────────────────────────────────────────────────────

BASE_URL = "http://localhost:3000/api/"

# Producto completo con todos los campos del modelo EcoMarket
PRODUCTO_MOCK = {
    "id": 1,
    "nombre": "Aguacate",
    "descripcion": "Aguacate Hass fresco de temporada",
    "precio": 25.0,
    "categoria": "Frutas",
    "stock": 100,
}

LISTA_MOCK = [PRODUCTO_MOCK]

CATEGORIAS_MOCK = ["Frutas", "Verduras", "Lacteos"]

PERFIL_MOCK = {
    "id": 1,
    "nombre": "Ana Lopez",
    "email": "ana@ecomarket.mx",
    "rol": "admin",
}


# ══════════════════════════════════════════════════════════════════════════════
# CATEGORÍA 1 — Equivalencia Funcional (5 tests)
#
# Verifican que cada función async retorna exactamente los mismos datos que
# la versión síncrona equivalente, sin efectos secundarios inesperados.
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_listar_productos_retorna_lista():
    """
    GET /api/productos → la función debe retornar una lista de dicts.

    Caso feliz: el servidor responde 200 con LISTA_MOCK.
    Verificamos tipo (list) y que contiene exactamente 1 elemento.
    """
    with aioresponses() as m:
        # Registrar el mock: GET /productos → 200 + JSON body
        m.get(
            f"{BASE_URL}productos",
            status=200,
            payload=LISTA_MOCK,
        )

        async with aiohttp.ClientSession() as session:
            result = await listar_productos(session)

        # Assertions
        assert isinstance(result, list), "listar_productos debe retornar una lista"
        assert len(result) == 1, "El resultado debe tener 1 elemento"
        assert result[0]["nombre"] == "Aguacate"


@pytest.mark.asyncio
async def test_obtener_producto_retorna_dict_correcto():
    """
    GET /api/productos/1 → retorna el dict del producto con id==1.

    Verificamos que el dict contiene los campos esperados y que el id
    coincide con el solicitado.
    """
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}productos/1",
            status=200,
            payload=PRODUCTO_MOCK,
        )

        async with aiohttp.ClientSession() as session:
            result = await obtener_producto(session, 1)

        assert isinstance(result, dict), "obtener_producto debe retornar un dict"
        assert result["id"] == 1, "El id del producto debe ser 1"
        assert result["nombre"] == "Aguacate"


@pytest.mark.asyncio
async def test_crear_producto_retorna_creado():
    """
    POST /api/productos → retorna el dict del producto recién creado (con id asignado).

    El servidor responde 201 Created con el body del producto.
    Verificamos que el resultado incluye la clave 'id'.
    """
    nuevo_producto = {
        "nombre": "Tomate",
        "descripcion": "Tomate cherry orgánico",
        "precio": 18.5,
        "categoria": "Verduras",
        "stock": 200,
    }

    with aioresponses() as m:
        m.post(
            f"{BASE_URL}productos",
            status=201,
            payload=PRODUCTO_MOCK,  # el servidor asigna id=1
        )

        async with aiohttp.ClientSession() as session:
            result = await crear_producto(session, nuevo_producto)

        assert isinstance(result, dict), "crear_producto debe retornar un dict"
        assert "id" in result, "El producto creado debe tener campo 'id'"


@pytest.mark.asyncio
async def test_error_404_levanta_validation_error():
    """
    GET /api/productos/999 con status 404 → debe lanzar ValidationError.

    El cliente no debe retornar None ni un dict vacío; debe propagar
    ValidationError para que el llamador decida cómo manejarlo.
    """
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}productos/999",
            status=404,
            payload={"error": "Producto no encontrado"},
        )

        async with aiohttp.ClientSession() as session:
            with pytest.raises(ValidationError):
                await obtener_producto(session, 999)


@pytest.mark.asyncio
async def test_error_500_levanta_server_error():
    """
    GET /api/productos con status 500 → debe lanzar ServerError.

    Distinguimos ServerError (fallo del servidor) de ValidationError
    (error del cliente) para que el llamador pueda reintentar si es 5xx.
    """
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}productos",
            status=500,
            payload={"error": "Internal Server Error"},
        )

        async with aiohttp.ClientSession() as session:
            with pytest.raises(ServerError):
                await listar_productos(session)


# ══════════════════════════════════════════════════════════════════════════════
# CATEGORÍA 2 — Concurrencia Correcta (5 tests)
#
# Verifican que gather(), Semaphore() y las funciones de coordinación
# (cargar_dashboard, crear_multiples_productos) funcionan correctamente.
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_obtener_categorias_retorna_lista():
    """
    GET /api/categorias → retorna una lista de strings/dicts.

    Verifica que el endpoint de categorías es compatible con el contrato
    del cliente (siempre retorna una lista).
    """
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}categorias",
            status=200,
            payload=CATEGORIAS_MOCK,
        )

        async with aiohttp.ClientSession() as session:
            result = await obtener_categorias(session)

        assert isinstance(result, list), "obtener_categorias debe retornar una lista"
        assert len(result) == 3


@pytest.mark.asyncio
async def test_obtener_perfil_retorna_dict():
    """
    GET /api/perfil → retorna un dict con al menos la clave 'nombre'.

    El perfil es un recurso protegido; verificamos que el cliente
    maneja correctamente la respuesta 200.
    """
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}perfil",
            status=200,
            payload=PERFIL_MOCK,
        )

        async with aiohttp.ClientSession() as session:
            result = await obtener_perfil(session)

        assert isinstance(result, dict), "obtener_perfil debe retornar un dict"
        assert "nombre" in result, "El perfil debe incluir la clave 'nombre'"
        assert result["nombre"] == "Ana Lopez"


@pytest.mark.asyncio
async def test_cargar_dashboard_retorna_estructura_correcta():
    """
    cargar_dashboard() lanza 3 peticiones en paralelo y retorna:
      {"datos": {...}, "errores": {...}}

    Cuando todas tienen éxito, 'errores' debe estar vacío y 'datos'
    debe contener los 3 endpoints: productos, categorias, perfil.
    """
    with aioresponses() as m:
        # Los 3 endpoints que cargar_dashboard() llama internamente
        m.get(f"{BASE_URL}productos", status=200, payload=LISTA_MOCK)
        m.get(f"{BASE_URL}categorias", status=200, payload=CATEGORIAS_MOCK)
        m.get(f"{BASE_URL}perfil", status=200, payload=PERFIL_MOCK)

        result = await cargar_dashboard()

    # La estructura retornada siempre tiene las dos claves
    assert "datos" in result, "cargar_dashboard debe retornar clave 'datos'"
    assert "errores" in result, "cargar_dashboard debe retornar clave 'errores'"
    # Todas tuvieron éxito → sin errores
    assert len(result["errores"]) == 0
    # Los 3 datasets presentes
    assert "productos" in result["datos"]
    assert "categorias" in result["datos"]
    assert "perfil" in result["datos"]


@pytest.mark.asyncio
async def test_cargar_dashboard_completa_aunque_una_falle():
    """
    cargar_dashboard() con return_exceptions=True: si /productos devuelve 500,
    las otras 2 peticiones (/categorias, /perfil) deben completarse igualmente.

    result["errores"] debe tener exactamente 1 entrada.
    """
    with aioresponses() as m:
        # productos falla con 500
        m.get(f"{BASE_URL}productos", status=500, payload={"error": "boom"})
        # las otras dos tienen éxito
        m.get(f"{BASE_URL}categorias", status=200, payload=CATEGORIAS_MOCK)
        m.get(f"{BASE_URL}perfil", status=200, payload=PERFIL_MOCK)

        result = await cargar_dashboard()

    # El dashboard no lanza excepción aunque una falle
    assert "errores" in result
    assert len(result["errores"]) == 1, "Solo 1 endpoint falló; debe haber 1 error"
    assert "productos" in result["errores"]
    # Las otras dos siguen en datos
    assert "categorias" in result["datos"]
    assert "perfil" in result["datos"]


@pytest.mark.asyncio
async def test_crear_multiples_5_productos_exitosos():
    """
    crear_multiples_productos(lista) con 5 productos que todos devuelven 201.
    Debe retornar (creados=5, fallidos=0).

    El Semaphore(5) limita la concurrencia a 5 simultáneas; con exactamente
    5 elementos, todas deben completarse en el primer "lote".
    """
    lista_de_5 = [
        {"nombre": f"Producto {i}", "precio": 10.0 * i,
         "categoria": "Frutas", "stock": 50}
        for i in range(1, 6)
    ]

    with aioresponses() as m:
        # Registrar 5 respuestas POST exitosas (aioresponses las consume en orden)
        for i in range(5):
            m.post(
                f"{BASE_URL}productos",
                status=201,
                payload={**PRODUCTO_MOCK, "id": i + 1, "nombre": f"Producto {i+1}"},
            )

        creados, fallidos = await crear_multiples_productos(lista_de_5)

    assert len(creados) == 5, "Los 5 productos deben crearse correctamente"
    assert len(fallidos) == 0, "No debe haber productos fallidos"


# ══════════════════════════════════════════════════════════════════════════════
# CATEGORÍA 3 — Timeouts y Cancelación (5 tests)
#
# Verifican el comportamiento correcto de las operaciones de escritura
# (DELETE, PATCH, PUT) y casos con respuestas especiales.
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_eliminar_producto_exitoso():
    """
    DELETE /api/productos/1 → 200 con mensaje de confirmación.

    Verifica que eliminar_producto retorna el dict de confirmación
    y no lanza ninguna excepción.
    """
    with aioresponses() as m:
        m.delete(
            f"{BASE_URL}productos/1",
            status=200,
            payload={"mensaje": "Producto eliminado correctamente", "id": 1},
        )

        async with aiohttp.ClientSession() as session:
            result = await eliminar_producto(session, 1)

        assert result is not None, "eliminar_producto no debe retornar None"
        assert isinstance(result, dict), "eliminar_producto debe retornar un dict"


@pytest.mark.asyncio
async def test_actualizar_parcial_exitoso():
    """
    PATCH /api/productos/1 → actualiza solo el precio y retorna el producto.

    Verifica que actualizar_producto_parcial retorna el dict actualizado
    y que el 'id' coincide con el solicitado.
    """
    campos_a_cambiar = {"precio": 30.0}
    producto_actualizado = {**PRODUCTO_MOCK, "precio": 30.0}

    with aioresponses() as m:
        m.patch(
            f"{BASE_URL}productos/1",
            status=200,
            payload=producto_actualizado,
        )

        async with aiohttp.ClientSession() as session:
            result = await actualizar_producto_parcial(session, 1, campos_a_cambiar)

        assert result["id"] == 1
        assert result["precio"] == 30.0


@pytest.mark.asyncio
async def test_actualizar_total_exitoso():
    """
    PUT /api/productos/1 → reemplaza el producto completo y retorna el resultado.

    PUT semántica REST: el body contiene el recurso completo.
    El servidor retorna el producto tal como quedó almacenado.
    """
    producto_completo = {
        "nombre": "Aguacate Premium",
        "descripcion": "Aguacate Hass orgánico de primera calidad",
        "precio": 35.0,
        "categoria": "Frutas",
        "stock": 80,
    }
    respuesta_servidor = {**producto_completo, "id": 1}

    with aioresponses() as m:
        m.put(
            f"{BASE_URL}productos/1",
            status=200,
            payload=respuesta_servidor,
        )

        async with aiohttp.ClientSession() as session:
            result = await actualizar_producto_total(session, 1, producto_completo)

        assert isinstance(result, dict)
        assert result["id"] == 1
        assert result["nombre"] == "Aguacate Premium"


@pytest.mark.asyncio
async def test_listar_con_categoria_filtra_correctamente():
    """
    GET /api/productos?categoria=Frutas → debe funcionar sin errores.

    Verifica que listar_productos acepta el parámetro opcional 'categoria'
    y lo pasa correctamente como query param (no en el path).
    El mock acepta cualquier URL que empiece con /productos (passthrough=False).
    """
    with aioresponses() as m:
        # aioresponses intercepta la URL con o sin query params por defecto
        m.get(
            f"{BASE_URL}productos",
            status=200,
            payload=LISTA_MOCK,
        )

        async with aiohttp.ClientSession() as session:
            result = await listar_productos(session, categoria="Frutas")

        # No debe lanzar excepción y debe retornar la lista mockeada
        assert isinstance(result, list)
        assert len(result) == 1


@pytest.mark.asyncio
async def test_respuesta_lista_vacia_es_valida():
    """
    GET /api/productos → el servidor retorna [] (sin productos).

    Una lista vacía es un estado válido (catálogo sin productos).
    La función debe retornar [] y no lanzar excepción.
    """
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}productos",
            status=200,
            payload=[],
        )

        async with aiohttp.ClientSession() as session:
            result = await listar_productos(session)

        assert result == [], "Una lista vacía es una respuesta válida"
        assert isinstance(result, list)


# ══════════════════════════════════════════════════════════════════════════════
# CATEGORÍA 4 — Edge Cases de Concurrencia (5 tests)
#
# Verifican comportamiento en situaciones límite o anómalas:
# todos fallan, algunos fallan, campos completos, errores específicos.
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_todas_dashboard_fallan_no_crash():
    """
    cargar_dashboard() cuando los 3 endpoints retornan 500.

    El dashboard NO debe lanzar excepción; en cambio, debe retornar
    {"datos": {}, "errores": {todos los 3}}.
    """
    with aioresponses() as m:
        m.get(f"{BASE_URL}productos", status=500, payload={"error": "down"})
        m.get(f"{BASE_URL}categorias", status=500, payload={"error": "down"})
        m.get(f"{BASE_URL}perfil", status=500, payload={"error": "down"})

        # No debe lanzar excepción
        result = await cargar_dashboard()

    assert "errores" in result
    assert len(result["errores"]) == 3, "Los 3 endpoints fallaron; deben registrarse 3 errores"
    assert len(result["datos"]) == 0, "No hay datos exitosos"


@pytest.mark.asyncio
async def test_crear_multiples_algunos_fallan():
    """
    crear_multiples_productos con 5 productos: 3 con éxito (201), 2 con error (400).

    Verifica el manejo de errores parciales con Semaphore:
      - creados = 3
      - fallidos = 2 (cada uno es una instancia de ValidationError)
    """
    lista_de_5 = [
        {"nombre": f"Producto {i}", "precio": 10.0, "categoria": "Frutas", "stock": 10}
        for i in range(5)
    ]

    with aioresponses() as m:
        # 3 exitosos
        for i in range(3):
            m.post(
                f"{BASE_URL}productos",
                status=201,
                payload={**PRODUCTO_MOCK, "id": i + 10},
            )
        # 2 fallidos (400 Bad Request → ValidationError)
        for _ in range(2):
            m.post(
                f"{BASE_URL}productos",
                status=400,
                payload={"error": "Datos inválidos"},
            )

        creados, fallidos = await crear_multiples_productos(lista_de_5)

    assert len(creados) == 3, "Deben crearse exactamente 3 productos"
    assert len(fallidos) == 2, "Deben fallar exactamente 2 productos"
    # Los fallidos deben ser excepciones, no None
    for exc in fallidos:
        assert isinstance(exc, Exception)


@pytest.mark.asyncio
async def test_product_tiene_todos_los_campos():
    """
    El dict retornado por obtener_producto debe contener los 6 campos del modelo:
    id, nombre, descripcion, precio, categoria, stock.

    Verifica que el cliente no filtra ni transforma el response JSON.
    """
    producto_completo = {
        "id": 7,
        "nombre": "Zanahoria",
        "descripcion": "Zanahoria baby orgánica",
        "precio": 12.0,
        "categoria": "Verduras",
        "stock": 500,
    }

    with aioresponses() as m:
        m.get(
            f"{BASE_URL}productos/7",
            status=200,
            payload=producto_completo,
        )

        async with aiohttp.ClientSession() as session:
            result = await obtener_producto(session, 7)

    campos_requeridos = {"id", "nombre", "descripcion", "precio", "categoria", "stock"}
    assert campos_requeridos.issubset(result.keys()), (
        f"Faltan campos: {campos_requeridos - result.keys()}"
    )


@pytest.mark.asyncio
async def test_error_mensaje_incluye_status_code():
    """
    GET /api/productos con status 503 → debe lanzar ServerError.

    503 Service Unavailable es un error 5xx → ServerError.
    El mensaje de la excepción debe contener información útil para el caller.
    """
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}productos",
            status=503,
            payload={"error": "Service Unavailable"},
        )

        async with aiohttp.ClientSession() as session:
            with pytest.raises(ServerError) as exc_info:
                await listar_productos(session)

        # La excepción debe ser de tipo ServerError (5xx)
        assert isinstance(exc_info.value, ServerError)


@pytest.mark.asyncio
async def test_eliminar_producto_no_existente_levanta_error():
    """
    DELETE /api/productos/999 con status 404 → debe lanzar ValidationError.

    Intentar eliminar un producto que no existe es un error del cliente (4xx),
    no del servidor (5xx). El cliente debe lanzar ValidationError.
    """
    with aioresponses() as m:
        m.delete(
            f"{BASE_URL}productos/999",
            status=404,
            payload={"error": "Producto con id=999 no encontrado"},
        )

        async with aiohttp.ClientSession() as session:
            with pytest.raises(ValidationError):
                await eliminar_producto(session, 999)


# ══════════════════════════════════════════════════════════════════════════════
# CATEGORÍA 5 — Tests Propios (2 tests)
#
# Casos adicionales que los tests anteriores no cubrieron directamente.
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_crear_multiples_productos_lista_vacia():
    """
    Test propio 1: crear_multiples_productos([]) con lista vacía.

    Cuando se pasa una lista vacía, la función no debe hacer ninguna
    petición HTTP y debe retornar (creados=[], fallidos=[]) inmediatamente.
    """
    # No necesitamos registrar ningún mock porque no debe haber peticiones
    creados, fallidos = await crear_multiples_productos([])

    assert creados == [], "Con lista vacía, creados debe ser []"
    assert fallidos == [], "Con lista vacía, fallidos debe ser []"


@pytest.mark.asyncio
async def test_cargar_dashboard_todas_exitosas():
    """
    Test propio 2: cargar_dashboard() con los 3 endpoints exitosos.

    Verifica de forma más estricta que, cuando todo va bien:
      - len(errores) == 0
      - len(datos) >= 3 (al menos los 3 datasets del dashboard)
      - los datos de cada endpoint son del tipo correcto
    """
    with aioresponses() as m:
        m.get(f"{BASE_URL}productos", status=200, payload=LISTA_MOCK)
        m.get(f"{BASE_URL}categorias", status=200, payload=CATEGORIAS_MOCK)
        m.get(f"{BASE_URL}perfil", status=200, payload=PERFIL_MOCK)

        result = await cargar_dashboard()

    errores = result["errores"]
    datos = result["datos"]

    assert len(errores) == 0, "No debe haber errores cuando todos los endpoints responden 200"
    assert len(datos) >= 3, "Debe haber al menos 3 datasets en datos"

    # Verificar tipos de cada dataset
    assert isinstance(datos["productos"], list), "productos debe ser lista"
    assert isinstance(datos["categorias"], list), "categorias debe ser lista"
    assert isinstance(datos["perfil"], dict), "perfil debe ser dict"
