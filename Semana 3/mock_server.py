"""
mock_server.py — Servidor simulado de la API EcoMarket
=======================================================
Implementa un servidor HTTP local con aiohttp que replica el
comportamiento de la API REST de EcoMarket. Útil para desarrollo
y pruebas sin necesidad de un backend real.

Endpoints implementados
-----------------------
  GET    /api/productos
  POST   /api/productos
  GET    /api/productos/{id}
  PUT    /api/productos/{id}
  PATCH  /api/productos/{id}
  DELETE /api/productos/{id}
  GET    /api/categorias
  GET    /api/perfil
  GET    /api/notificaciones

Parámetro especial
------------------
  ?delay_ms=<n>   Añade n milisegundos de latencia simulada a la respuesta.

Uso
---
  python mock_server.py              # sin latencia
  python mock_server.py --delay 200  # 200 ms de latencia en cada petición

Semana 3 — Programación del lado del cliente
"""

import argparse
import asyncio
import json
import logging
import sys
from copy import deepcopy
from datetime import datetime, timezone

from aiohttp import web

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("mock_server")

# ---------------------------------------------------------------------------
# Base de datos en memoria
# ---------------------------------------------------------------------------

_NEXT_ID = 6  # contador global para nuevos IDs

PRODUCTOS_DB: dict[int, dict] = {
    1: {
        "id": 1,
        "nombre": "Laptop Ultradelgada",
        "descripcion": "Laptop de 14 pulgadas con procesador i7 y 16 GB RAM",
        "precio": 1299.99,
        "categoria": "electronica",
        "stock": 15,
    },
    2: {
        "id": 2,
        "nombre": "Camisa de Algodón",
        "descripcion": "Camisa casual 100% algodón, varios colores",
        "precio": 24.99,
        "categoria": "ropa",
        "stock": 200,
    },
    3: {
        "id": 3,
        "nombre": "Aceite de Oliva Extra Virgen",
        "descripcion": "Botella 500 ml, primera prensada en frío",
        "precio": 12.50,
        "categoria": "alimentos",
        "stock": 80,
    },
    4: {
        "id": 4,
        "nombre": "Silla Ergonómica",
        "descripcion": "Silla de oficina con soporte lumbar ajustable",
        "precio": 349.00,
        "categoria": "hogar",
        "stock": 25,
    },
    5: {
        "id": 5,
        "nombre": "Balón de Fútbol",
        "descripcion": "Balón oficial FIFA talla 5",
        "precio": 49.99,
        "categoria": "deportes",
        "stock": 60,
    },
}

CATEGORIAS: list[str] = [
    "electronica",
    "ropa",
    "alimentos",
    "hogar",
    "deportes",
    "libros",
    "juguetes",
    "otros",
]

PERFIL: dict = {
    "id": "usr_001",
    "nombre": "Ana García",
    "email": "ana.garcia@ecomarket.com",
    "rol": "administrador",
    "created_at": "2024-01-15T08:00:00Z",
}

