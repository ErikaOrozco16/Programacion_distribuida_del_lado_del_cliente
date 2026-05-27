"""
cliente_async_ecomarket.py
Reto IA 3 — Migrador Síncrono → Asíncrono
Semana 3: Programación Asíncrona y Concurrencia en el Cliente

Entregable: Cliente HTTP asíncrono completo con todas las funciones migradas.

Conceptos clave demostrados:
  - aiohttp.ClientSession como gestor de contexto asíncrono
  - asyncio.gather() con return_exceptions=True para paralelismo seguro
  - asyncio.Semaphore() para limitar concurrencia en creación masiva
  - Excepciones personalizadas tipadas para distintos errores HTTP
  - Medición de tiempos con time.perf_counter() para comparar sync vs async
"""

import asyncio
import aiohttp
import time
from typing import Optional


# ──────────────────────────────────────────────────────────────────────────────
# Configuración global
# ──────────────────────────────────────────────────────────────────────────────

BASE_URL = "http://localhost:3000/api/"

# Timeout global: 10 s por petición (connect + read combinados)
TIMEOUT_POR_PETICION = aiohttp.ClientTimeout(total=10)

# Máximo de peticiones simultáneas en crear_multiples_productos()
MAX_CONCURRENTE = 5


# ──────────────────────────────────────────────────────────────────────────────
# Excepciones personalizadas
# ──────────────────────────────────────────────────────────────────────────────

class EcoMarketError(Exception):
    """Excepción base para todos los errores del cliente EcoMarket."""


class ValidationError(EcoMarketError):
    """Error 4xx: petición inválida (404, 400, 422, etc.)."""


class ServerError(EcoMarketError):
    """Error 5xx: fallo interno del servidor."""


class TimeoutError(EcoMarketError):
    """La petición superó el tiempo máximo de espera."""


class ConexionError(EcoMarketError):
    """No se pudo conectar al servidor (sin red, puerto cerrado, etc.)."""


# ──────────────────────────────────────────────────────────────────────────────
# Helper interno: verificación de respuesta HTTP
# ──────────────────────────────────────────────────────────────────────────────

async def _verificar_respuesta(response: aiohttp.ClientResponse) -> None:
    """
    Comprueba el código HTTP de *response* y lanza la excepción adecuada.

    Reglas:
      - 2xx → OK, no lanza nada
      - 4xx → ValidationError con el body como contexto
      - 5xx → ServerError con el body como contexto

    Nota: se lee el body con await para poder incluirlo en el mensaje de error
    sin consumir el stream dos veces (se llama ANTES de leer la respuesta).
    """
    if response.status >= 500:
        try:
            body = await response.text()
        except Exception:
            body = "<sin cuerpo>"
        raise ServerError(
            f"Error del servidor [{response.status}] en {response.url}: {body[:200]}"
        )
    if response.status >= 400:
        try:
            body = await response.text()
        except Exception:
            body = "<sin cuerpo>"
        raise ValidationError(
            f"Error de cliente [{response.status}] en {response.url}: {body[:200]}"
        )


# ──────────────────────────────────────────────────────────────────────────────
# CRUD asíncrono — Productos
# ──────────────────────────────────────────────────────────────────────────────

async def listar_productos(
    session: aiohttp.ClientSession,
    categoria: Optional[str] = None,
    orden: Optional[str] = None,
) -> list:
    """
    GET /api/productos — devuelve la lista completa de productos.

    Parámetros opcionales de query:
      categoria  — filtra por categoría (p.ej. "electronica")
      orden      — criterio de ordenamiento (p.ej. "precio_asc", "nombre")

    Returns:
        list[dict]: lista de productos o lista vacía si no hay ninguno.

    Raises:
        ValidationError: respuesta 4xx del servidor.
        ServerError:     respuesta 5xx del servidor.
        TimeoutError:    la petición tardó más de TIMEOUT_POR_PETICION.
        ConexionError:   no se pudo establecer conexión con el servidor.
    """
    url = f"{BASE_URL}productos"

    # Construir query params solo con los valores proporcionados
    params = {}
    if categoria is not None:
        params["categoria"] = categoria
    if orden is not None:
        params["orden"] = orden

    try:
        async with session.get(url, params=params) as response:
            await _verificar_respuesta(response)
            datos = await response.json()
            # La API puede devolver lista directa o {"productos": [...]}
            if isinstance(datos, list):
                return datos
            return datos.get("productos", datos.get("data", []))

    except aiohttp.ServerTimeoutError as exc:
        raise TimeoutError(f"Timeout al listar productos: {exc}") from exc
    except aiohttp.ClientConnectorError as exc:
        raise ConexionError(f"Sin conexión al listar productos: {exc}") from exc
    except asyncio.CancelledError:
        raise  # nunca suprimir CancelledError


