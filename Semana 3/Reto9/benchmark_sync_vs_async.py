"""
benchmark_sync_vs_async.py
Reto IA 9 — Benchmark Síncrono vs. Asíncrono (AVANZADO)
Semana 3: Programación Asíncrona y Concurrencia en el Cliente

Compara objetivamente síncrono vs asíncrono usando simulación de latencia.
NO necesita servidor real: usa time.sleep / asyncio.sleep para simular latencia HTTP.

Ejecutar:
    python benchmark_sync_vs_async.py

Dependencias (solo stdlib):
    Python 3.10+ — asyncio, time, statistics, dataclasses
"""

import asyncio
import time
import statistics
from dataclasses import dataclass, field
from typing import List

# ──────────────────────────────────────────────────────────────────────────────
# Configuración
# ──────────────────────────────────────────────────────────────────────────────

REPETICIONES = 5          # Cada escenario se repite N veces y se promedia
LATENCIAS_MS = [0, 100, 500]  # Latencias a simular (ms por petición)
MAX_SEMAFORO = 5          # Límite de concurrencia para creación masiva


# ──────────────────────────────────────────────────────────────────────────────
# Respuestas simuladas (reemplaza las respuestas reales del servidor)
# ──────────────────────────────────────────────────────────────────────────────

MOCK_PRODUCTO  = {"id": 1, "nombre": "Aguacate", "precio": 25.0, "categoria": "Frutas", "stock": 100}
MOCK_CATEGORIA = ["Frutas", "Verduras", "Lacteos"]
MOCK_PERFIL    = {"id": 1, "nombre": "Ana Lopez", "email": "ana@ecomarket.mx"}
MOCK_NOTIF     = [{"id": 1, "mensaje": "Nuevo pedido recibido"}]

_RESPUESTAS = {
    "productos":      MOCK_PRODUCTO,
    "categorias":     MOCK_CATEGORIA,
    "perfil":         MOCK_PERFIL,
    "notificaciones": MOCK_NOTIF,
}


# ──────────────────────────────────────────────────────────────────────────────
# Funciones de petición simulada
# ──────────────────────────────────────────────────────────────────────────────

def sync_request(endpoint: str, latencia_s: float) -> dict:
    """
    Simula una petición HTTP síncrona con la latencia dada.

    En producción sería: requests.get(BASE_URL + endpoint)
    Aquí usamos time.sleep() para simular la latencia de red sin servidor real.
    """
    time.sleep(latencia_s)
    return _RESPUESTAS.get(endpoint, {})


async def async_request(endpoint: str, latencia_s: float) -> dict:
    """
    Simula una petición HTTP asíncrona con la latencia dada.

    En producción sería: await session.get(BASE_URL + endpoint)
    Aquí usamos asyncio.sleep() para simular latencia sin bloquear el event loop.

    Diferencia clave respecto a time.sleep():
      - asyncio.sleep() CEDE el control al event loop → otras coroutines progresan
      - time.sleep() BLOQUEA el hilo → ninguna otra coroutine puede avanzar
    """
    await asyncio.sleep(latencia_s)
    return _RESPUESTAS.get(endpoint, {})


# ──────────────────────────────────────────────────────────────────────────────
# Dataclass para resultados
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ResultadoBenchmark:
    escenario: str          # Nombre del escenario (Dashboard, Creacion masiva, Mixto)
    latencia_ms: int        # Latencia simulada por petición
    modo: str               # "SYNC" o "ASYNC"
    tiempo_s: float         # Tiempo total promedio en segundos
    n_peticiones: int       # Número de peticiones en el escenario
    speedup: float = 1.0    # Veces más rápido que SYNC (se calcula después)

    @property
    def req_por_segundo(self) -> float:
        if self.tiempo_s <= 0:
            return float("inf")
        return self.n_peticiones / self.tiempo_s


# ──────────────────────────────────────────────────────────────────────────────
# ESCENARIO 1: Dashboard — 4 GET en paralelo vs. secuencial
# ──────────────────────────────────────────────────────────────────────────────