NOTIFICACIONES: list[dict] = [
    {
        "id": "notif_001",
        "tipo": "stock_bajo",
        "mensaje": "El producto 'Aceite de Oliva' tiene stock bajo (< 10 unidades).",
        "leida": False,
        "created_at": "2026-05-19T10:00:00Z",
    },
    {
        "id": "notif_002",
        "tipo": "nuevo_pedido",
        "mensaje": "Nuevo pedido #PED-20260519-001 recibido.",
        "leida": False,
        "created_at": "2026-05-19T11:30:00Z",
    },
    {
        "id": "notif_003",
        "tipo": "info",
        "mensaje": "Actualización del sistema programada para esta noche a las 02:00.",
        "leida": True,
        "created_at": "2026-05-18T09:00:00Z",
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DEFAULT_DELAY_MS: int = 0  # se sobreescribe desde CLI


def _json_response(data, *, status: int = 200) -> web.Response:
    """Serializa *data* a JSON y retorna un web.Response con el Content-Type correcto."""
    return web.Response(
        status=status,
        content_type="application/json",
        text=json.dumps(data, ensure_ascii=False, indent=2),
    )


async def _aplicar_latencia(request: web.Request) -> None:
    """
    Aplica latencia simulada.
    Prioridad: query param ?delay_ms=N  →  flag global --delay N  →  0 ms
    """
    delay_str = request.rel_url.query.get("delay_ms")
    if delay_str is not None:
        try:
            delay = int(delay_str)
        except ValueError:
            delay = DEFAULT_DELAY_MS
    else:
        delay = DEFAULT_DELAY_MS

    if delay > 0:
        await asyncio.sleep(delay / 1000)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Middleware de logging
# ---------------------------------------------------------------------------

@web.middleware
async def log_middleware(request: web.Request, handler):
    log.info("→  %s %s", request.method, request.path)
    response = await handler(request)
    log.info("←  %s %s  [%d]", request.method, request.path, response.status)
    return response


# ---------------------------------------------------------------------------
# Handlers — /api/productos
# ---------------------------------------------------------------------------

async def handle_get_productos(request: web.Request) -> web.Response:
    """GET /api/productos — retorna todos los productos."""
    await _aplicar_latencia(request)
    productos = list(PRODUCTOS_DB.values())
    return _json_response({"data": productos, "total": len(productos)})


async def handle_post_producto(request: web.Request) -> web.Response:
    """POST /api/productos — crea un nuevo producto."""
    global _NEXT_ID
    await _aplicar_latencia(request)

    try:
        body = await request.json()
    except Exception:
        return _json_response(
            {"error": "Cuerpo JSON inválido o ausente."}, status=400
        )

    # Validación mínima
    requeridos = ["nombre", "precio", "categoria"]
    faltantes = [c for c in requeridos if c not in body]
    if faltantes:
        return _json_response(
            {"error": f"Campos requeridos faltantes: {faltantes}"}, status=400
        )

    if not isinstance(body["precio"], (int, float)) or body["precio"] <= 0:
        return _json_response(
            {"error": "'precio' debe ser mayor que 0."}, status=400
        )

    nuevo = {
        "id": _NEXT_ID,
        "nombre": str(body["nombre"]).strip(),
        "descripcion": str(body.get("descripcion", "")).strip(),
        "precio": float(body["precio"]),
        "categoria": str(body["categoria"]).strip().lower(),
        "stock": int(body.get("stock", 0)),
        "created_at": _now_iso(),
    }
    PRODUCTOS_DB[_NEXT_ID] = nuevo
    _NEXT_ID += 1

    return _json_response({"data": nuevo, "mensaje": "Producto creado exitosamente."}, status=201)


async def handle_get_producto(request: web.Request) -> web.Response:
    """GET /api/productos/{id} — retorna un producto por ID."""
    await _aplicar_latencia(request)
    try:
        pid = int(request.match_info["id"])
    except ValueError:
        return _json_response({"error": "ID de producto inválido."}, status=400)

    producto = PRODUCTOS_DB.get(pid)
    if producto is None:
        return _json_response(
            {"error": f"Producto con id={pid} no encontrado."}, status=404
        )

    return _json_response({"data": producto})


async def handle_put_producto(request: web.Request) -> web.Response:
    """PUT /api/productos/{id} — reemplaza un producto completo."""
    await _aplicar_latencia(request)
    try:
        pid = int(request.match_info["id"])
    except ValueError:
        return _json_response({"error": "ID de producto inválido."}, status=400)

    if pid not in PRODUCTOS_DB:
        return _json_response(
            {"error": f"Producto con id={pid} no encontrado."}, status=404
        )

    try:
        body = await request.json()
    except Exception:
        return _json_response({"error": "Cuerpo JSON inválido."}, status=400)

    requeridos = ["nombre", "precio", "categoria"]
    faltantes = [c for c in requeridos if c not in body]
    if faltantes:
        return _json_response(
            {"error": f"Campos requeridos faltantes: {faltantes}"}, status=400
        )

    actualizado = {
        "id": pid,
        "nombre": str(body["nombre"]).strip(),
        "descripcion": str(body.get("descripcion", "")).strip(),
        "precio": float(body["precio"]),
        "categoria": str(body["categoria"]).strip().lower(),
        "stock": int(body.get("stock", 0)),
        "updated_at": _now_iso(),
    }
    PRODUCTOS_DB[pid] = actualizado
    return _json_response(
        {"data": actualizado, "mensaje": "Producto actualizado completamente."}
    )


async def handle_patch_producto(request: web.Request) -> web.Response:
    """PATCH /api/productos/{id} — actualiza campos parciales de un producto."""
    await _aplicar_latencia(request)
    try:
        pid = int(request.match_info["id"])
    except ValueError:
        return _json_response({"error": "ID de producto inválido."}, status=400)

    if pid not in PRODUCTOS_DB:
        return _json_response(
            {"error": f"Producto con id={pid} no encontrado."}, status=404
        )

    try:
        body = await request.json()
    except Exception:
        return _json_response({"error": "Cuerpo JSON inválido."}, status=400)

    if not body:
        return _json_response({"error": "No se proporcionaron campos para actualizar."}, status=400)

    producto = deepcopy(PRODUCTOS_DB[pid])
    campos_permitidos = {"nombre", "descripcion", "precio", "categoria", "stock"}

    for campo, valor in body.items():
        if campo in campos_permitidos:
            producto[campo] = valor

    producto["updated_at"] = _now_iso()
    PRODUCTOS_DB[pid] = producto

    return _json_response(
        {"data": producto, "mensaje": "Producto actualizado parcialmente."}
    )


async def handle_delete_producto(request: web.Request) -> web.Response:
    """DELETE /api/productos/{id} — elimina un producto."""
    await _aplicar_latencia(request)
    try:
        pid = int(request.match_info["id"])
    except ValueError:
        return _json_response({"error": "ID de producto inválido."}, status=400)

    if pid not in PRODUCTOS_DB:
        return _json_response(
            {"error": f"Producto con id={pid} no encontrado."}, status=404
        )

    eliminado = PRODUCTOS_DB.pop(pid)
    return _json_response(
        {"mensaje": f"Producto '{eliminado['nombre']}' eliminado.", "data": eliminado}
    )


# ---------------------------------------------------------------------------
# Handlers — /api/categorias, /api/perfil, /api/notificaciones
# ---------------------------------------------------------------------------

async def handle_get_categorias(request: web.Request) -> web.Response:
    """GET /api/categorias — retorna lista de categorías disponibles."""
    await _aplicar_latencia(request)
    return _json_response({"data": CATEGORIAS, "total": len(CATEGORIAS)})


async def handle_get_perfil(request: web.Request) -> web.Response:
    """GET /api/perfil — retorna el perfil del usuario autenticado."""
    await _aplicar_latencia(request)
    return _json_response({"data": PERFIL})


async def handle_get_notificaciones(request: web.Request) -> web.Response:
    """GET /api/notificaciones — retorna las notificaciones del usuario."""
    await _aplicar_latencia(request)
    return _json_response(
        {"data": NOTIFICACIONES, "total": len(NOTIFICACIONES)}
    )


# ---------------------------------------------------------------------------
# Ruta raíz / health-check
# ---------------------------------------------------------------------------

async def handle_root(request: web.Request) -> web.Response:
    return _json_response({
        "servicio": "EcoMarket Mock API",
        "version": "1.0.0",
        "estado": "operativo",
        "timestamp": _now_iso(),
        "endpoints": [
            "GET  /api/productos",
            "POST /api/productos",
            "GET  /api/productos/{id}",
            "PUT  /api/productos/{id}",
            "PATCH /api/productos/{id}",
            "DELETE /api/productos/{id}",
            "GET  /api/categorias",
            "GET  /api/perfil",
            "GET  /api/notificaciones",
        ],
    })


# ---------------------------------------------------------------------------
# Construcción de la aplicación
# ---------------------------------------------------------------------------

def crear_app() -> web.Application:
    """Crea y configura la aplicación aiohttp."""
    app = web.Application(middlewares=[log_middleware])

    app.router.add_get("/", handle_root)
    app.router.add_get("/api/productos", handle_get_productos)
    app.router.add_post("/api/productos", handle_post_producto)
    app.router.add_get("/api/productos/{id}", handle_get_producto)
    app.router.add_put("/api/productos/{id}", handle_put_producto)
    app.router.add_patch("/api/productos/{id}", handle_patch_producto)
    app.router.add_delete("/api/productos/{id}", handle_delete_producto)
    app.router.add_get("/api/categorias", handle_get_categorias)
    app.router.add_get("/api/perfil", handle_get_perfil)
    app.router.add_get("/api/notificaciones", handle_get_notificaciones)

    return app


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Servidor mock de la API EcoMarket (aiohttp)"
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=0,
        metavar="MS",
        help="Latencia simulada en milisegundos para todos los endpoints (default: 0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=3000,
        help="Puerto en el que escucha el servidor (default: 3000)",
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Host en el que escucha el servidor (default: localhost)",
    )
    args = parser.parse_args()

    # Configurar latencia global
    global DEFAULT_DELAY_MS
    DEFAULT_DELAY_MS = args.delay

    app = crear_app()

    log.info("╔══════════════════════════════════════════════╗")
    log.info("║   EcoMarket Mock Server — aiohttp            ║")
    log.info("╠══════════════════════════════════════════════╣")
    log.info("║  URL base : http://%s:%d/api/      ", args.host, args.port)
    log.info("║  Latencia : %d ms por petición              ", DEFAULT_DELAY_MS)
    log.info("║  Productos: %d en memoria                   ", len(PRODUCTOS_DB))
    log.info("║  Ctrl+C para detener                         ║")
    log.info("╚══════════════════════════════════════════════╝")

    web.run_app(app, host=args.host, port=args.port, print=None)


if __name__ == "__main__":
    main()