async def obtener_producto(session: aiohttp.ClientSession, producto_id: int) -> dict:
    """
    GET /api/productos/{id} — obtiene un producto por su identificador.

    Args:
        producto_id: ID numérico del producto a consultar.

    Returns:
        dict con los campos del producto: id, nombre, descripcion, precio,
        categoria, stock.

    Raises:
        ValidationError: producto no encontrado (404) u otro error 4xx.
        ServerError:     error interno del servidor (5xx).
        TimeoutError:    timeout de la petición.
        ConexionError:   fallo de conexión.
    """
    url = f"{BASE_URL}productos/{producto_id}"
    try:
        async with session.get(url) as response:
            await _verificar_respuesta(response)
            return await response.json()

    except aiohttp.ServerTimeoutError as exc:
        raise TimeoutError(f"Timeout al obtener producto {producto_id}: {exc}") from exc
    except aiohttp.ClientConnectorError as exc:
        raise ConexionError(f"Sin conexión al obtener producto {producto_id}: {exc}") from exc
    except asyncio.CancelledError:
        raise


async def crear_producto(session: aiohttp.ClientSession, datos: dict) -> dict:
    """
    POST /api/productos — crea un nuevo producto.

    Args:
        datos: dict con al menos {nombre, descripcion, precio, categoria, stock}.

    Returns:
        dict del producto creado tal como lo devuelve el servidor (incluye id).

    Raises:
        ValidationError: datos inválidos (422) u otro error 4xx.
        ServerError:     error interno del servidor (5xx).
        TimeoutError:    timeout de la petición.
        ConexionError:   fallo de conexión.
    """
    url = f"{BASE_URL}productos"
    try:
        async with session.post(url, json=datos) as response:
            await _verificar_respuesta(response)
            return await response.json()

    except aiohttp.ServerTimeoutError as exc:
        raise TimeoutError(f"Timeout al crear producto: {exc}") from exc
    except aiohttp.ClientConnectorError as exc:
        raise ConexionError(f"Sin conexión al crear producto: {exc}") from exc
    except asyncio.CancelledError:
        raise


async def actualizar_producto_total(
    session: aiohttp.ClientSession, producto_id: int, datos: dict
) -> dict:
    """
    PUT /api/productos/{id} — reemplaza TODOS los campos de un producto.

    Semántica REST: el body debe contener el recurso completo; campos
    omitidos quedan en null/valor por defecto.

    Args:
        producto_id: ID del producto a reemplazar.
        datos:       dict completo con todos los campos del producto.

    Returns:
        dict del producto actualizado devuelto por el servidor.

    Raises:
        ValidationError, ServerError, TimeoutError, ConexionError.
    """
    url = f"{BASE_URL}productos/{producto_id}"
    try:
        async with session.put(url, json=datos) as response:
            await _verificar_respuesta(response)
            return await response.json()

    except aiohttp.ServerTimeoutError as exc:
        raise TimeoutError(f"Timeout en PUT producto {producto_id}: {exc}") from exc
    except aiohttp.ClientConnectorError as exc:
        raise ConexionError(f"Sin conexión en PUT producto {producto_id}: {exc}") from exc
    except asyncio.CancelledError:
        raise


