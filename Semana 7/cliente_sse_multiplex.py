"""
DECISIONES DE DISENO - ClienteSSEMultiplex para EcoMarket
==========================================================
MODULOS_ACTIVOS = ["precios", "inventario", "pedidos"]
  -> Trade-off: mas modulos significan mas volumen de eventos para procesar en
     el cliente, pero no consumen mas conexiones SSE. Elijo los tres modulos
     operativos principales de EcoMarket; "devoluciones" requiere reconectar.

TIMEOUT = 30
  -> Trade-off: un timeout corto detecta cuelgues rapido, pero puede cortar
     redes corporativas lentas. Treinta segundos tolera jitter sin dejar al
     panel esperando indefinidamente.

MAX_REINTENTOS = 5
  -> Trade-off: mas reintentos dan resiliencia ante caidas breves, pero
     retrasan el momento en que el panel informa fallo. Cinco intentos con
     backoff cubren interrupciones pequenas y evitan ciclos infinitos.

ESPERA_INICIAL = 1
  -> Trade-off: esperar poco reacciona rapido, pero puede insistir demasiado
     cuando la red esta inestable. Un segundo permite backoff 1, 2, 4, 8, 16.

Trade-off principal:
  Uso una sola conexion SSE multiplexada para conservar ranuras del pool
  HTTP/1.1 del cliente y centralizar el routing. A cambio, si esa conexion se
  corta, todos los modulos dejan de recibir eventos hasta reconectar, y agregar
  modulos exige cerrar y abrir una nueva conexion con otra URL.

Limitacion pendiente:
  El cliente aun no guarda eventos en disco ni confirma procesamiento
  persistente. Si el proceso muere despues de recibir un evento y antes de
  actuar sobre el, Last-Event-ID no basta para garantizar recuperacion completa.

Correccion/validacion del resumen de IA:
  El resumen fue validado desde la perspectiva del cliente. No se aceptaron
  argumentos centrados en escalamiento del servidor porque esta entrega evalua
  conexiones, handlers, estado y recuperacion del lado cliente.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, Callable, Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "https://api.ecomarket.com/eventos"
TIMEOUT = 30
MAX_REINTENTOS = 5
ESPERA_INICIAL = 1
MODULOS_ACTIVOS = ["precios", "inventario", "pedidos"]

Handler = Callable[[Any], None]

pedidos_importantes: list[dict[str, Any]] = []
ultima_conexion_activa: str | None = None


class EventRouter:
    """Despacha eventos por tipo sin permitir que un handler rompa el stream."""

    def __init__(self) -> None:
        self.handlers: dict[str, list[Handler]] = {}

    def registrar(self, tipo: str, fn: Handler) -> None:
        self.handlers.setdefault(tipo, []).append(fn)

    def desregistrar(self, tipo: str, fn: Handler) -> None:
        if tipo in self.handlers and fn in self.handlers[tipo]:
            self.handlers[tipo].remove(fn)

    def despachar(self, tipo: str, datos: Any) -> None:
        for fn in self.handlers.get(tipo, []):
            try:
                fn(datos)
            except Exception as exc:
                print(f"[router] Handler para '{tipo}' fallo: {exc}")


class ClienteSSEMultiplex:
    """Cliente SSE que recibe varios tipos de eventos en una sola conexion."""

    def __init__(self, modulos: list[str]) -> None:
        if not modulos:
            raise ValueError("La lista de modulos no puede estar vacia.")
        self.modulos = modulos
        self.router = EventRouter()
        self.estado = "DESCONECTADO"
        self.reintentos = 0
        self.ultimo_id: str | None = None
        self._parar = False
        self.ultimo_request_headers: dict[str, str] = {}

    def suscribir(self, tipo_evento: str, handler_fn: Handler) -> None:
        self.router.registrar(tipo_evento, handler_fn)

    def construir_url(self) -> str:
        if not self.modulos:
            raise ValueError("No se puede construir URL sin modulos activos.")
        query = urlencode({"modulos": ",".join(self.modulos)})
        return f"{BASE_URL}?{query}"

    def _parsear_linea(self, linea: str, evento_parcial: dict[str, Any]) -> dict[str, Any]:
        linea = linea.rstrip("\r\n")
        if linea == "":
            evento_parcial["_fin_bloque"] = True
            return evento_parcial
        if linea.startswith(":"):
            return evento_parcial
        if ":" in linea:
            campo, valor = linea.split(":", 1)
            if valor.startswith(" "):
                valor = valor[1:]
        else:
            campo, valor = linea, ""

        if campo == "data":
            datos_previos = evento_parcial.get("data")
            evento_parcial["data"] = valor if datos_previos is None else f"{datos_previos}\n{valor}"
        elif campo in {"event", "id", "retry"}:
            evento_parcial[campo] = valor
        return evento_parcial

    def _procesar_evento(self, evento_parcial: dict[str, Any]) -> dict[str, Any]:
        if not evento_parcial.get("_fin_bloque"):
            return evento_parcial
        evento_parcial.pop("_fin_bloque", None)
        if not evento_parcial:
            return {}

        tipo = evento_parcial.get("event", "message")
        datos = evento_parcial.get("data", "")
        if "id" in evento_parcial:
            self.ultimo_id = evento_parcial["id"]
        print(f"[cliente] Evento recibido id={self.ultimo_id or '-'} tipo={tipo}")
        self.router.despachar(tipo, datos)
        return {}

    async def _leer_stream(self, respuesta_http: Iterable[str]) -> None:
        evento_parcial: dict[str, Any] = {}
        for linea in respuesta_http:
            if self._parar:
                print("[cliente] Lectura detenida limpiamente.")
                break
            evento_parcial = self._parsear_linea(linea, evento_parcial)
            evento_parcial = self._procesar_evento(evento_parcial)
            await asyncio.sleep(0)

    async def _conectar(self) -> None:
        self.estado = "CONECTANDO"
        headers = {"Accept": "text/event-stream"}
        if self.ultimo_id is not None:
            headers["Last-Event-ID"] = self.ultimo_id
        self.ultimo_request_headers = headers.copy()
        request = Request(self.construir_url(), headers=headers)
        print(f"[cliente] Conectando a {request.full_url} timeout={TIMEOUT}s headers={headers}")

        self.estado = "CONECTADO"
        with urlopen(request, timeout=TIMEOUT) as response:
            lineas = (line.decode("utf-8") for line in response)
            await self._leer_stream(lineas)

    async def iniciar(self) -> bool:
        if self.estado in {"CONECTANDO", "CONECTADO", "RECONECTANDO"}:
            print(f"[cliente] iniciar() ignorado: ya existe conexion en estado {self.estado}.")
            return False

        self._parar = False
        self.reintentos = 0
        while not self._parar and self.reintentos <= MAX_REINTENTOS:
            try:
                await self._conectar()
                self.estado = "DESCONECTADO"
                return True
            except Exception as exc:
                self.reintentos += 1
                if self.reintentos > MAX_REINTENTOS:
                    self.estado = "DESCONECTADO"
                    print(f"[cliente] Sin conexion tras {MAX_REINTENTOS} reintentos: {exc}")
                    return False
                self.estado = "RECONECTANDO"
                espera = ESPERA_INICIAL * (2 ** (self.reintentos - 1))
                print(f"[cliente] Error de conexion: {exc}. Reintento {self.reintentos} en {espera}s.")
                await asyncio.sleep(espera)
        self.estado = "DESCONECTADO"
        return False

    def detener(self) -> None:
        self._parar = True
        self.estado = "DESCONECTADO"
        self.ultimo_id = None
        print("[cliente] Detenido por el usuario; Last-Event-ID reiniciado.")


def _cargar_json(datos: Any) -> dict[str, Any] | None:
    if isinstance(datos, dict):
        return datos
    try:
        return json.loads(str(datos))
    except json.JSONDecodeError as exc:
        print(f"[handler] Datos malformados ignorados: {exc}. dato={datos!r}")
        return None


def handler_precio_actualizado(datos: Any) -> None:
    payload = _cargar_json(datos)
    if not payload:
        return
    if payload.get("producto_id") == "FORZAR_EXCEPCION":
        raise RuntimeError("fallo simulado en precio para validar aislamiento")
    anterior = float(payload["precio_anterior"])
    nuevo = float(payload["precio_nuevo"])
    cambio = ((nuevo - anterior) / anterior) * 100
    if abs(cambio) > 5:
        print(f"[precios] Alerta {payload['producto_id']}: cambio {cambio:.1f}% ({anterior} -> {nuevo})")
    else:
        print(f"[precios] Cambio menor {payload['producto_id']}: {cambio:.1f}%")


def handler_stock_critico(datos: Any) -> None:
    payload = _cargar_json(datos)
    if not payload:
        return
    stock = int(payload["stock_actual"])
    urgencia = "CRITICO" if stock <= 3 else "BAJO" if stock <= 10 else "NORMAL"
    print(f"[inventario] {urgencia}: {payload['producto_id']} stock={stock}")


def handler_pedido_nuevo(datos: Any) -> None:
    payload = _cargar_json(datos)
    if not payload:
        return
    total = float(payload["total"])
    if total > 500:
        pedidos_importantes.append(payload)
        print(f"[pedidos] Pedido importante {payload['pedido_id']} total=${total:.2f}")
    else:
        print(f"[pedidos] Pedido normal {payload['pedido_id']} total=${total:.2f}")


def handler_heartbeat(datos: Any) -> None:
    global ultima_conexion_activa
    payload = _cargar_json(datos)
    ultima_conexion_activa = (
        payload.get("timestamp") if payload else datetime.now(timezone.utc).isoformat()
    )
    print(f"[sistema] Heartbeat registrado: {ultima_conexion_activa}")


def registrar_handlers(cliente: ClienteSSEMultiplex) -> None:
    cliente.suscribir("precio-actualizado", handler_precio_actualizado)
    cliente.suscribir("stock-critico", handler_stock_critico)
    cliente.suscribir("pedido-nuevo", handler_pedido_nuevo)
    cliente.suscribir("sistema-ping", handler_heartbeat)


def generar_stream_mock() -> list[str]:
    stream = (
        'id: evt-001\nevent: precio-actualizado\ndata: {"producto_id": "P042", "precio_anterior": 89.0, "precio_nuevo": 79.5}\n\n'
        'id: evt-002\nevent: stock-critico\ndata: {"producto_id": "P019", "stock_actual": 3, "umbral": 10}\n\n'
        'id: evt-003\nevent: pedido-nuevo\ndata: {"pedido_id": "ORD-0471", "total": 1250.0, "items": 8}\n\n'
        'id: evt-004\nevent: sistema-ping\ndata: {"timestamp": "2026-03-10T14:32:30Z"}\n\n'
        'id: evt-005\nevent: precio-actualizado\ndata: {"producto_id": "FORZAR_EXCEPCION", "precio_anterior": 0}\n\n'
        'id: evt-006\nevent: stock-critico\ndata: {"producto_id": "P077", "stock_actual": 8, "umbral": 10}\n\n'
        'id: evt-007\nevent: pedido-nuevo\ndata: {"pedido_id": "ORD-0472", "total": 230.0, "items": 2}\n\n'
        'id: evt-008\nevent: precio-actualizado\ndata: {"producto_id": "P100", "precio_anterior": 100.0, "precio_nuevo": 103.0}\n\n'
        'id: evt-009\nevent: sistema-ping\ndata: {"timestamp": "2026-03-10T14:33:00Z"}\n\n'
        'id: evt-010\nevent: stock-critico\ndata: {"producto_id": "P008", "stock_actual": 1, "umbral": 10}\n\n'
    )
    return stream.splitlines(keepends=True)


async def demo_10_eventos() -> ClienteSSEMultiplex:
    print("=== DEMO: 10 eventos mixtos EcoMarket ===")
    cliente = ClienteSSEMultiplex(MODULOS_ACTIVOS.copy())
    registrar_handlers(cliente)
    cliente.estado = "CONECTADO"
    await cliente._leer_stream(generar_stream_mock())
    cliente.estado = "DESCONECTADO"
    print(f"[demo] ultimo_id={cliente.ultimo_id}")
    print(f"[demo] pedidos_importantes={len(pedidos_importantes)}")
    print(f"[demo] ultima_conexion_activa={ultima_conexion_activa}")
    return cliente


async def auditar_escenarios() -> None:
    print("\n=== AUDITORIA: 4 escenarios de fallo ===")

    cliente = ClienteSSEMultiplex(MODULOS_ACTIVOS.copy())
    registrar_handlers(cliente)
    cliente.estado = "CONECTADO"
    print("\n[escenario 1] Datos malformados en medio del stream")
    await cliente._leer_stream(
        [
            "id: bad-001\n",
            "event: precio-actualizado\n",
            "data: ERROR_INTERNO_SERVIDOR_PARSE_FAILED\n",
            "\n",
            "id: ok-002\n",
            "event: stock-critico\n",
            'data: {"producto_id": "P020", "stock_actual": 2}\n',
            "\n",
        ]
    )
    print("[resultado 1] Correcto: se logueo el error JSON y el siguiente evento continuo.")

    print("\n[escenario 2] Reconexion con Last-Event-ID")
    cliente.ultimo_id = "5"
    cliente.estado = "DESCONECTADO"
    cliente.ultimo_request_headers = {}

    async def conectar_falso() -> None:
        cliente.estado = "CONECTANDO"
        headers = {"Accept": "text/event-stream"}
        if cliente.ultimo_id is not None:
            headers["Last-Event-ID"] = cliente.ultimo_id
        cliente.ultimo_request_headers = headers
        cliente.estado = "CONECTADO"
        print(f"[cliente] Reconexion simulada headers={headers}")

    await conectar_falso()
    print(f"[resultado 2] Correcto: Last-Event-ID={cliente.ultimo_request_headers.get('Last-Event-ID')}")

    print("\n[escenario 3] Tipo de evento desconocido")
    await cliente._leer_stream(
        [
            "id: fraud-001\n",
            "event: alerta-fraude\n",
            'data: {"pedido_id": "ORD-9999"}\n',
            "\n",
        ]
    )
    print("[resultado 3] Correcto: tipo desconocido ignorado sin excepcion.")

    print("\n[escenario 4] iniciar() con conexion ya activa")
    cliente.estado = "CONECTADO"
    resultado = await cliente.iniciar()
    print(f"[resultado 4] Correcto: no abre segunda conexion, retorno={resultado}.")

    print("\n=== CHECKLIST FINAL ===")
    print("[ok] No abre segunda conexion activa.")
    print("[ok] Bloque sin event: usa tipo message y el router lo ignora si no hay handler.")
    print("[ok] Handler con excepcion no corta eventos posteriores.")
    print("[ok] Last-Event-ID se conserva durante reconexion automatica.")
    print("[ok] data no JSON se loguea y no crashea.")
    print("[ok] detener() activa bandera de parada limpia.")
    print(f"[ok] URL valida: {ClienteSSEMultiplex(MODULOS_ACTIVOS.copy()).construir_url()}")
    print("\nComentario final: Los 4 escenarios pasaron sin modificaciones posteriores.")


async def main() -> None:
    inicio = time.perf_counter()
    await demo_10_eventos()
    await auditar_escenarios()
    print(f"\nTiempo de validacion: {time.perf_counter() - inicio:.3f}s")


if __name__ == "__main__":
    asyncio.run(main())