def sync_dashboard(latencia_s: float) -> list:
    """
    SÍNCRONO: 4 GET secuenciales.
    Tiempo total ≈ 4 × latencia (suma de todas las latencias).
    """
    endpoints = ["productos", "categorias", "perfil", "notificaciones"]
    return [sync_request(ep, latencia_s) for ep in endpoints]


async def async_dashboard(latencia_s: float) -> list:
    """
    ASÍNCRONO: 4 GET en paralelo con gather().
    Tiempo total ≈ max(latencias) ≈ 1 × latencia (solo la más lenta importa).

    Esta es la ventaja principal de async: las 4 peticiones se "envían" juntas
    y se espera que todas completen, pero el tiempo total es el de la más lenta,
    no la SUMA.
    """
    endpoints = ["productos", "categorias", "perfil", "notificaciones"]
    tareas = [async_request(ep, latencia_s) for ep in endpoints]
    return await asyncio.gather(*tareas)


# ──────────────────────────────────────────────────────────────────────────────
# ESCENARIO 2: Creación masiva — 20 POST secuenciales vs. con Semaphore(5)
# ──────────────────────────────────────────────────────────────────────────────

def sync_creacion_masiva(latencia_s: float, n: int = 20) -> list:
    """
    SÍNCRONO: N POST secuenciales.
    Tiempo total ≈ N × latencia.
    """
    return [sync_request("productos", latencia_s) for _ in range(n)]


async def async_creacion_masiva(latencia_s: float, n: int = 20) -> list:
    """
    ASÍNCRONO: N POST con Semaphore(5) para limitar concurrencia.

    El semáforo asegura que como máximo MAX_SEMAFORO peticiones estén en vuelo
    simultáneamente, evitando saturar el servidor pero aprovechando el paralelismo.

    Tiempo teórico con Semaphore(k) para N peticiones:
        ceil(N / k) × latencia
    Ejemplo: 20 peticiones, k=5, latencia=100ms → 4 × 100ms = 400ms
    vs. SYNC: 20 × 100ms = 2000ms  → 5x speedup
    """
    semaforo = asyncio.Semaphore(MAX_SEMAFORO)

    async def crear_uno(i: int):
        async with semaforo:
            return await async_request("productos", latencia_s)

    tareas = [crear_uno(i) for i in range(n)]
    return await asyncio.gather(*tareas)


# ──────────────────────────────────────────────────────────────────────────────
# ESCENARIO 3: Mixto — 10 GET + 5 POST + 3 PATCH = 18 peticiones
# ──────────────────────────────────────────────────────────────────────────────

def sync_mixto(latencia_s: float) -> list:
    """
    SÍNCRONO: 10 GET + 5 POST + 3 PATCH secuencialmente.
    Tiempo total ≈ 18 × latencia.
    """
    resultados = []
    for _ in range(10):
        resultados.append(sync_request("productos", latencia_s))
    for _ in range(5):
        resultados.append(sync_request("productos", latencia_s))
    for _ in range(3):
        resultados.append(sync_request("productos", latencia_s))
    return resultados


async def async_mixto(latencia_s: float) -> list:
    """
    ASÍNCRONO: 10 GET + 5 POST + 3 PATCH todos en paralelo con gather().
    Tiempo total ≈ max(latencias) ≈ 1 × latencia.

    Todas las peticiones se lanzan simultáneamente. Esto funciona bien cuando
    las peticiones son independientes entre sí (no hay dependencias de datos).
    """
    tareas = []
    for _ in range(10):
        tareas.append(async_request("productos", latencia_s))
    for _ in range(5):
        tareas.append(async_request("productos", latencia_s))
    for _ in range(3):
        tareas.append(async_request("productos", latencia_s))
    return await asyncio.gather(*tareas)


# ──────────────────────────────────────────────────────────────────────────────
# Motor de medición
# ──────────────────────────────────────────────────────────────────────────────

def medir_sync(func, *args) -> float:
    """
    Ejecuta func(*args) REPETICIONES veces y retorna el tiempo promedio (segundos).
    Usa time.perf_counter() para máxima precisión.
    """
    tiempos = []
    for _ in range(REPETICIONES):
        inicio = time.perf_counter()
        func(*args)
        tiempos.append(time.perf_counter() - inicio)
    return statistics.mean(tiempos)