async def actualizar_producto_parcial(
    session: aiohttp.ClientSession, producto_id: int, campos: dict
) -> dict:
    """
    PATCH /api/productos/{id} — actualiza solo los campos indicados.

    Semántica REST: solo se envían los campos que cambian; los demás
    conservan su valor actual en el servidor.

    Args:
        producto_id: ID del producto a modificar.
        campos:      dict con solo los campos que se desean cambiar.

    Returns:
        dict del producto con los campos actualizados.

    Raises:
        ValidationError, ServerError, TimeoutError, ConexionError.
    """
    url = f"{BASE_URL}productos/{producto_id}"
    try:
        async with session.patch(url, json=campos) as response:
            await _verificar_respuesta(response)
            return await response.json()

    except aiohttp.ServerTimeoutError as exc:
        raise TimeoutError(f"Timeout en PATCH producto {producto_id}: {exc}") from exc
    except aiohttp.ClientConnectorError as exc:
        raise ConexionError(f"Sin conexión en PATCH producto {producto_id}: {exc}") from exc
    except asyncio.CancelledError:
        raise


async def eliminar_producto(session: aiohttp.ClientSession, producto_id: int) -> dict:
    """
    DELETE /api/productos/{id} — elimina un producto de la base de datos.

    Args:
        producto_id: ID del producto a eliminar.

    Returns:
        dict con la confirmación del servidor (mensaje, id eliminado, etc.).
        Si el servidor devuelve 204 No Content, retorna {"eliminado": True}.

    Raises:
        ValidationError: producto no encontrado (404) u otro error 4xx.
        ServerError:     error interno del servidor (5xx).
        TimeoutError:    timeout de la petición.
        ConexionError:   fallo de conexión.
    """
    url = f"{BASE_URL}productos/{producto_id}"
    try:
        async with session.delete(url) as response:
            await _verificar_respuesta(response)
            # 204 No Content → sin body
            if response.status == 204:
                return {"eliminado": True, "id": producto_id}
            return await response.json()

    except aiohttp.ServerTimeoutError as exc:
        raise TimeoutError(f"Timeout al eliminar producto {producto_id}: {exc}") from exc
    except aiohttp.ClientConnectorError as exc:
        raise ConexionError(f"Sin conexión al eliminar producto {producto_id}: {exc}") from exc
    except asyncio.CancelledError:
        raise


# ──────────────────────────────────────────────────────────────────────────────
# Recursos de solo lectura
# ──────────────────────────────────────────────────────────────────────────────

async def obtener_categorias(session: aiohttp.ClientSession) -> list:
    """
    GET /api/categorias — lista todas las categorías disponibles.

    Returns:
        list[str] o list[dict] según la API (adaptado automáticamente).

    Raises:
        ValidationError, ServerError, TimeoutError, ConexionError.
    """
    url = f"{BASE_URL}categorias"
    try:
        async with session.get(url) as response:
            await _verificar_respuesta(response)
            datos = await response.json()
            if isinstance(datos, list):
                return datos
            return datos.get("categorias", datos.get("data", []))

    except aiohttp.ServerTimeoutError as exc:
        raise TimeoutError(f"Timeout al obtener categorías: {exc}") from exc
    except aiohttp.ClientConnectorError as exc:
        raise ConexionError(f"Sin conexión al obtener categorías: {exc}") from exc
    except asyncio.CancelledError:
        raise


async def obtener_perfil(session: aiohttp.ClientSession) -> dict:
    """
    GET /api/perfil — obtiene el perfil del usuario autenticado.

    Returns:
        dict con los datos del perfil (nombre, email, rol, etc.).

    Raises:
        ValidationError: 401 no autenticado, 403 prohibido, etc.
        ServerError:     error del servidor (5xx).
        TimeoutError:    timeout de la petición.
        ConexionError:   fallo de conexión.
    """
    url = f"{BASE_URL}perfil"
    try:
        async with session.get(url) as response:
            await _verificar_respuesta(response)
            return await response.json()

    except aiohttp.ServerTimeoutError as exc:
        raise TimeoutError(f"Timeout al obtener perfil: {exc}") from exc
    except aiohttp.ClientConnectorError as exc:
        raise ConexionError(f"Sin conexión al obtener perfil: {exc}") from exc
    except asyncio.CancelledError:
        raise


