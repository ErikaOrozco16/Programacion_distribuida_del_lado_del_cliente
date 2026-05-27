"""Extension opcional del Reto 5: EventRouter con prioridades por handler."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


Handler = Callable[[Any], None]


@dataclass(order=True)
class HandlerPrioritizado:
    prioridad: int
    orden: int
    fn: Handler


class EventRouterPrioritizado:
    """
    Decorador de comportamiento compatible con EventRouter.

    Mantiene registrar(tipo, fn) funcionando sin prioridad explicita y agrega
    registrar(tipo, fn, prioridad=N). Elegi decorador conceptual porque el
    ClienteSSEMultiplex no debe conocer prioridades: sigue llamando
    despachar(tipo, datos) igual que antes.
    """

    def __init__(self) -> None:
        self.handlers: dict[str, list[HandlerPrioritizado]] = {}
        self._orden = 0

    def registrar(self, tipo: str, fn: Handler, prioridad: int = 0) -> None:
        self._orden += 1
        item = HandlerPrioritizado(prioridad=-prioridad, orden=self._orden, fn=fn)
        self.handlers.setdefault(tipo, []).append(item)

    def desregistrar(self, tipo: str, fn: Handler) -> None:
        if tipo not in self.handlers:
            return
        self.handlers[tipo] = [item for item in self.handlers[tipo] if item.fn is not fn]

    def despachar(self, tipo: str, datos: Any) -> None:
        for item in sorted(self.handlers.get(tipo, [])):
            try:
                item.fn(datos)
            except Exception as exc:
                print(f"[router-prioridad] Handler para '{tipo}' fallo: {exc}")


def demo() -> None:
    router = EventRouterPrioritizado()

    def registrar_salida(nombre: str) -> Handler:
        return lambda datos: print(f"{nombre}: {datos}")

    router.registrar("stock-critico", registrar_salida("auditoria"), prioridad=5)
    router.registrar("stock-critico", registrar_salida("alerta visual"), prioridad=10)
    router.registrar("stock-critico", registrar_salida("bitacora"))  # compatibilidad
    router.despachar("stock-critico", {"producto_id": "P019", "stock_actual": 2})


if __name__ == "__main__":
    demo()
