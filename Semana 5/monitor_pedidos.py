"""
DECISIONES DE DISENO - Cliente EcoMarket / Simulacro Semana 5
=============================================================

TIMEOUT_HTTP = 10s
  Trade-off: si es muy corto, el cliente cortara respuestas lentas legitimas;
  si es muy largo, la interfaz puede quedar esperando un servidor caido.
  Decision: 10s permite detectar fallos sin congelar el flujo del cliente.

INTERVALO_BASE = 5s
  Trade-off: un intervalo menor da datos mas frescos, pero consume mas bateria,
  CPU y conexiones; uno mayor reduce consumo, pero aumenta la latencia visible.
  Decision: 5s da sensacion de monitoreo activo y el backoff reduce el costo
  cuando no hay cambios.

REINTENTOS_MAX = 3
  Trade-off: mas reintentos absorben fallos temporales, pero retrasan el aviso
  al usuario cuando el servicio realmente no esta disponible.
  Decision: 3 intentos equilibran resiliencia y respuesta clara al usuario.

TIPO_DE_POLLING = short polling con ETag
  Trade-off: no tiene latencia casi cero como long polling, pero evita mantener
  conexiones abiertas por mucho tiempo en clientes moviles o redes inestables.
  Decision: short polling con ETag y backoff es suficiente para este monitor.

JITTER_EN_BACKOFF
  Decision: se agrega una pequena variacion aleatoria al intervalo para que mi
  cliente no reintente exactamente al mismo tiempo que otras instancias durante
  una falla compartida.
"""

from __future__ import annotations

import asyncio
import random
from abc import ABC, abstractmethod
from typing import Any

import aiohttp


BASE_URL = "http://localhost:8000"
TIMEOUT_HTTP = 10
INTERVALO_BASE = 5
INTERVALO_MAX = 60
FACTOR_BACKOFF = 1.5
REINTENTOS_MAX = 3


class Observador(ABC):
    @abstractmethod
    def actualizar(self, datos: dict[str, Any]) -> None:
        """Recibe datos nuevos del monitor."""


class Observable:
    def __init__(self) -> None:
        self._observadores: list[Observador] = []

    def suscribir(self, observador: Observador) -> None:
        if observador not in self._observadores:
            self._observadores.append(observador)

    def desuscribir(self, observador: Observador) -> None:
        if observador in self._observadores:
            self._observadores.remove(observador)

    def _notificar(self, datos: dict[str, Any]) -> None:
        for observador in list(self._observadores):
            try:
                observador.actualizar(datos)
            except Exception as error:
                print(
                    f"[OBSERVABLE] Error en {type(observador).__name__}: {error}"
                )