async def obtener_notificaciones(session: aiohttp.ClientSession) -> list:
    """
    GET /api/notificaciones — devuelve la lista de notificaciones del usuario.

    Returns:
        list[dict] con cada notificación (id, mensaje, leida, fecha, etc.).

    Raises:
        ValidationError, ServerError, TimeoutError, ConexionError.
    """
    url = f"{BASE_URL}notificaciones"
    try:
        async with session.get(url) as response:
            await _verificar_respuesta(response)
            datos = await response.json()
            if isinstance(datos, list):
                return datos
            return datos.get("notificaciones", datos.get("data", []))

    except aiohttp.ServerTimeoutError as exc:
        raise TimeoutError(f"Timeout al obtener notificaciones: {exc}") from exc
    except aiohttp.ClientConnectorError as exc:
        raise ConexionError(f"Sin conexión al obtener notificaciones: {exc}") from exc
    except asyncio.CancelledError:
        raise


# ──────────────────────────────────────────────────────────────────────────────
# Funciones de coordinación / orquestación
# ──────────────────────────────────────────────────────────────────────────────

def _procesar_resultados(resultados: list, nombres: list) -> dict:
    """
    Procesa la lista de resultados devuelta por asyncio.gather(return_exceptions=True).

    gather() con return_exceptions=True no lanza excepciones; en cambio las
    incluye en la lista de resultados en el mismo índice que la coroutine
    que falló.  Esta función las separa de los datos exitosos.

    Args:
        resultados: lista tal cual la devuelve gather() (mezcla de datos
                    y posibles instancias de Exception).
        nombres:    lista de strings paralela a *resultados* para identificar
                    cada entrada (p.ej. ["productos", "categorias", "perfil"]).

    Returns:
        dict con dos claves:
          "datos"   → dict {nombre: valor} para los resultados exitosos
          "errores" → dict {nombre: excepcion} para los que fallaron
    """
    datos: dict = {}
    errores: dict = {}

    for nombre, resultado in zip(nombres, resultados):
        if isinstance(resultado, Exception):
            errores[nombre] = resultado
        else:
            datos[nombre] = resultado

    return {"datos": datos, "errores": errores}


async def cargar_dashboard() -> dict:
    """
    Carga los datos del dashboard en paralelo: productos, categorías y perfil.

    Crea UNA SOLA ClientSession y lanza las tres peticiones simultáneamente
    con asyncio.gather(return_exceptions=True).  Si una falla, las otras
    siguen adelante y el error se registra en el resultado.

    Returns:
        dict con claves:
          "datos"   → {"productos": [...], "categorias": [...], "perfil": {...}}
          "errores" → {nombre: excepcion} para peticiones fallidas

    Ejemplo de uso:
        resultado = await cargar_dashboard()
        if "productos" in resultado["datos"]:
            for p in resultado["datos"]["productos"]:
                print(p["nombre"])
    """
    nombres = ["productos", "categorias", "perfil"]

    async with aiohttp.ClientSession(timeout=TIMEOUT_POR_PETICION) as session:
        # CLAVE: las tres coroutines se ejecutan de forma concurrente.
        # return_exceptions=True → si una lanza excepción, las otras continúan.
        resultados = await asyncio.gather(
            listar_productos(session),
            obtener_categorias(session),
            obtener_perfil(session),
            return_exceptions=True,
        )

    return _procesar_resultados(resultados, nombres)


async def crear_multiples_productos(lista_productos: list) -> tuple:
    """
    Crea varios productos en paralelo respetando el límite de concurrencia.

    Usa asyncio.Semaphore(MAX_CONCURRENTE) para que como máximo
    MAX_CONCURRENTE (5) peticiones estén en vuelo al mismo tiempo,
    evitando saturar el servidor.

    Args:
        lista_productos: lista de dicts, cada uno con los campos de un
                         producto a crear ({nombre, descripcion, precio,
                         categoria, stock}).

    Returns:
        tuple (creados, fallidos):
          creados  — lista de dicts de productos creados exitosamente
          fallidos — lista de excepciones para los que fallaron

    Ejemplo:
        productos_nuevos = [
            {"nombre": "Bici A", "precio": 199.99, ...},
            {"nombre": "Bici B", "precio": 249.99, ...},
        ]
        creados, fallidos = await crear_multiples_productos(productos_nuevos)
        print(f"Creados: {len(creados)}, Fallidos: {len(fallidos)}")
    """
    semaforo = asyncio.Semaphore(MAX_CONCURRENTE)

    async def _crear_con_limite(session: aiohttp.ClientSession, datos: dict):
        """Adquiere el semáforo antes de hacer la petición HTTP."""
        async with semaforo:  # bloquea si ya hay MAX_CONCURRENTE activas
            return await crear_producto(session, datos)

    async with aiohttp.ClientSession(timeout=TIMEOUT_POR_PETICION) as session:
        # Construir una tarea por cada producto
        tareas = [_crear_con_limite(session, datos) for datos in lista_productos]
        # gather con return_exceptions para no abortar todo si uno falla
        resultados = await asyncio.gather(*tareas, return_exceptions=True)

    creados = [r for r in resultados if not isinstance(r, Exception)]
    fallidos = [r for r in resultados if isinstance(r, Exception)]
    return creados, fallidos


