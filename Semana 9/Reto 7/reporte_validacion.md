# Reporte de validación - Semana 9

|Caso|Esperado|Observado|Estado|
|-|-|-|-|
|1. Estado inicial y operación normal|Inicia CERRADO; 10 éxitos dejan fallos en 0.|`CircuitBreaker()` inicia `CERRADO`; exitos llaman `\_registrar\_exito()` y mantienen contador 0.|Pasado|
|2. CERRADO a ABIERTO|Exactamente N fallos 5xx abren el circuito.|Con umbral 3, el tercer 503 cambia a `ABIERTO`; la siguiente llamada lanza `CircuitOpenError`.|Pasado|
|3. Los 4xx no abren|N+5 respuestas 401 no cambian estado ni contador.|8 respuestas 401 dejan `estado=CERRADO` y `\_fallos\_consecutivos=0`; TokenManager recibe los 401 y renueva token.|Pasado|
|4. ABIERTO a SEMIABIERTO|Tras `timeout\_apertura`, la siguiente lectura de estado pasa a SEMIABIERTO.|Despues de 2.1s, `estado=SEMIABIERTO`.|Pasado|
|5. Recuperacion exitosa|Exito en SEMIABIERTO cierra circuito y reinicia contador.|La peticion de prueba normal cambia a `CERRADO` y contador 0.|Pasado|
|6. Fallo en SEMIABIERTO|Un 503 en prueba vuelve a ABIERTO con timeout nuevo.|`\_registrar\_fallo()` abre de nuevo cuando el estado es `SEMIABIERTO`.|Pasado|
|7. Concurrencia en SEMIABIERTO|De 3 peticiones simultaneas, solo 1 llega al servidor.|`\_probe\_en\_curso` y `asyncio.Lock` permiten una prueba; las demas reciben `CircuitOpenError`.|Pasado|

## Evidencia de proteccion al servidor

Durante la demo, al abrirse el circuito el contador del mock queda fijo mientras
las peticiones posteriores fallan rapido. En la fase abierta se registra:

```text
servidor\_antes=6 servidor\_despues=6
```

Eso confirma que la llamada fue rechazada por el cliente y no llego al servidor.

## Bug encontrado y fix aplicado

Bug detectado: si el estado `SEMIABIERTO` no se protege con un indicador de
prueba en curso, varias peticiones concurrentes pueden pasar al servidor antes
de que la primera termine.

Causa raiz: `asyncio.Lock.acquire()` serializa entrada al bloque, pero si no se
marca una prueba activa antes de soltar el lock, las tareas siguientes tambien
pueden ejecutar la llamada remota.

Fix aplicado: se agrego `\_probe\_en\_curso`. La primera peticion semiabierta lo
activa; las demas reciben `CircuitOpenError`. Al terminar la prueba, exito o
fallo limpian el indicador y actualizan el estado.

## Resultado Zero Tolerance

La prueba conductual de 401 repetido pasa:

```text
estado=CERRADO contador\_fallos=0
```

El breaker no intercepta errores de autenticacion como fallos del servidor.

