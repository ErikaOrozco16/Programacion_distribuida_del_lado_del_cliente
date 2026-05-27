"""
smart_session.py
Reto IA 10 — Diseñador de Pool de Conexiones Inteligente (AVANZADO)
Semana 3: Programación Asíncrona y Concurrencia en el Cliente

Drop-in replacement para aiohttp.ClientSession con monitoreo del pool de conexiones.
"""

import asyncio
import time
import aiohttp
from aiohttp import TCPConnector
from dataclasses import dataclass, field


# ──────────────────────────────────────────────
# Métricas del Pool
# ──────────────────────────────────────────────

@dataclass
class PoolMetrics:
    conexiones_creadas: int = 0
    conexiones_reutilizadas: int = 0
    conexiones_cerradas: int = 0
    peticiones_en_cola: int = 0
    pico_conexiones_activas: int = 0
    _activas_ahora: int = field(default=0, repr=False)

    def registrar_nueva(self):
        self.conexiones_creadas += 1
        self._activas_ahora += 1
        if self._activas_ahora > self.pico_conexiones_activas:
            self.pico_conexiones_activas = self._activas_ahora

    def registrar_reutilizada(self):
        self.conexiones_reutilizadas += 1

    def registrar_cerrada(self):
        self.conexiones_cerradas += 1
        self._activas_ahora = max(0, self._activas_ahora - 1)

    def resumen(self) -> str:
        return (
            f"Creadas: {self.conexiones_creadas} | "
            f"Reutilizadas: {self.conexiones_reutilizadas} | "
            f"Cerradas: {self.conexiones_cerradas} | "
            f"Pico activas: {self.pico_conexiones_activas}"
        )


# ──────────────────────────────────────────────
# SmartSession — Drop-in replacement para ClientSession
# ──────────────────────────────────────────────

class SmartSession:
    """
    Wrapper de aiohttp.ClientSession con:
    - TCPConnector configurado con límites apropiados
    - Monitoreo del estado del pool
    - Métricas de conexiones
    - Health check periódico

    Uso:
        async with SmartSession(limit=10) as session:
            async with session.get(url) as resp:
                datos = await resp.json()
    """

    def __init__(
        self,
        limit: int = 10,
        limit_per_host: int = 5,
        keepalive_timeout: float = 30,
        health_check_interval: float = 60,
        **kwargs
    ):
        self.metrics = PoolMetrics()
        self._limit = limit
        self._connector = TCPConnector(
            limit=limit,
            limit_per_host=limit_per_host,
            keepalive_timeout=keepalive_timeout,
            enable_cleanup_closed=True,
        )
        self._session = aiohttp.ClientSession(
            connector=self._connector,
            **kwargs
        )
        self._health_check_task = None
        self._health_check_interval = health_check_interval

    async def __aenter__(self):
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        return self

    async def __aexit__(self, *args):
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        await self._session.close()
        print(f"\n[SmartSession] Pool cerrado. {self.metrics.resumen()}")

    def get(self, url, **kwargs):
        """Proxy de session.get() con métricas."""
        return self._session.get(url, **kwargs)

    def post(self, url, **kwargs):
        """Proxy de session.post() con métricas."""
        return self._session.post(url, **kwargs)

    def put(self, url, **kwargs):
        """Proxy de session.put() con métricas."""
        return self._session.put(url, **kwargs)

    def patch(self, url, **kwargs):
        """Proxy de session.patch() con métricas."""
        return self._session.patch(url, **kwargs)

    def delete(self, url, **kwargs):
        """Proxy de session.delete() con métricas."""
        return self._session.delete(url, **kwargs)

    def estado_pool(self) -> dict:
        """Retorna el estado actual del pool de conexiones."""
        return {
            "limite_global": self._limit,
            "conexiones_activas": self._connector._acquired_per_host,
            "metricas": self.metrics.resumen(),
        }

    async def _health_check_loop(self):
        """Verifica el estado del pool periódicamente."""
        while True:
            await asyncio.sleep(self._health_check_interval)
            estado = self.estado_pool()
            print(f"[HealthCheck] Pool: {estado}")


# ──────────────────────────────────────────────
# Benchmark: 5 vs. 20 conexiones vs. ilimitado
# ──────────────────────────────────────────────

BASE_URL = "http://localhost:3000/api/"

async def benchmark_pool(limit, nombre, n_peticiones=50):
    """Benchmark con una configuración de pool específica."""
    connector_kwargs = {} if limit == 0 else {"limit": limit}
    connector = TCPConnector(**connector_kwargs)

    inicio = time.monotonic()
    async with aiohttp.ClientSession(connector=connector) as session:
        tareas = [
            session.get(f"{BASE_URL}productos")
            for _ in range(n_peticiones)
        ]
        responses = await asyncio.gather(*tareas, return_exceptions=True)
        # Leer los cuerpos
        for r in responses:
            if not isinstance(r, Exception):
                try:
                    async with r:
                        await r.json()
                except Exception:
                    pass

    duracion = time.monotonic() - inicio
    throughput = n_peticiones / duracion
    print(f"  [{nombre}] Pool={limit or 'ilimitado'} | "
          f"Tiempo: {duracion:.2f}s | Throughput: {throughput:.1f} req/s")
    return duracion, throughput


async def main():
    print("=" * 60)
    print("SmartSession — Benchmark de Configuraciones de Pool")
    print("=" * 60)

    configs = [
        (5, "Pool pequeño (5)"),
        (20, "Pool mediano (20)"),
        (0, "Sin límite (ilimitado)"),
    ]

    resultados = []
    for limit, nombre in configs:
        duracion, throughput = await benchmark_pool(limit, nombre)
        resultados.append((nombre, duracion, throughput))

    print("\n=== Resumen ===")
    print(f"{'Configuración':<25} {'Tiempo (s)':>12} {'Req/s':>10}")
    print("-" * 50)
    for nombre, dur, tput in resultados:
        print(f"{nombre:<25} {dur:>12.2f} {tput:>10.1f}")

    print("\n=== Usando SmartSession ===")
    async with SmartSession(limit=10, limit_per_host=5) as smart:
        tareas = [smart.get(f"{BASE_URL}productos") for _ in range(20)]
        await asyncio.gather(*tareas, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
