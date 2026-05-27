"""
ClienteRobusto integra CircuitBreaker + TokenManager simulado.

La demo ejecuta cuatro fases:
  1. operacion normal con tres peticiones exitosas;
  2. fallos 503 hasta abrir el circuito;
  3. fallo rapido mientras el circuito esta abierto;
  4. espera del timeout y recuperacion en estado semiabierto.
"""

import asyncio
from datetime import datetime

from circuit_breaker import CircuitBreaker, CircuitOpenError, EstadoCircuito, HttpError


class TokenManager:
    def __init__(self):
        self.access_token = "token-inicial"
        self.refresh_count = 0

    async def obtener_access_token(self) -> str:
        return self.access_token

    async def refresh_access_token(self) -> str:
        self.refresh_count += 1
        self.access_token = f"token-renovado-{self.refresh_count}"
        return self.access_token


class ServidorMockEcoMarket:
    def __init__(self):
        self.modo = "normal"
        self._peticiones_recibidas = 0

    @property
    def peticiones_recibidas(self) -> int:
        return self._peticiones_recibidas

    async def get_inventario(self, token: str):
        self._peticiones_recibidas += 1
        await asyncio.sleep(0.01)

        if self.modo == "fallo_503":
            raise HttpError(503, "Service Unavailable")
        if self.modo == "timeout":
            raise asyncio.TimeoutError("Tiempo de espera agotado")
        if self.modo == "auth":
            raise HttpError(401, "Unauthorized")

        return {
            "productos": 42,
            "token_usado": token,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }


class ClienteRobusto:
    def __init__(self, servidor: ServidorMockEcoMarket):
        self.servidor = servidor
        self.token_manager = TokenManager()
        self.breaker = CircuitBreaker(
            umbral_fallos=3,
            timeout_apertura=2.0,
            nombre="EcoMarketInventario",
        )
        self._observadores_estado = []

    def al_cambiar_estado(self, callback):
        self._observadores_estado.append(callback)

    def _notificar_si_cambio(self, estado_anterior: EstadoCircuito) -> None:
        estado_actual = self.breaker.estado
        if estado_actual == estado_anterior:
            return
        for callback in self._observadores_estado:
            callback(estado_anterior, estado_actual)

    async def obtener_inventario(self):
        token = await self.token_manager.obtener_access_token()
        estado_anterior = self.breaker.estado
        try:
            return await self.breaker.ejecutar(self.servidor.get_inventario(token))
        except HttpError as exc:
            if exc.status == 401:
                await self.token_manager.refresh_access_token()
            raise
        finally:
            self._notificar_si_cambio(estado_anterior)


def log(mensaje: str) -> None:
    print(f"{datetime.now().isoformat(timespec='seconds')} | {mensaje}")


async def demo_resiliencia():
    mock = ServidorMockEcoMarket()
    cliente = ClienteRobusto(mock)

    cliente.al_cambiar_estado(
        lambda antes, despues: log(
            f"UI notificada: circuito {antes.name} -> {despues.name}"
        )
    )

    log("FASE 1 normal: 3 peticiones exitosas")
    for i in range(1, 4):
        resultado = await cliente.obtener_inventario()
        log(
            f"normal #{i}: OK productos={resultado['productos']} "
            f"estado={cliente.breaker.estado.name} "
            f"servidor={mock.peticiones_recibidas}"
        )

    log("FASE 2 fallo_503: se acumulan fallos hasta abrir")
    mock.modo = "fallo_503"
    for i in range(1, 5):
        try:
            await cliente.obtener_inventario()
        except CircuitOpenError as exc:
            log(
                f"fallo #{i}: CircuitOpenError inmediato "
                f"restante={exc.tiempo_restante:.1f}s "
                f"estado={cliente.breaker.estado.name} "
                f"servidor={mock.peticiones_recibidas}"
            )
        except HttpError as exc:
            log(
                f"fallo #{i}: HTTP {exc.status} "
                f"contador_fallos={cliente.breaker._fallos_consecutivos} "
                f"estado={cliente.breaker.estado.name} "
                f"servidor={mock.peticiones_recibidas}"
            )

    log("FASE 3 abierto: una peticion falla rapido sin tocar servidor")
    antes = mock.peticiones_recibidas
    try:
        await cliente.obtener_inventario()
    except CircuitOpenError as exc:
        log(
            f"abierto: CircuitOpenError restante={exc.tiempo_restante:.1f}s "
            f"servidor_antes={antes} servidor_despues={mock.peticiones_recibidas}"
        )

    log("FASE 4 recuperacion: espera timeout y prueba semiabierta")
    await asyncio.sleep(cliente.breaker._timeout_apertura + 0.1)
    log(f"despues del timeout estado={cliente.breaker.estado.name}")
    mock.modo = "normal"
    resultado = await cliente.obtener_inventario()
    log(
        f"recuperacion: OK productos={resultado['productos']} "
        f"estado={cliente.breaker.estado.name} "
        f"contador_fallos={cliente.breaker._fallos_consecutivos} "
        f"servidor={mock.peticiones_recibidas}"
    )

    log("Verificacion 401: los 4xx no abren el circuito")
    mock.modo = "auth"
    for _ in range(cliente.breaker._umbral_fallos + 5):
        try:
            await cliente.obtener_inventario()
        except HttpError:
            pass
    log(
        f"401 repetido: estado={cliente.breaker.estado.name} "
        f"contador_fallos={cliente.breaker._fallos_consecutivos} "
        f"refresh_token={cliente.token_manager.refresh_count}"
    )


if __name__ == "__main__":
    asyncio.run(demo_resiliencia())
