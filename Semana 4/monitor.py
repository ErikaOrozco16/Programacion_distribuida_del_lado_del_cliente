"""
DECISIONES DE DISENO - Monitor de Inventario EcoMarket
======================================================

INTERVALO_BASE = 5s
  El inventario no necesita reaccionar en milisegundos. Cinco segundos dan
  una respuesta razonable sin saturar al servidor con consultas permanentes.

INTERVALO_MAX = 60s
  El backoff no debe crecer sin limite. Si el sistema lleva varios ciclos sin
  cambios o con errores temporales, el cliente reduce presion, pero aun vuelve
  a revisar dentro de un minuto.

TIMEOUT = 10s
  Un cliente de polling no puede quedarse esperando para siempre. El timeout
  protege el ciclo de eventos del cliente y permite pasar a una decision clara:
  registrar el problema, notificarlo y aplicar backoff.

ETag
  Cuando el servidor responde 304, el cliente evita descargar y comparar todo
  el inventario. Esto ahorra ancho de banda y trabajo de parseo.

Observer
  ServicioPolling no conoce directamente a la UI, alertas ni bitacora. Solo
  emite eventos. Asi se pueden agregar o quitar observadores sin tocar el ciclo
  de polling.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


Callback = Callable[[Any], None]


class Observable:
    def __init__(self) -> None:
        self._observadores: dict[str, list[Callback]] = {}

    def suscribir(self, evento: str, callback: Callback) -> None:
        self._observadores.setdefault(evento, []).append(callback)

    def desuscribir(self, evento: str, callback: Callback) -> None:
        if evento not in self._observadores:
            return
        try:
            self._observadores[evento].remove(callback)
        except ValueError:
            pass

    def notificar(self, evento: str, datos: Any) -> None:
        for callback in list(self._observadores.get(evento, [])):
            try:
                callback(datos)
            except Exception as exc:
                print(f"[WARN] Observador '{callback.__name__}' fallo: {exc}")


@dataclass
class RespuestaHTTP:
    status: int
    headers: dict[str, str]
    body: Any | None = None


class TransporteHTTP:
    async def get_json(self, url: str, headers: dict[str, str], timeout: int) -> RespuestaHTTP:
        return await asyncio.to_thread(self._get_json_sync, url, headers, timeout)

    def _get_json_sync(self, url: str, headers: dict[str, str], timeout: int) -> RespuestaHTTP:
        request = Request(url, headers=headers, method="GET")
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
                content_type = response.headers.get("Content-Type", "")
                if "json" not in content_type:
                    raise ValueError(f"Content-Type inesperado: {content_type}")
                return RespuestaHTTP(
                    status=response.status,
                    headers=dict(response.headers.items()),
                    body=json.loads(raw),
                )
        except HTTPError as exc:
            if exc.code == 304:
                return RespuestaHTTP(status=304, headers=dict(exc.headers.items()))
            if exc.code >= 500:
                return RespuestaHTTP(status=exc.code, headers=dict(exc.headers.items()))
            raise
        except URLError as exc:
            raise TimeoutError(str(exc)) from exc


class ServicioPolling(Observable):
    INTERVALO_BASE = 5.0
    INTERVALO_MAX = 60.0
    TIMEOUT = 10
    FACTOR_SIN_CAMBIOS = 1.5
    FACTOR_ERROR = 2

    def __init__(
        self,
        url: str,
        transporte: TransporteHTTP | None = None,
        intervalo_base: float = INTERVALO_BASE,
    ) -> None:
        super().__init__()
        self.url = url
        self.transporte = transporte or TransporteHTTP()
        self.intervalo_base = intervalo_base
        self.intervalo_actual = intervalo_base
        self.ultimo_etag: str | None = None
        self._activo = False
        self.ciclos = 0

    async def iniciar(self, max_ciclos: int | None = None) -> None:
        self._activo = True
        print(f"Polling iniciado: {self.url}")
        while self._activo:
            await self._consultar()
            if max_ciclos is not None and self.ciclos >= max_ciclos:
                self.detener()
            if self._activo:
                await asyncio.sleep(self.intervalo_actual)
        print("Polling detenido limpiamente.")

    def detener(self) -> None:
        self._activo = False

    async def _consultar(self) -> None:
        self.ciclos += 1
        headers = {"Accept": "application/json"}
        if self.ultimo_etag:
            headers["If-None-Match"] = self.ultimo_etag

        inicio = time.perf_counter()
        print(f"Ciclo #{self.ciclos} | intervalo={self.intervalo_actual:.1f}s")

        try:
            respuesta = await self.transporte.get_json(self.url, headers, self.TIMEOUT)
            duracion_ms = int((time.perf_counter() - inicio) * 1000)
            await self._procesar_respuesta(respuesta, duracion_ms)
        except TimeoutError:
            self.intervalo_actual = min(self.intervalo_actual * self.FACTOR_ERROR, self.INTERVALO_MAX)
            self.notificar("timeout_polling", {"timeout": self.TIMEOUT, "ciclo": self.ciclos})
            print(f"Timeout despues de {self.TIMEOUT}s. Proxima consulta en {self.intervalo_actual:.1f}s")
        except Exception as exc:
            self.intervalo_actual = min(self.intervalo_actual * self.FACTOR_ERROR, self.INTERVALO_MAX)
            self.notificar("error_servidor", {"mensaje": str(exc), "ciclo": self.ciclos})
            print(f"Error controlado: {exc}. Proxima consulta en {self.intervalo_actual:.1f}s")

    async def _procesar_respuesta(self, respuesta: RespuestaHTTP, duracion_ms: int) -> None:
        if respuesta.status == 200:
            self.ultimo_etag = respuesta.headers.get("ETag", self.ultimo_etag)
            self.intervalo_actual = self.intervalo_base
            self.notificar("datos_actualizados", respuesta.body)
            print(f"200 OK en {duracion_ms}ms. Datos notificados. Intervalo reiniciado.")
            return

        if respuesta.status == 304:
            self.intervalo_actual = min(
                self.intervalo_actual * self.FACTOR_SIN_CAMBIOS,
                self.INTERVALO_MAX,
            )
            print(f"304 sin cambios. Proxima consulta en {self.intervalo_actual:.1f}s")
            return

        if respuesta.status >= 500:
            self.intervalo_actual = min(self.intervalo_actual * self.FACTOR_ERROR, self.INTERVALO_MAX)
            self.notificar("error_servidor", {"status": respuesta.status, "ciclo": self.ciclos})
            print(f"Error {respuesta.status}. Proxima consulta en {self.intervalo_actual:.1f}s")
            return

        self.detener()
        self.notificar("error_servidor", {"status": respuesta.status, "ciclo": self.ciclos})
        print(f"Status no recuperable {respuesta.status}. Polling detenido.")


class TransporteSimulado(TransporteHTTP):
    def __init__(self) -> None:
        self._respuestas = [
            RespuestaHTTP(200, {"ETag": '"abc123"'}, {"productos": [{"id": 1, "stock": 4}]}),
            RespuestaHTTP(304, {}),
            RespuestaHTTP(304, {}),
            RespuestaHTTP(503, {}),
            RespuestaHTTP(200, {"ETag": '"def456"'}, {"productos": [{"id": 1, "stock": 2}]}),
        ]
        self._indice = 0

    async def get_json(self, url: str, headers: dict[str, str], timeout: int) -> RespuestaHTTP:
        await asyncio.sleep(0.05)
        respuesta = self._respuestas[self._indice % len(self._respuestas)]
        self._indice += 1
        return respuesta


def actualizar_ui(datos: Any) -> None:
    productos = datos.get("productos", []) if isinstance(datos, dict) else []
    print(f"[UI] Inventario actualizado: {len(productos)} productos.")


def detectar_agotados(datos: Any) -> None:
    productos = datos.get("productos", []) if isinstance(datos, dict) else []
    agotados = [producto for producto in productos if producto.get("stock", 0) == 0]
    print(f"[ALERTA] Productos agotados detectados: {len(agotados)}.")


def registrar_error(datos: Any) -> None:
    print(f"[LOG] Evento de error registrado: {datos}")


async def demo() -> None:
    monitor = ServicioPolling(
        "https://api.ecomarket.local/inventario",
        transporte=TransporteSimulado(),
        intervalo_base=0.1,
    )
    monitor.suscribir("datos_actualizados", actualizar_ui)
    monitor.suscribir("datos_actualizados", detectar_agotados)
    monitor.suscribir("error_servidor", registrar_error)
    monitor.suscribir("timeout_polling", registrar_error)

    await monitor.iniciar(max_ciclos=5)


if __name__ == "__main__":
    asyncio.run(demo())