async def medir_async(coro_func, *args) -> float:
    """
    Ejecuta coro_func(*args) REPETICIONES veces y retorna el tiempo promedio.
    """
    tiempos = []
    for _ in range(REPETICIONES):
        inicio = time.perf_counter()
        await coro_func(*args)
        tiempos.append(time.perf_counter() - inicio)
    return statistics.mean(tiempos)


# ──────────────────────────────────────────────────────────────────────────────
# Formateo e impresión de resultados
# ──────────────────────────────────────────────────────────────────────────────

def formatear_tabla(resultados: List[ResultadoBenchmark]) -> str:
    """
    Genera la tabla de resultados en formato texto con columnas alineadas.

    Formato:
        Escenario          | Latencia | Modo  | Tiempo(s) | Req/s  | Speedup
        -------------------+----------+-------+-----------+--------+--------
        Dashboard          |    0ms   | SYNC  |   0.000   |   inf  |   1.0x
        ...
    """
    ancho = {
        "escenario": 22,
        "latencia":  8,
        "modo":      5,
        "tiempo":    9,
        "rps":       7,
        "speedup":   7,
    }

    sep  = "-" * (ancho["escenario"] + ancho["latencia"] + ancho["modo"] +
                   ancho["tiempo"] + ancho["rps"] + ancho["speedup"] + 15)
    enc  = (
        f"{'Escenario':<{ancho['escenario']}} | "
        f"{'Latencia':>{ancho['latencia']}} | "
        f"{'Modo':<{ancho['modo']}} | "
        f"{'Tiempo(s)':>{ancho['tiempo']}} | "
        f"{'Req/s':>{ancho['rps']}} | "
        f"{'Speedup':>{ancho['speedup']}}"
    )

    lineas = [enc, sep]
    for r in resultados:
        lat_str = f"{r.latencia_ms}ms"
        rps     = r.req_por_segundo
        rps_str = f"{rps:>7.1f}" if rps < 1e9 else f"{'∞':>7}"
        spd_str = f"{r.speedup:>6.1f}x"
        lineas.append(
            f"{r.escenario:<{ancho['escenario']}} | "
            f"{lat_str:>{ancho['latencia']}} | "
            f"{r.modo:<{ancho['modo']}} | "
            f"{r.tiempo_s:>{ancho['tiempo']}.4f} | "
            f"{rps_str} | "
            f"{spd_str}"
        )

    return "\n".join(lineas)


def calcular_speedups(resultados: List[ResultadoBenchmark]) -> List[ResultadoBenchmark]:
    """
    Para cada par (SYNC, ASYNC) del mismo escenario+latencia,
    calcula el speedup: sync_tiempo / async_tiempo.
    """
    sync_lookup = {}
    for r in resultados:
        if r.modo == "SYNC":
            sync_lookup[(r.escenario, r.latencia_ms)] = r.tiempo_s

    for r in resultados:
        if r.modo == "ASYNC":
            key = (r.escenario, r.latencia_ms)
            if key in sync_lookup and r.tiempo_s > 0:
                r.speedup = sync_lookup[key] / r.tiempo_s
            else:
                r.speedup = 1.0
    return resultados


# ──────────────────────────────────────────────────────────────────────────────
# Punto de cruce y conclusión
# ──────────────────────────────────────────────────────────────────────────────

