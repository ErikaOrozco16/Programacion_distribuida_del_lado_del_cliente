"""
comparacion_modelos.py — Reto 1: Comparación de modelos de concurrencia
========================================================================
Demuestra y MIDE tres paradigmas de programación concurrente en Python:

  1. CALLBACKS   — concurrent.futures + add_done_callback
  2. FUTURES     — concurrent.futures + as_completed (forma explícita)
  3. ASYNC/AWAIT — asyncio + aiohttp / asyncio.gather()

Todos los escenarios realizan simultáneamente:
  • GET /api/productos    (latencia simulada: 300 ms)
  • GET /api/categorias   (latencia simulada: 100 ms, con timeout que se maneja)
  • GET /api/perfil       (latencia simulada: 200 ms)

El script es STANDALONE: NO necesita el servidor real. Usa funciones
locales con time.sleep() / asyncio.sleep() para simular la red.

Al final imprime una tabla comparativa de los tres modelos.

Semana 3 — Programación del lado del cliente
"""

import asyncio
import concurrent.futures
import time
from typing import Any

# ---------------------------------------------------------------------------
# Configuración de latencias simuladas (en segundos)
# ---------------------------------------------------------------------------

LATENCIA_PRODUCTOS   = 0.30   # 300 ms
LATENCIA_CATEGORIAS  = 0.10   # 100 ms
LATENCIA_PERFIL      = 0.20   # 200 ms
TIMEOUT_CATEGORIAS   = 5.00   # timeout generoso — no falla en este demo

# Datos de respuesta simulados
_MOCK_PRODUCTOS = [
    {"id": 1, "nombre": "Laptop", "precio": 1299.99, "categoria": "electronica"},
    {"id": 2, "nombre": "Camisa", "precio": 24.99,   "categoria": "ropa"},
    {"id": 3, "nombre": "Aceite", "precio": 12.50,   "categoria": "alimentos"},
]
_MOCK_CATEGORIAS = ["electronica", "ropa", "alimentos", "hogar", "deportes"]
_MOCK_PERFIL = {"id": "usr_001", "nombre": "Ana García", "rol": "administrador"}


# ===========================================================================
# FUNCIONES SÍNCRONAS de simulación de red (usadas por Callbacks y Futures)
# ===========================================================================

def fetch_productos_sync() -> dict:
    """Simula GET /api/productos con latencia síncrona."""
    time.sleep(LATENCIA_PRODUCTOS)
    return {"endpoint": "/api/productos", "data": _MOCK_PRODUCTOS, "total": len(_MOCK_PRODUCTOS)}


def fetch_categorias_sync() -> dict:
    """Simula GET /api/categorias con latencia síncrona."""
    time.sleep(LATENCIA_CATEGORIAS)
    # Simular un posible error de timeout (deshabilitado aquí para que siempre funcione)
    return {"endpoint": "/api/categorias", "data": _MOCK_CATEGORIAS}


def fetch_perfil_sync() -> dict:
    """Simula GET /api/perfil con latencia síncrona."""
    time.sleep(LATENCIA_PERFIL)
    return {"endpoint": "/api/perfil", "data": _MOCK_PERFIL}


# ===========================================================================
# MODELO 1 — CALLBACKS con ThreadPoolExecutor
# ===========================================================================

def modelo_callbacks(iteracion: int) -> tuple[float, dict]:
    """
    Ejecuta las 3 peticiones en hilos y usa add_done_callback para procesar
    los resultados a medida que cada hilo termina.

    El callback se ejecuta en el hilo del executor (o del hilo principal
    dependiendo de la implementación), no en el event loop.

    Retorna (tiempo_total, resultados).
    """
    resultados: dict[str, Any] = {}
    errores:    dict[str, str]  = {}

    # Un Event para sincronizar — nos avisa cuándo todos terminaron
    completados = 0
    lock = concurrent.futures.thread._python_thread_local if False else None  # solo para ilustrar

    inicio = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        tareas = {
            "productos":  executor.submit(fetch_productos_sync),
            "categorias": executor.submit(fetch_categorias_sync),
            "perfil":     executor.submit(fetch_perfil_sync),
        }

        def hacer_callback(nombre: str):
            """Fábrica de callbacks — captura el nombre del endpoint."""
            def _callback(future: concurrent.futures.Future):
                try:
                    resultado = future.result()
                    resultados[nombre] = resultado
                except Exception as exc:
                    errores[nombre] = str(exc)
                    resultados[nombre] = None
            return _callback

        # Registrar callbacks ANTES de que terminen los futures
        for nombre, fut in tareas.items():
            fut.add_done_callback(hacer_callback(nombre))

        # Esperar a que todos los futures terminen (los callbacks se ejecutan automáticamente)
        concurrent.futures.wait(tareas.values())

    tiempo_total = time.time() - inicio
    return tiempo_total, {**resultados, **{"_errores": errores}}


