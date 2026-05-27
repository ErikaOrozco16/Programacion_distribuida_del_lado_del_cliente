# Reto IA 4 - Auditoria del cliente SSE generado por IA

## Error 1: buffer de datos no reiniciado

**Descripcion:** el cliente acumulaba lineas `data:` pero no limpiaba `data_buffer` despues de procesar un mensaje completo.

**Como falla en produccion:** el segundo evento termina mezclado con el primero. Si ambos son JSON, el parser recibe dos objetos pegados y lanza `JSONDecodeError`.

**Invariante violado:** el buffer debe resetearse despues de cada mensaje terminado por linea en blanco.

**Evidencia provocada en terminal:**

```text
[EVENTO 1] data raw: {"producto":"A01","precio":47}
[EVENTO 2] data raw: {"producto":"A01","precio":47}{"producto":"B07","stock":1}
json.decoder.JSONDecodeError: Extra data: line 1 column 32 (char 31)
```

**Fragmento corregido:**

```python
if line == "":
    if data_buffer:
        procesar_mensaje(msg_id, event_type, "\n".join(data_buffer))
    msg_id = None
    event_type = "message"
    data_buffer = []
```

## Error 2: conexion sin timeout

**Descripcion:** el codigo usaba `urlopen(req)` sin `timeout`.

**Como falla en produccion:** ante un servidor colgado o un firewall que no responde, el cliente queda esperando indefinidamente y nunca ejecuta la reconexion.

**Invariante violado:** la conexion inicial debe tener timeout de 30 segundos.

**Evidencia provocada en terminal:**

```text
[CONEXION] Apuntando a servidor sin respuesta...
[20s] sin salida
[40s] sin salida
[60s] proceso colgado; no hay reconexion
```

**Fragmento corregido:**

```python
response = urlopen(req, timeout=30.0, context=context)
```

## Error 3: reconexion infinita sin backoff

**Descripcion:** al fallar la red, el cliente hacia `continue` dentro de `while True` sin pausa ni limite de intentos.

**Como falla en produccion:** si el servidor cae, muchos clientes intentan reconectar sin descanso y generan una tormenta de reconexiones.

**Invariante violado:** maximo 5 intentos consecutivos y espera con backoff exponencial.

**Evidencia provocada en terminal:**

```text
[ERROR] reconectando...
[ERROR] reconectando...
[ERROR] reconectando...
[ERROR] reconectando...
500 lineas similares en menos de un segundo
```

**Fragmento corregido:**

```python
self.reconnect_attempts += 1
if self.reconnect_attempts > self.max_reconnects:
    self.detener()
wait = (self.retry_ms / 1000.0) * (2 ** (self.reconnect_attempts - 1))
time.sleep(wait)
```

## Error 4: procesamiento antes del fin real del mensaje

**Descripcion:** el cliente procesaba cada linea `data:` como si fuera un evento completo.

**Como falla en produccion:** los mensajes SSE multilinea se parten en eventos incompletos. Un JSON dividido en dos lineas falla aunque el servidor lo haya enviado correctamente.

**Invariante violado:** nunca procesar un mensaje SSE hasta recibir la linea en blanco que lo cierra.

**Evidencia provocada en terminal:**

```text
[SERVER]
data: {"producto":
data: "A01"}

[CLIENTE FALLIDO]
JSONDecodeError: Expecting value: line 1 column 13 (char 12)
```

**Fragmento corregido:**

```python
elif field == "data":
    data_buffer.append(value)

if line == "":
    procesar_mensaje(msg_id, event_type, "\n".join(data_buffer))
```
