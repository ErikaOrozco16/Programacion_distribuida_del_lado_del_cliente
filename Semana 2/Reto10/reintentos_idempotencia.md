# Reto IA 10 - Reintentos e idempotencia

## Implementacion

El modulo `retry.py` contiene el decorador `with_retry`. Reintenta automaticamente cuando ocurre un `TimeoutError` o un `HttpServerError` 5xx, usa exponential backoff, acepta limite maximo de reintentos, agrega jitter configurable y registra cada reintento mediante `RetryEvent`.

## Tiempos medidos en pruebas

| Escenario | Esperas observadas |
| --- | --- |
| Dos errores 503 y luego exito | `1s`, `2s` |
| Falla permanente con maximo 2 reintentos | `1s`, `2s` y luego error |
| Timeout transitorio | `0.5s` y luego exito |
| Jitter de 20% con valor aleatorio 0.5 | `11s` sobre base de `10s` |
| Tope maximo de espera | `10s`, `15s`, `15s` |

## Cuando es seguro reintentar

Es seguro reintentar automaticamente operaciones idempotentes cuando el fallo parece transitorio: `GET`, `PUT` y algunos `DELETE`. Si se repite la misma peticion, el estado final esperado no cambia de forma peligrosa.

## Cuando no conviene reintentar

No conviene reintentar errores 4xx porque indican que la peticion esta mal formada, no autorizada o apunta a un recurso inexistente. Tampoco conviene reintentar automaticamente `POST /productos` sin una llave de idempotencia, porque un timeout podria ocultar que el producto si fue creado y el reintento generaria duplicados.

## Por que backoff y jitter

Exponential backoff evita golpear al servidor inmediatamente despues de una falla. Jitter separa los reintentos de muchos clientes para reducir el riesgo de que todos vuelvan a intentar al mismo tiempo y provoquen otra sobrecarga.
