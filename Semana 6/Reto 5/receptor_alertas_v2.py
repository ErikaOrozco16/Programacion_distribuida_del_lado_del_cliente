import json
from datetime import datetime


class Observable:
    def __init__(self):
        self._suscriptores = {}

    def suscribir(self, tipo_evento, callback):
        self._suscriptores.setdefault(tipo_evento, []).append(callback)

    def notificar(self, tipo_evento, evento):
        for callback in self._suscriptores.get(tipo_evento, []):
            try:
                callback(evento)
            except Exception as exc:
                print(f"[WARN] Suscriptor fallo en {tipo_evento}: {exc}")


class ReceptorAlertas:
    """Receptor SSE que compone Observable para separar red y despacho."""

    def __init__(self):
        self.eventos = Observable()
        self.last_event_id = None
        self.tabla_precios = {}
        self.auditoria = []

    def suscribir(self, tipo_evento, callback):
        self.eventos.suscribir(tipo_evento, callback)

    def procesar_mensaje(self, msg_id, tipo_evento, data_text):
        self.last_event_id = msg_id
        try:
            data = json.loads(data_text)
        except json.JSONDecodeError:
            data = {"raw": data_text}

        evento = {
            "id": msg_id,
            "tipo": tipo_evento or "message",
            "data": data,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
        self.eventos.notificar(evento["tipo"], evento)

    def reproducir_demo(self, eventos):
        for msg_id, tipo_evento, data in eventos:
            self.procesar_mensaje(msg_id, tipo_evento, json.dumps(data))


def crear_actualizador_precios_ui(tabla_precios):
    def actualizador(evento):
        data = evento["data"]
        tabla_precios[data["producto"]] = data["precio"]
        print(f"[UI] {data['producto']} actualizado a ${data['precio']}")

    return actualizador


def alerta_stock_critico(evento):
    data = evento["data"]
    urgencia = "alta" if data["stock"] <= 2 else "media"
    print(f"[ALERTA] Stock {urgencia}: {data['producto']} tiene {data['stock']}")


def crear_registrador_auditoria(auditoria):
    def registrar(evento):
        auditoria.append(
            {
                "timestamp": evento["timestamp"],
                "id": evento["id"],
                "tipo": evento["tipo"],
                "data": evento["data"],
            }
        )
        print(f"[AUDITORIA] id={evento['id']} tipo={evento['tipo']}")

    return registrar


def suscriptor_que_falla(evento):
    if evento["id"] == "6":
        raise RuntimeError("fallo simulado de UI")


def main():
    receptor = ReceptorAlertas()

    receptor.suscribir(
        "precio-actualizado", crear_actualizador_precios_ui(receptor.tabla_precios)
    )
    receptor.suscribir("precio-actualizado", crear_registrador_auditoria(receptor.auditoria))
    receptor.suscribir("precio-actualizado", suscriptor_que_falla)
    receptor.suscribir("stock-critico", alerta_stock_critico)
    receptor.suscribir("stock-critico", crear_registrador_auditoria(receptor.auditoria))

    eventos_demo = [
        ("1", "precio-actualizado", {"producto": "A01", "precio": 47}),
        ("2", "stock-critico", {"producto": "B07", "stock": 1, "umbral": 5}),
        ("3", "precio-actualizado", {"producto": "A01", "precio": 45}),
        ("4", "precio-actualizado", {"producto": "C12", "precio": 89}),
        ("5", "stock-critico", {"producto": "D03", "stock": 3, "umbral": 4}),
        ("6", "precio-actualizado", {"producto": "A01", "precio": 44}),
        ("7", "stock-critico", {"producto": "B07", "stock": 0, "umbral": 5}),
        ("8", "precio-actualizado", {"producto": "E20", "precio": 15}),
        ("9", "precio-actualizado", {"producto": "C12", "precio": 86}),
        ("10", "stock-critico", {"producto": "F09", "stock": 2, "umbral": 6}),
    ]

    receptor.reproducir_demo(eventos_demo)
    print(f"[RESUMEN] precios={receptor.tabla_precios}")
    print(f"[RESUMEN] registros_auditoria={len(receptor.auditoria)}")
    print(f"[RESUMEN] ultimo_id={receptor.last_event_id}")


if __name__ == "__main__":
    main()
