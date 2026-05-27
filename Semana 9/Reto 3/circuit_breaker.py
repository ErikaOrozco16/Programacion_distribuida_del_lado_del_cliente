"""
circuit_breaker.py - CircuitBreaker del lado del cliente para EcoMarket.

Decisiones de resiliencia:
  1. Cuentan como fallo del servidor: timeouts, errores de red, ConnectionError,
     OSError y respuestas HTTP 5xx. No cuentan como fallo: 4xx, ValueError ni
     errores de parseo del cliente.
  2. Umbral elegido: 3 fallos consecutivos. En EcoMarket protege pronto al
     servidor sin abrir el circuito por un error aislado.
  3. Timeout de apertura: 2 segundos para la demo local. En produccion se
     recomienda iniciar entre 30 y 60 segundos y ajustarlo con telemetria.

Tabla de clasificacion usada por _es_fallo_servidor:
  - 500, 502, 503, 504: fallo del servidor.
  - timeout: fallo del servidor o red.
  - conexion rechazada / red caida: fallo del servidor o infraestructura.
  - 400, 401, 403, 404, 409, 422, 429: no abren este breaker general.
    429 puede manejarse con backoff especifico, no como caida del servidor.
"""

import asyncio
import time
import inspect
from enum import Enum, auto


class EstadoCircuito(Enum):
    CERRADO = auto()
    ABIERTO = auto()
    SEMIABIERTO = auto()


class CircuitOpenError(Exception):
    """El circuito esta abierto y no se intento contactar al servidor."""

    def __init__(self, tiempo_restante: float):
        self.tiempo_restante = max(0.0, tiempo_restante)
        super().__init__(
            f"Circuit breaker abierto. Reintenta en {self.tiempo_restante:.1f}s"
        )


class HttpError(Exception):
    """Excepcion HTTP simple para que las pruebas no dependan de aiohttp."""

    def __init__(self, status: int, message: str = ""):
        self.status = status
        super().__init__(message or f"HTTP {status}")


class CircuitBreaker:
    """Implementa el patron Circuit Breaker del lado del cliente."""

    def __init__(
        self,
        umbral_fallos: int = 3,
        timeout_apertura: float = 2.0,
        nombre: str = "EcoMarketAPI",
    ):
        if umbral_fallos < 1:
            raise ValueError("umbral_fallos debe ser mayor o igual a 1")
        if timeout_apertura <= 0:
            raise ValueError("timeout_apertura debe ser mayor que 0")

        self._umbral_fallos = umbral_fallos
        self._timeout_apertura = timeout_apertura
        self._nombre = nombre
        self._estado = EstadoCircuito.CERRADO
        self._fallos_consecutivos = 0
        self._tiempo_apertura = None
        self._lock = asyncio.Lock()
        self._probe_en_curso = False

    @property
    def estado(self) -> EstadoCircuito:
        self._revisar_timeout()
        return self._estado

    @property
    def esta_abierto(self) -> bool:
        return self.estado == EstadoCircuito.ABIERTO

    def _revisar_timeout(self) -> None:
        if self._estado != EstadoCircuito.ABIERTO or self._tiempo_apertura is None:
            return

        transcurrido = time.monotonic() - self._tiempo_apertura
        if transcurrido >= self._timeout_apertura:
            self._estado = EstadoCircuito.SEMIABIERTO
            self._probe_en_curso = False

    def _tiempo_restante(self) -> float:
        if self._tiempo_apertura is None:
            return 0.0
        transcurrido = time.monotonic() - self._tiempo_apertura
        return max(0.0, self._timeout_apertura - transcurrido)

    def _es_fallo_servidor(self, excepcion: Exception) -> bool:
        status = getattr(excepcion, "status", None)
        if status is None:
            status = getattr(getattr(excepcion, "response", None), "status", None)

        if isinstance(status, int):
            return 500 <= status <= 599

        if isinstance(excepcion, (asyncio.TimeoutError, ConnectionError)):
            return True

        if isinstance(excepcion, OSError) and not isinstance(excepcion, ValueError):
            return True

        nombre = type(excepcion).__name__.lower()
        return "timeout" in nombre or "connection" in nombre

    def _registrar_exito(self) -> None:
        self._fallos_consecutivos = 0
        self._estado = EstadoCircuito.CERRADO
        self._tiempo_apertura = None
        self._probe_en_curso = False

    def _registrar_fallo(self) -> None:
        if self._estado == EstadoCircuito.SEMIABIERTO:
            self._abrir()
            return

        self._fallos_consecutivos += 1
        if self._fallos_consecutivos >= self._umbral_fallos:
            self._abrir()

    def _abrir(self) -> None:
        self._estado = EstadoCircuito.ABIERTO
        self._tiempo_apertura = time.monotonic()
        self._probe_en_curso = False

    def _cerrar_si_es_coro(self, posible_coro) -> None:
        if inspect.iscoroutine(posible_coro):
            posible_coro.close()

    async def ejecutar(self, coro):
        estado_actual = self.estado

        if estado_actual == EstadoCircuito.ABIERTO:
            self._cerrar_si_es_coro(coro)
            raise CircuitOpenError(self._tiempo_restante())

        if estado_actual == EstadoCircuito.SEMIABIERTO:
            async with self._lock:
                if self._probe_en_curso:
                    self._cerrar_si_es_coro(coro)
                    raise CircuitOpenError(self._timeout_apertura)
                self._probe_en_curso = True

            try:
                resultado = await coro
            except Exception as exc:
                async with self._lock:
                    self._probe_en_curso = False
                    if self._es_fallo_servidor(exc):
                        self._registrar_fallo()
                raise

            async with self._lock:
                self._registrar_exito()
            return resultado

        try:
            resultado = await coro
        except Exception as exc:
            if self._es_fallo_servidor(exc):
                self._registrar_fallo()
            raise

        self._registrar_exito()
        return resultado