class MonitorPedidos(Observable):
    def __init__(self, base_url: str, sesion: aiohttp.ClientSession) -> None:
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.sesion = sesion
        self.ejecutando = False
        self.intervalo_actual = INTERVALO_BASE
        self.ultimo_etag: str | None = None
        self.ultimo_estado: dict[str, Any] | None = None
        self.fallos_consecutivos = 0

    async def _consultar_pedidos(self) -> dict[str, Any] | None:
        url = f"{self.base_url}/pedidos"
        headers = {}
        if self.ultimo_etag:
            headers["If-None-Match"] = self.ultimo_etag

        try:
            timeout = aiohttp.ClientTimeout(total=TIMEOUT_HTTP)
            async with self.sesion.get(url, headers=headers, timeout=timeout) as resp:
                if resp.status == 304:
                    print("[HTTP 304] Sin cambios; no se notifican observadores.")
                    self.fallos_consecutivos = 0
                    return None

                if 200 <= resp.status < 300:
                    datos = await self._leer_json_seguro(resp)
                    if not self._respuesta_valida(datos):
                        print("[ERROR] Respuesta 2xx con estructura invalida.")
                        return None

                    self.ultimo_etag = resp.headers.get("ETag", self.ultimo_etag)
                    self.fallos_consecutivos = 0
                    return datos

                if 400 <= resp.status < 500:
                    detalle = await resp.text()
                    print(f"[HTTP {resp.status}] Error del cliente: {detalle}")
                    return None

                if 500 <= resp.status < 600:
                    self.fallos_consecutivos += 1
                    print(f"[HTTP {resp.status}] Servicio no disponible temporalmente.")
                    return None

                print(f"[HTTP {resp.status}] Estado no esperado.")
                return None

        except asyncio.TimeoutError:
            self.fallos_consecutivos += 1
            print("[TIMEOUT] El servidor tardo mas que el limite configurado.")
            return None
        except aiohttp.ClientError as error:
            self.fallos_consecutivos += 1
            print(f"[RED] No fue posible contactar el servidor: {error}")
            return None
        except Exception as error:
            self.fallos_consecutivos += 1
            print(f"[ERROR] Fallo inesperado controlado: {error}")
            return None

    async def iniciar(self) -> None:
        self.ejecutando = True

        while self.ejecutando:
            datos = await self._consultar_pedidos()

            if datos is not None and datos != self.ultimo_estado:
                self.ultimo_estado = datos
                self.intervalo_actual = INTERVALO_BASE
                self._notificar(datos)
            else:
                self.intervalo_actual = self._calcular_backoff_con_jitter()

            if self.fallos_consecutivos >= REINTENTOS_MAX:
                print("[ESTADO] Servicio no disponible; se mantiene polling con backoff.")

            await asyncio.sleep(self.intervalo_actual)

    def detener(self) -> None:
        self.ejecutando = False

    async def _leer_json_seguro(self, resp: aiohttp.ClientResponse) -> Any:
        content_type = resp.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            print(f"[ERROR] Content-Type inesperado: {content_type}")
            return None
        return await resp.json()

    def _respuesta_valida(self, datos: Any) -> bool:
        if not isinstance(datos, dict):
            return False
        pedidos = datos.get("pedidos")
        if not isinstance(pedidos, list):
            return False
        return all(isinstance(pedido, dict) for pedido in pedidos)

    def _calcular_backoff_con_jitter(self) -> float:
        base = min(self.intervalo_actual * FACTOR_BACKOFF, INTERVALO_MAX)
        jitter = random.uniform(0, base * 0.2)
        return min(base + jitter, INTERVALO_MAX)


class ObservadorPedidosUI(Observador):
    def actualizar(self, datos: dict[str, Any]) -> None:
        pedidos = datos.get("pedidos", [])
        print("\n--- PEDIDOS ---")
        if not pedidos:
            print("No hay pedidos para mostrar.")
            return

        for pedido in pedidos:
            print(
                f"{pedido.get('id', 'N/A')} | "
                f"{pedido.get('cliente', 'Sin cliente')} | "
                f"${pedido.get('total', 0):.2f} | "
                f"{pedido.get('status', 'SIN_ESTADO')}"
            )


class ObservadorPedidosCriticos(Observador):
    def actualizar(self, datos: dict[str, Any]) -> None:
        pedidos = datos.get("pedidos", [])
        retrasados = [
            pedido for pedido in pedidos if pedido.get("status") == "RETRASADO"
        ]

        if not retrasados:
            return

        print("\n[ALERTA] Pedidos retrasados detectados:")
        for pedido in retrasados:
            print(f"- {pedido.get('id', 'N/A')} de {pedido.get('cliente', 'N/A')}")


async def main() -> None:
    async with aiohttp.ClientSession() as sesion:
        monitor = MonitorPedidos(BASE_URL, sesion)
        monitor.suscribir(ObservadorPedidosUI())
        monitor.suscribir(ObservadorPedidosCriticos())

        tarea = asyncio.create_task(monitor.iniciar())
        try:
            await asyncio.sleep(30)
        finally:
            monitor.detener()
            await tarea


if __name__ == "__main__":
    asyncio.run(main())