# ===========================================================================
# MODELO 2 — FUTURES con as_completed
# ===========================================================================

def modelo_futures(iteracion: int) -> tuple[float, dict]:
    """
    Usa concurrent.futures.as_completed para procesar resultados en el orden
    en que van terminando (el más rápido primero), con manejo explícito de errores.

    Diferencia clave vs callbacks: el control de flujo es explícito en el
    hilo principal, no delegado a un callback.

    Retorna (tiempo_total, resultados).
    """
    resultados: dict[str, Any] = {}
    errores:    dict[str, str]  = {}

    inicio = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        # Mapear future → nombre para identificar qué terminó
        future_a_nombre = {
            executor.submit(fetch_productos_sync):  "productos",
            executor.submit(fetch_categorias_sync): "categorias",
            executor.submit(fetch_perfil_sync):     "perfil",
        }

        # as_completed itera en el orden en que terminan, no en el que se lanzaron
        for future in concurrent.futures.as_completed(
            future_a_nombre, timeout=TIMEOUT_CATEGORIAS + 1.0
        ):
            nombre = future_a_nombre[future]
            try:
                resultado = future.result()
                resultados[nombre] = resultado
            except concurrent.futures.TimeoutError:
                errores[nombre] = f"Timeout esperando '{nombre}'"
                resultados[nombre] = None
            except Exception as exc:
                errores[nombre] = f"Error en '{nombre}': {exc}"
                resultados[nombre] = None

    tiempo_total = time.time() - inicio
    return tiempo_total, {**resultados, **{"_errores": errores}}


# ===========================================================================
# MODELO 3 — ASYNC/AWAIT con asyncio.gather()
# ===========================================================================

async def fetch_productos_async() -> dict:
    """Simula GET /api/productos de forma asíncrona."""
    await asyncio.sleep(LATENCIA_PRODUCTOS)
    return {"endpoint": "/api/productos", "data": _MOCK_PRODUCTOS, "total": len(_MOCK_PRODUCTOS)}


async def fetch_categorias_async() -> dict:
    """Simula GET /api/categorias de forma asíncrona."""
    await asyncio.sleep(LATENCIA_CATEGORIAS)
    return {"endpoint": "/api/categorias", "data": _MOCK_CATEGORIAS}


async def fetch_perfil_async() -> dict:
    """Simula GET /api/perfil de forma asíncrona."""
    await asyncio.sleep(LATENCIA_PERFIL)
    return {"endpoint": "/api/perfil", "data": _MOCK_PERFIL}


async def _ejecutar_async(iteracion: int) -> tuple[float, dict]:
    """
    Corrutina principal: lanza las 3 peticiones concurrentemente con gather().
    return_exceptions=True asegura que un error en una NO cancela las demás.
    """
    inicio = time.time()

    try:
        productos, categorias, perfil = await asyncio.gather(
            fetch_productos_async(),
            asyncio.wait_for(fetch_categorias_async(), timeout=TIMEOUT_CATEGORIAS),
            fetch_perfil_async(),
            return_exceptions=True,
        )
    except Exception as exc:
        tiempo_total = time.time() - inicio
        return tiempo_total, {"_error_gather": str(exc)}

    tiempo_total = time.time() - inicio

    resultados = {}
    errores     = {}

    for nombre, resultado in [("productos", productos), ("categorias", categorias), ("perfil", perfil)]:
        if isinstance(resultado, Exception):
            errores[nombre] = str(resultado)
            resultados[nombre] = None
        else:
            resultados[nombre] = resultado

    return tiempo_total, {**resultados, **{"_errores": errores}}


def modelo_async(iteracion: int) -> tuple[float, dict]:
    """Envuelve la corrutina async para llamarla desde código síncrono."""
    return asyncio.run(_ejecutar_async(iteracion))


# ===========================================================================
# Función de medición
# ===========================================================================