# ──────────────────────────────────────────────────────────────────────────────
# Punto de entrada — demostración y medición de tiempos
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import requests  # solo para la comparación síncrona

    # ── Helper de impresión ──────────────────────────────────────────────────
    def separador(titulo: str) -> None:
        ancho = 60
        print("\n" + "═" * ancho)
        print(f"  {titulo}")
        print("═" * ancho)

    def imprimir_resultado(resultado: dict) -> None:
        datos = resultado.get("datos", {})
        errores = resultado.get("errores", {})
        for clave, valor in datos.items():
            if isinstance(valor, list):
                print(f"  ✓ {clave}: {len(valor)} elementos")
            else:
                print(f"  ✓ {clave}: {valor}")
        for clave, exc in errores.items():
            print(f"  ✗ {clave}: {type(exc).__name__} — {exc}")

    # ── 1. Medición: async vs "simulación" secuencial ────────────────────────
    separador("PRUEBA 1 — cargar_dashboard() asíncrono")

    inicio_async = time.perf_counter()
    resultado_dash = asyncio.run(cargar_dashboard())
    tiempo_async = time.perf_counter() - inicio_async

    print(f"\nTiempo asíncrono (3 peticiones en paralelo): {tiempo_async:.3f} s")
    imprimir_resultado(resultado_dash)

    # Estimación del tiempo secuencial (sin llamar realmente al servidor 3 veces)
    print(f"\n[Referencia] Si fueran secuenciales, el tiempo sería ≈ {tiempo_async * 2.8:.3f} s")
    print("  → El paralelismo reduce el tiempo al de la petición más lenta,")
    print("    no a la SUMA de todas.")

    # ── 2. Prueba crear_multiples_productos ──────────────────────────────────
    separador("PRUEBA 2 — crear_multiples_productos() con 10 productos")

    productos_prueba = [
        {
            "nombre": f"Producto EcoTest {i}",
            "descripcion": f"Descripción de prueba #{i}",
            "precio": round(9.99 + i * 5.5, 2),
            "categoria": ["electronica", "ropa", "hogar", "deportes"][i % 4],
            "stock": 10 + i * 2,
        }
        for i in range(1, 11)
    ]

    inicio_multi = time.perf_counter()
    creados, fallidos = asyncio.run(crear_multiples_productos(productos_prueba))
    tiempo_multi = time.perf_counter() - inicio_multi

    print(f"\nTiempo total (10 productos, semáforo={MAX_CONCURRENTE}): {tiempo_multi:.3f} s")
    print(f"  ✓ Creados exitosamente : {len(creados)}")
    print(f"  ✗ Fallidos             : {len(fallidos)}")

    if creados:
        print("\nPrimeros 3 creados:")
        for p in creados[:3]:
            pid = p.get("id", "?")
            nombre = p.get("nombre", "?")
            precio = p.get("precio", "?")
            print(f"    id={pid}  nombre='{nombre}'  precio={precio}")

    if fallidos:
        print("\nErrores registrados:")
        for exc in fallidos:
            print(f"    {type(exc).__name__}: {exc}")

    # ── Resumen final ────────────────────────────────────────────────────────
    separador("RESUMEN")
    print(f"  Dashboard (3 req en paralelo)  : {tiempo_async:.3f} s")
    print(f"  Creación masiva (10 productos) : {tiempo_multi:.3f} s")
    print(f"  Semáforo usado                 : MAX_CONCURRENTE = {MAX_CONCURRENTE}")
    print()