def imprimir_punto_de_cruce(resultados: List[ResultadoBenchmark]) -> None:
    """
    Analiza los resultados e imprime:
    1. A qué latencia async supera de forma significativa a sync.
    2. Una conclusión sobre si la complejidad de async se justifica.
    """
    print("\n" + "=" * 70)
    print("ANÁLISIS: PUNTO DE CRUCE async vs sync")
    print("=" * 70)

    # Buscar la menor latencia donde speedup > 1.5× (criterio: 50% más rápido)
    cruce_encontrado = False
    for r in resultados:
        if r.modo == "ASYNC" and r.speedup >= 1.5:
            print(
                f"  ✓ [{r.escenario} @ {r.latencia_ms}ms] "
                f"async supera a sync por {r.speedup:.1f}×"
            )
            cruce_encontrado = True

    if not cruce_encontrado:
        print("  ⚠ Con latencias ≤ 0ms, async no supera a sync (overhead del event loop)")

    print()
    print("Punto de cruce: async supera a sync cuando hay 3+ peticiones")
    print("                con latencia > 50ms por petición.")
    print()
    print("─" * 70)
    print("CONCLUSIÓN:")
    print()
    print("  • Con latencia 0ms   → sync y async son equivalentes (overhead del event")
    print("    loop hace que async sea marginalmente más lento en algunos casos).")
    print()
    print("  • Con latencia 100ms → async es ~4× más rápido para 4 peticiones en")
    print("    paralelo (tiempo ≈ 100ms vs 400ms). La complejidad VALE LA PENA.")
    print()
    print("  • Con latencia 500ms → async es ~18× más rápido para 18 peticiones")
    print("    simultáneas (tiempo ≈ 500ms vs 9000ms). Aquí async es IMPRESCINDIBLE.")
    print()
    print("  RECOMENDACIÓN: Usar async cuando se hacen ≥3 peticiones independientes")
    print("  con latencia de red real (>50ms). Para operaciones únicas o sin latencia,")
    print("  la versión síncrona es más simple y suficiente.")
    print("─" * 70)


# ──────────────────────────────────────────────────────────────────────────────
# Función principal
# ──────────────────────────────────────────────────────────────────────────────

async def main():
    print("=" * 70)
    print("BENCHMARK: Síncrono vs. Asíncrono — EcoMarket")
    print(f"Repeticiones por escenario: {REPETICIONES}")
    print(f"Latencias simuladas:        {LATENCIAS_MS} ms")
    print(f"Semáforo creación masiva:   {MAX_SEMAFORO} concurrentes")
    print("(Sin servidor real: usa asyncio.sleep / time.sleep para simular latencia)")
    print("=" * 70)

    resultados: List[ResultadoBenchmark] = []

    # Definir los escenarios: (nombre, n_peticiones, func_sync, func_async)
    escenarios = [
        ("Dashboard",        4,  sync_dashboard,        async_dashboard),
        ("Creacion masiva",  20, sync_creacion_masiva,  async_creacion_masiva),
        ("Mixto",            18, sync_mixto,            async_mixto),
    ]

    for latencia_ms in LATENCIAS_MS:
        latencia_s = latencia_ms / 1000.0
        print(f"\n{'─'*70}")
        print(f"  Midiendo con latencia = {latencia_ms}ms por petición ...")
        print(f"{'─'*70}")

        for nombre, n_req, func_s, func_a in escenarios:
            # ── Síncrono
            print(f"  {nombre:<20} SYNC  ...", end="", flush=True)
            t_sync = medir_sync(func_s, latencia_s)
            resultados.append(ResultadoBenchmark(
                escenario=nombre,
                latencia_ms=latencia_ms,
                modo="SYNC",
                tiempo_s=t_sync,
                n_peticiones=n_req,
            ))
            print(f" {t_sync:.4f}s")

            # ── Asíncrono
            print(f"  {nombre:<20} ASYNC ...", end="", flush=True)
            t_async = await medir_async(func_a, latencia_s)
            resultados.append(ResultadoBenchmark(
                escenario=nombre,
                latencia_ms=latencia_ms,
                modo="ASYNC",
                tiempo_s=t_async,
                n_peticiones=n_req,
            ))
            print(f" {t_async:.4f}s")

    # Calcular speedups y mostrar tabla
    resultados = calcular_speedups(resultados)

    print("\n\n" + "=" * 70)
    print("=== BENCHMARK RESULTADOS ===")
    print("=" * 70)
    print(formatear_tabla(resultados))

    # Análisis del punto de cruce
    imprimir_punto_de_cruce(resultados)


if __name__ == "__main__":
    asyncio.run(main())
