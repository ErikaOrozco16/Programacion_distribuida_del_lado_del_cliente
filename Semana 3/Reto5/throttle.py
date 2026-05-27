"""
throttle.py — Módulo de control de tráfico para EcoMarket (Reto 5, Semana 3)
=============================================================================
Implementa tres capas de throttling:
  1. ConcurrencyLimiter  — limita cuántas peticiones corren EN PARALELO
  2. RateLimiter         — limita cuántas peticiones se INICIAN por segundo
  3. ThrottledClient     — cliente HTTP que combina ambos mecanismos

Uso:
    async with aiohttp.ClientSession() as session:
        client = ThrottledClient(session, max_concurrent=5, max_per_second=10)
        data = await client.get("http://localhost:3000/api/productos")

Ejecutar la demo standalone:
    python throttle.py
"""

import asyncio
import aiohttp
import time
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

# ─── Configuración de logging ────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("throttle")


# ═══════════════════════════════════════════════════════════════════════════════
# CLASE 1: ConcurrencyLimiter
# ═══════════════════════════════════════════════════════════════════════════════

class ConcurrencyLimiter:
    """
    Limita cuántas corrutinas pueden estar ACTIVAS simultáneamente.

    Internamente usa asyncio.Semaphore, que es 100 % compatible con el event
    loop y NO requiere locks de threading.

    Ejemplo:
        limiter = ConcurrencyLimiter(max_concurrent=5)
        async with limiter:
            response = await session.get(url)
    """

    def __init__(self, max_concurrent: int) -> None:
        if max_concurrent < 1:
            raise ValueError("max_concurrent debe ser >= 1")
        self._semaforo = asyncio.Semaphore(max_concurrent)
        self._max_concurrent = max_concurrent
        self._en_vuelo: int = 0          # corrutinas activas AHORA
        self._pico_concurrencia: int = 0  # máximo histórico alcanzado

    # ── Propiedades de observabilidad ────────────────────────────────────────

    @property
    def en_vuelo(self) -> int:
        """Número de corrutinas activas en este momento."""
        return self._en_vuelo

    @property
    def pico_concurrencia(self) -> int:
        """Máximo de corrutinas que estuvieron activas a la vez (histórico)."""
        return self._pico_concurrencia

    # ── Context manager asíncrono ─────────────────────────────────────────────

    async def __aenter__(self) -> "ConcurrencyLimiter":
        # Espera hasta que haya un "slot" disponible en el semáforo
        await self._semaforo.acquire()
        self._en_vuelo += 1
        if self._en_vuelo > self._pico_concurrencia:
            self._pico_concurrencia = self._en_vuelo
        logger.debug(
            "ConcurrencyLimiter: INICIO — en vuelo=%d / max=%d",
            self._en_vuelo,
            self._max_concurrent,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        self._en_vuelo -= 1
        self._semaforo.release()
        logger.debug(
            "ConcurrencyLimiter: FIN   — en vuelo=%d / max=%d",
            self._en_vuelo,
            self._max_concurrent,
        )
        # Devolver False: no suprimimos excepciones
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# CLASE 2: RateLimiter  (token bucket)
# ═══════════════════════════════════════════════════════════════════════════════

class RateLimiter:
    """
    Implementa el algoritmo "token bucket" para limitar peticiones por segundo.

    Cada vez que se llama a `acquire()` se consume un token. Si no hay tokens
    disponibles, la corrutina espera hasta que el bucket se recargue.

    El bucket se recarga automáticamente con el tiempo transcurrido:
        tokens_nuevos = tiempo_transcurrido * max_per_second

    Ejemplo:
        rl = RateLimiter(max_per_second=10)
        await rl.acquire()       # garantiza que no se superan 10 req/s
        response = await session.get(url)
    """

    def __init__(self, max_per_second: float) -> None:
        if max_per_second <= 0:
            raise ValueError("max_per_second debe ser > 0")
        self._rate = max_per_second              # tokens por segundo
        self._tokens: float = max_per_second     # bucket lleno al inicio
        self._max_tokens: float = max_per_second # capacidad máxima del bucket
        self._ultimo_refill: float = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        """
        Recarga tokens según el tiempo transcurrido desde la última llamada.
        Debe llamarse DENTRO del lock para evitar condiciones de carrera.
        """
        ahora = time.monotonic()
        elapsed = ahora - self._ultimo_refill
        nuevos = elapsed * self._rate
        self._tokens = min(self._max_tokens, self._tokens + nuevos)
        self._ultimo_refill = ahora

    async def acquire(self) -> None:
        """
        Espera hasta que haya un token disponible y lo consume.
        Registra cuánto tiempo esperó la corrutina.
        """
        inicio_espera = time.monotonic()

        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    tiempo_espera = time.monotonic() - inicio_espera
                    if tiempo_espera > 0.001:  # solo loguear si esperó algo
                        logger.debug(
                            "RateLimiter: token adquirido tras %.3fs de espera "
                            "(tokens restantes=%.2f)",
                            tiempo_espera,
                            self._tokens,
                        )
                    return  # ← token consumido, continúa

                # Calcular cuánto tiempo esperar hasta el próximo token
                tiempo_hasta_token = (1.0 - self._tokens) / self._rate

            # Esperar FUERA del lock para no bloquear a otras corrutinas
            logger.debug(
                "RateLimiter: sin tokens disponibles, esperando %.3fs",
                tiempo_hasta_token,
            )
            await asyncio.sleep(tiempo_hasta_token)


# ═══════════════════════════════════════════════════════════════════════════════
# CLASE 3: ThrottledClient
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class _Estadisticas:
    """Acumula métricas de uso del ThrottledClient."""
    peticiones_realizadas: int = 0
    peticiones_exitosas: int = 0
    peticiones_fallidas: int = 0
    tiempo_total_espera: float = 0.0
    inicio: float = field(default_factory=time.monotonic)


class ThrottledClient:
    """
    Cliente HTTP con throttling integrado.

    Combina ConcurrencyLimiter + RateLimiter para garantizar:
      - No más de `max_concurrent` peticiones simultáneas
      - No más de `max_per_second` peticiones iniciadas por segundo

    Expone los métodos HTTP más comunes: GET, POST, PATCH, DELETE.

    Ejemplo:
        async with aiohttp.ClientSession() as session:
            client = ThrottledClient(session, max_concurrent=5, max_per_second=10)
            data = await client.get("http://localhost:3000/api/productos")
            print(client.stats())
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        max_concurrent: int = 10,
        max_per_second: float = 20,
    ) -> None:
        self._session = session
        self._concurrency = ConcurrencyLimiter(max_concurrent)
        self._rate = RateLimiter(max_per_second)
        self._stats = _Estadisticas()

    # ── Método interno que aplica ambos limitadores ───────────────────────────

    async def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        """
        Ejecuta una petición HTTP pasando por el rate limiter y el concurrency
        limiter en ese orden.

        Devuelve el texto de la respuesta o lanza la excepción original.
        """
        t0 = time.monotonic()

        # 1️⃣  Rate limiter: espera hasta poder iniciar la petición
        await self._rate.acquire()

        espera_rate = time.monotonic() - t0
        self._stats.tiempo_total_espera += espera_rate
        self._stats.peticiones_realizadas += 1

        # 2️⃣  Concurrency limiter: espera hasta que haya slot disponible
        async with self._concurrency:
            logger.info(
                "→ %s %s (en vuelo=%d)",
                method.upper(),
                url,
                self._concurrency.en_vuelo,
            )
            try:
                async with self._session.request(method, url, **kwargs) as resp:
                    resp.raise_for_status()
                    body = await resp.json()
                    self._stats.peticiones_exitosas += 1
                    logger.info("← %s %s [%d]", method.upper(), url, resp.status)
                    return body
            except Exception as exc:
                self._stats.peticiones_fallidas += 1
                logger.warning("✗ %s %s — %s", method.upper(), url, exc)
                raise

    # ── Métodos HTTP públicos ─────────────────────────────────────────────────

    async def get(self, url: str, **kwargs: Any) -> Any:
        """Petición GET con throttling aplicado."""
        return await self._request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> Any:
        """Petición POST con throttling aplicado."""
        return await self._request("POST", url, **kwargs)

    async def patch(self, url: str, **kwargs: Any) -> Any:
        """Petición PATCH con throttling aplicado."""
        return await self._request("PATCH", url, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> Any:
        """Petición DELETE con throttling aplicado."""
        return await self._request("DELETE", url, **kwargs)

    # ── Estadísticas ──────────────────────────────────────────────────────────

    def stats(self) -> dict:
        """
        Devuelve un diccionario con estadísticas acumuladas de uso.

        Claves:
          - peticiones_realizadas: total de llamadas iniciadas
          - peticiones_exitosas:   respuestas HTTP 2xx
          - peticiones_fallidas:   errores de red / HTTP 4xx-5xx
          - pico_concurrencia:     máximo de peticiones en vuelo simultáneamente
          - tiempo_total_espera_s: segundos acumulados esperando tokens
          - req_por_segundo_real:  tasa real desde la primera petición
        """
        duracion = time.monotonic() - self._stats.inicio
        req_s = (
            self._stats.peticiones_realizadas / duracion if duracion > 0 else 0
        )
        return {
            "peticiones_realizadas": self._stats.peticiones_realizadas,
            "peticiones_exitosas": self._stats.peticiones_exitosas,
            "peticiones_fallidas": self._stats.peticiones_fallidas,
            "pico_concurrencia": self._concurrency.pico_concurrencia,
            "tiempo_total_espera_s": round(self._stats.tiempo_total_espera, 3),
            "req_por_segundo_real": round(req_s, 2),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# DEMO: 50 peticiones con y sin throttling
# ═══════════════════════════════════════════════════════════════════════════════

async def demo_50_peticiones() -> None:
    """
    Demuestra el efecto del throttling con 50 "peticiones" simuladas.

    No requiere servidor real: asyncio.sleep() simula latencia de red.
    Cada petición dura entre 80 ms y 200 ms (aleatoria dentro del rango).

    Muestra:
      1. Tabla de slots de 0.5 s con peticiones en vuelo.
      2. Comparación contra ejecución sin throttling.
    """
    import random

    TOTAL_PETICIONES = 50
    MAX_CONCURRENT = 5      # máximo 5 en vuelo simultáneos
    MAX_PER_SECOND = 8.0    # máximo 8 iniciadas por segundo

    print("\n" + "═" * 65)
    print("  DEMO — 50 peticiones con throttling (sin servidor real)")
    print("═" * 65)

    # ── Registro de métricas ──────────────────────────────────────────────────
    inicio_global = time.monotonic()
    registros: list[dict] = []   # una entrada por petición

    concurrency_limiter = ConcurrencyLimiter(MAX_CONCURRENT)
    rate_limiter = RateLimiter(MAX_PER_SECOND)

    async def peticion_simulada(idx: int) -> None:
        """Simula una petición HTTP con throttling."""
        # ── Rate limit ────────────────────────────────────────────────────────
        await rate_limiter.acquire()

        # ── Concurrency limit ─────────────────────────────────────────────────
        async with concurrency_limiter:
            t_inicio = time.monotonic() - inicio_global
            duracion = random.uniform(0.08, 0.20)  # 80–200 ms de "red"
            registros.append({"idx": idx, "t_inicio": t_inicio, "en_vuelo": concurrency_limiter.en_vuelo})

            await asyncio.sleep(duracion)   # simula latencia de red

            t_fin = time.monotonic() - inicio_global
            registros[-1]["t_fin"] = t_fin

    # ── Lanzar 50 tareas CON throttling ──────────────────────────────────────
    print(f"\n[CON throttling] max_concurrent={MAX_CONCURRENT}, max_per_second={MAX_PER_SECOND}")
    tareas = [asyncio.create_task(peticion_simulada(i)) for i in range(TOTAL_PETICIONES)]
    await asyncio.gather(*tareas)

    duracion_total = time.monotonic() - inicio_global
    print(f"  ✓ {TOTAL_PETICIONES} peticiones completadas en {duracion_total:.2f}s")
    print(f"  ✓ Pico de concurrencia: {concurrency_limiter.pico_concurrencia}")
    print(f"  ✓ Tasa real: {TOTAL_PETICIONES / duracion_total:.1f} req/s")

    # ── Tabla de slots temporales (0.5 s cada uno) ───────────────────────────
    slot_size = 0.5
    num_slots = int(duracion_total / slot_size) + 1

    print("\n  Tabla de actividad (ventanas de 0.5 s):")
    print(f"  {'Tiempo':>8}  {'En vuelo (máx)':>15}  {'Iniciadas':>10}  {'Completadas':>12}")
    print("  " + "─" * 52)

    for slot in range(num_slots):
        t_ini = slot * slot_size
        t_fin_slot = t_ini + slot_size
        en_vuelo_en_slot = [
            r for r in registros
            if r["t_inicio"] < t_fin_slot and r.get("t_fin", t_fin_slot) > t_ini
        ]
        iniciadas = sum(1 for r in registros if t_ini <= r["t_inicio"] < t_fin_slot)
        completadas = sum(1 for r in registros if t_ini <= r.get("t_fin", -1) < t_fin_slot)
        pico_slot = max((r["en_vuelo"] for r in en_vuelo_en_slot), default=0)

        print(f"  {t_ini:>6.1f}s  {pico_slot:>15}  {iniciadas:>10}  {completadas:>12}")

    # ── Comparación SIN throttling ────────────────────────────────────────────
    print("\n[SIN throttling] todas las peticiones lanzadas al mismo tiempo")
    registros_sin: list[dict] = []

    async def peticion_libre(idx: int) -> None:
        t_i = time.monotonic()
        dur = 0.14  # promedio fijo para comparación justa
        await asyncio.sleep(dur)
        t_f = time.monotonic()
        registros_sin.append({"t_inicio": t_i, "t_fin": t_f})

    t0_sin = time.monotonic()
    await asyncio.gather(*[peticion_libre(i) for i in range(TOTAL_PETICIONES)])
    dur_sin = time.monotonic() - t0_sin

    print(f"  ✓ {TOTAL_PETICIONES} peticiones completadas en {dur_sin:.2f}s")
    print(f"  ✓ Concurrencia real: {TOTAL_PETICIONES} (todas simultáneas)")
    print(f"  ✓ Tasa real: {TOTAL_PETICIONES / dur_sin:.1f} req/s")

    # ── Resumen comparativo ───────────────────────────────────────────────────
    print("\n" + "─" * 65)
    print("  COMPARACIÓN")
    print(f"  {'Métrica':<30} {'CON throttling':>15} {'SIN throttling':>15}")
    print("  " + "─" * 62)
    print(f"  {'Tiempo total (s)':<30} {duracion_total:>15.2f} {dur_sin:>15.2f}")
    print(f"  {'Pico concurrencia':<30} {concurrency_limiter.pico_concurrencia:>15} {TOTAL_PETICIONES:>15}")
    print(f"  {'Req/s real':<30} {TOTAL_PETICIONES/duracion_total:>15.1f} {TOTAL_PETICIONES/dur_sin:>15.1f}")
    print("─" * 65)
    print("  → Throttling protege al servidor sacrificando throughput bruto.")
    print("  → En producción, evita errores 429 / 503 y respeta SLAs del API.")
    print("═" * 65 + "\n")


# ═══════════════════════════════════════════════════════════════════════════════
# PUNTO DE ENTRADA
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    asyncio.run(demo_50_peticiones())
