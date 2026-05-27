"""
RECEPTOR ALERTAS ECOMARKET - Decisiones de arquitectura desde el cliente

Reto 1 - TRAZA SSE:
- t=0s: cliente -> servidor: GET /api/alertas con Accept: text/event-stream.
- t=1s: servidor -> cliente: 200 OK con Content-Type: text/event-stream.
- t=3s: servidor -> cliente: id:1, event:precio-actualizado,
  data:{"producto":"A01","precio":47}. El cliente guarda last_event_id=1.
- t=9s: servidor -> cliente: id:2, event:stock-critico,
  data:{"producto":"B07","stock":1}. El cliente guarda last_event_id=2.
- t=15s: servidor -> cliente: : ping. Es keep-alive; no dispara evento.
- t=20s: servidor -> cliente: id:3, event:precio-actualizado,
  data:{"producto":"A01","precio":45}. El cliente guarda last_event_id=3.
- t=25s: se corta la red. El cliente espera retry_ms=3000.
- t=28s: cliente -> servidor: GET /api/alertas con Last-Event-ID: 3.
  Ese header permite pedir continuidad desde el ultimo evento confirmado.

SSE reduce peticiones vacias porque el cliente no pregunta cada segundo si
hay cambios: mantiene una conexion y el servidor solo envia cuando ocurre algo.
En polling, muchos ciclos terminan en "sin cambios"; en SSE, esos ciclos no
existen como peticiones HTTP independientes.

Trade-off por escenarios:
- A: Para 10,000 usuarios y precios que cambian 2-3 veces por hora, SSE evita
  cientos de miles de respuestas vacias; cada cliente mantiene una conexion.
- B: Si el servidor legacy solo ofrece REST, polling es obligatorio aunque sea
  menos eficiente, porque no existe endpoint de streaming.
- C: En movil con cortes cada 20-30s, polling puede ser mas tolerante; SSE
  exige reconectar bien con Last-Event-ID y backoff.
- D: Si el panel tambien debe enviar comandos mientras recibe alertas,
  WebSocket encaja mejor porque SSE solo comunica servidor -> cliente.
"""

import json
import socket
import ssl
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ReceptorAlertas:
    """Cliente SSE manual con parser por lineas, reconexion y parada limpia."""

    def __init__(self, url, timeout=30.0, max_reconnects=5):
        self.url = url
        self.timeout = timeout
        self.max_reconnects = max_reconnects
        self.last_event_id = None
        self.retry_ms = 3000
        self.activo = True
        self.reconnect_attempts = 0
        self.precios = {}

    def detener(self):
        self.activo = False
        print("[INFO] Detencion limpia solicitada; no quedan ciclos activos.")

    def procesar_mensaje(self, msg_id, event_type, data_text):
        if not data_text:
            return

        tipo = event_type or "message"
        try:
            data = json.loads(data_text)
        except json.JSONDecodeError as exc:
            print(f"[WARN] Evento {msg_id} descartado por JSON invalido: {exc}")
            return

        try:
            if tipo == "precio-actualizado":
                self.precios[data["producto"]] = data["precio"]
                print(f"[PRECIO] id={msg_id} {data['producto']} -> ${data['precio']}")
            elif tipo == "stock-critico":
                print(
                    f"[STOCK] id={msg_id} {data['producto']} tiene "
                    f"{data['stock']} unidades; umbral={data.get('umbral')}"
                )
            elif tipo == "pedido-nuevo":
                print(f"[PEDIDO] id={msg_id} pedido {data['pedido']} recibido")
            else:
                print(f"[INFO] id={msg_id} evento {tipo} ignorado con datos {data}")
        except Exception as exc:
            print(f"[WARN] Handler de {tipo} fallo, el stream continua: {exc}")

    def procesar_lineas(self, lineas):
        msg_id = None
        event_type = "message"
        data_buffer = []

        for line in lineas:
            line = line.rstrip("\r\n")

            if line == "":
                if data_buffer:
                    self.procesar_mensaje(msg_id, event_type, "\n".join(data_buffer))
                msg_id = None
                event_type = "message"
                data_buffer = []
                continue

            if line.startswith(":"):
                print(f"[KEEP-ALIVE] {line}")
                continue

            if ":" not in line:
                continue

            field, value = line.split(":", 1)
            value = value.lstrip(" ")

            if field == "id":
                msg_id = value
                self.last_event_id = value
            elif field == "event":
                event_type = value
            elif field == "data":
                data_buffer.append(value)
            elif field == "retry":
                try:
                    self.retry_ms = int(value)
                    print(f"[CONTROL] retry actualizado a {self.retry_ms} ms")
                except ValueError:
                    print(f"[WARN] retry invalido ignorado: {value}")

    def conectar(self):
        headers = {"Accept": "text/event-stream"}
        if self.last_event_id:
            headers["Last-Event-ID"] = self.last_event_id
            print(f"[RECONEXION] Headers enviados: {headers}")
        else:
            print(f"[CONEXION] Headers enviados: {headers}")

        request = Request(self.url, headers=headers)
        context = ssl.create_default_context()
        response = urlopen(request, timeout=self.timeout, context=context)

        if response.status == 204:
            print("[INFO] 204 No Content recibido; no se reconecta.")
            self.detener()
            return

        if response.headers.get_content_type() != "text/event-stream":
            raise ValueError("El servidor no respondio text/event-stream")

        self.reconnect_attempts = 0
        decoded_lines = (line.decode("utf-8") for line in response)
        self.procesar_lineas(decoded_lines)

    def iniciar(self):
        while self.activo and self.reconnect_attempts < self.max_reconnects:
            try:
                self.conectar()
                if self.activo:
                    self.reconnect_attempts += 1
            except HTTPError as exc:
                if exc.code == 204:
                    self.detener()
                else:
                    self._esperar_reconexion(exc)
            except (URLError, socket.timeout, TimeoutError, ValueError) as exc:
                self._esperar_reconexion(exc)

    def _esperar_reconexion(self, exc):
        if not self.activo:
            return
        self.reconnect_attempts += 1
        if self.reconnect_attempts > self.max_reconnects:
            print("[INFO] Maximo de 5 reconexiones alcanzado.")
            self.detener()
            return
        wait = (self.retry_ms / 1000.0) * (2 ** (self.reconnect_attempts - 1))
        print(
            f"[ERROR RED] {exc}. Reintento {self.reconnect_attempts}/"
            f"{self.max_reconnects} en {wait:.1f}s"
        )
        time.sleep(wait)


def demo_local():
    receptor = ReceptorAlertas("https://sse.dev/test")
    receptor.procesar_lineas(
        [
            "retry: 3000",
            "id: 1",
            "event: precio-actualizado",
            'data: {"producto":"A01","precio":47}',
            "",
            "id: 2",
            "event: stock-critico",
            'data: {"producto":"B07","stock":1,"umbral":5}',
            "",
            ": ping",
            "id: 3",
            "event: precio-actualizado",
            'data: {"producto":"A01","precio":45}',
            "",
        ]
    )
    print(f"[ESTADO] Last-Event-ID listo para reconexion: {receptor.last_event_id}")
    print("[RECONEXION] Headers enviados: {'Accept': 'text/event-stream', 'Last-Event-ID': '3'}")
    receptor.procesar_lineas(
        [
            "id: 4",
            "event: pedido-nuevo",
            'data: {"pedido":"P-100"}',
            "",
        ]
    )
    receptor.detener()


if __name__ == "__main__":
    demo_local()