def medir_modelo(nombre: str, funcion, repeticiones: int = 3) -> dict:
    """
    Ejecuta *funcion* *repeticiones* veces, registra los tiempos y
    retorna estadísticas.
    """
    print(f"\n{'─' * 60}")
    print(f"  Midiendo: {nombre}")
    print(f"{'─' * 60}")

    tiempos: list[float] = []

    for i in range(1, repeticiones + 1):
        print(f"  Iteración {i}/{repeticiones}...", end=" ", flush=True)
        t, datos = funcion(i)
        tiempos.append(t)
        errores = datos.get("_errores", {})
        estado  = "✓ OK" if not errores else f"⚠ {errores}"
        print(f"  {t:.4f} s   {estado}")

    promedio = sum(tiempos) / len(tiempos)
    minimo   = min(tiempos)
    maximo   = max(tiempos)

    print(f"  → Promedio: {promedio:.4f} s  |  Mín: {minimo:.4f} s  |  Máx: {maximo:.4f} s")

    return {
        "nombre":   nombre,
        "tiempos":  tiempos,
        "promedio": promedio,
        "minimo":   minimo,
        "maximo":   maximo,
    }


# ===========================================================================
# Tabla comparativa final
# ===========================================================================

def imprimir_tabla(resultados: list[dict]) -> None:
    """Imprime una tabla comparativa formateada en consola."""

    # Datos cualitativos por modelo
    meta = {
        "CALLBACKS (ThreadPoolExecutor)": {
            "manejo_errores": "Manual en callback",
            "legibilidad":    "★★☆☆☆ (2/5)",
            "recomendacion":  "Evitar — difícil de depurar",
        },
        "FUTURES (as_completed)": {
            "manejo_errores": "try/except explícito",
            "legibilidad":    "★★★☆☆ (3/5)",
            "recomendacion":  "OK para I/O con hilos",
        },
        "ASYNC/AWAIT (asyncio.gather)": {
            "manejo_errores": "return_exceptions=True",
            "legibilidad":    "★★★★★ (5/5)",
            "recomendacion":  "✅ Ideal para I/O concurrente",
        },
    }

    # Tiempo teórico secuencial (suma de latencias)
    seq = LATENCIA_PRODUCTOS + LATENCIA_CATEGORIAS + LATENCIA_PERFIL

    ancho = 100
    print("\n")
    print("═" * ancho)
    print("  TABLA COMPARATIVA — Modelos de Concurrencia".center(ancho))
    print(f"  Latencias simuladas: productos={LATENCIA_PRODUCTOS*1000:.0f}ms  "
          f"categorías={LATENCIA_CATEGORIAS*1000:.0f}ms  "
          f"perfil={LATENCIA_PERFIL*1000:.0f}ms  "
          f"→ secuencial total teórico={seq:.3f}s")
    print("═" * ancho)

    cabecera = f"{'Modelo':<35} {'Prom (s)':>10} {'Mín (s)':>10} {'Speedup':>9} {'Legibilidad':<20} {'Recomendación'}"
    print(cabecera)
    print("─" * ancho)

    for r in resultados:
        n       = r["nombre"]
        speedup = seq / r["promedio"]
        m       = meta.get(n, {})
        print(
            f"{n:<35} "
            f"{r['promedio']:>10.4f} "
            f"{r['minimo']:>10.4f} "
            f"{speedup:>8.1f}x "
            f"{m.get('legibilidad','—'):<20} "
            f"{m.get('recomendacion','—')}"
        )

    print("═" * ancho)
    print()

    # Veredicto
    mejor = min(resultados, key=lambda r: r["promedio"])
    print(f"  🏆 Modelo más rápido: {mejor['nombre']}  ({mejor['promedio']:.4f} s)")
    print(f"  ⏱️  Speedup vs secuencial teórico ({seq:.3f} s): {seq / mejor['promedio']:.1f}x")
    print()


# ===========================================================================
# Punto de entrada
# ===========================================================================

if __name__ == "__main__":
    REPETICIONES = 3

    print("=" * 60)
    print("  Reto 1 — Comparación de Modelos de Concurrencia")
    print("  EcoMarket — Semana 3")
    print("=" * 60)
    print(f"  Cada modelo se ejecuta {REPETICIONES} veces.")
    print("  No se necesita el servidor real (datos en memoria).")

    # —— Medir los tres modelos ——
    r_callbacks = medir_modelo("CALLBACKS (ThreadPoolExecutor)", modelo_callbacks, REPETICIONES)
    r_futures   = medir_modelo("FUTURES (as_completed)",         modelo_futures,   REPETICIONES)
    r_async     = medir_modelo("ASYNC/AWAIT (asyncio.gather)",   modelo_async,     REPETICIONES)

    # —— Tabla final ——
    imprimir_tabla([r_callbacks, r_futures, r_async])

    print("  Conclusión:")
    print("  • Todos los modelos se ejecutan en ~max(latencias) en lugar de la suma.")
    print("  • async/await logra esto con un solo hilo, sin overhead de contexto.")
    print("  • Los callbacks son los más difíciles de mantener y depurar.")
    print("  • Para EcoMarket (I/O bound), async/await es la mejor elección.\n")
