# Tabla Comparativa — Modelos de Concurrencia en Python

## Reto 1 · Semana 3 · EcoMarket — Programación del lado del cliente

### Contexto del experimento

Se midió el tiempo de realizar **3 peticiones HTTP concurrentes** simuladas:

|Endpoint|Latencia simulada|
|-|:-:|
|`GET /productos`|300 ms|
|`GET /categorias`|100 ms|
|`GET /perfil`|200 ms|
|**Total secuencial**|**600 ms**|

> \[!NOTE]
> En un modelo \*\*secuencial puro\*\*, el tiempo total sería ≈ 600 ms (suma de las tres latencias).
> Los modelos concurrentes deberían aproximarse al \*\*tiempo del request más lento\*\*: ≈ 300 ms.

\---

### Resultados medidos (promedio de 3 ejecuciones)

|Modelo|Tiempo Total (s)|Tiempo Prom/petición (s)|Manejo de Errores|Legibilidad (1–5)|Recomendación|
|-|:-:|:-:|-|:-:|-|
|**Callbacks** `ThreadPoolExecutor + add\_done\_callback`|\~0.312|\~0.104|Manual dentro del callback; difícil de propagar|★★☆☆☆ (2)|❌ Evitar — callback hell, difícil de depurar|
|**Futures** `ThreadPoolExecutor + as\_completed`|\~0.308|\~0.103|`try/except` explícito; más claro|★★★☆☆ (3)|⚠️ Aceptable para tareas CPU-bound o con librerías síncronas|
|**Async/Await** `asyncio + asyncio.gather()`|\~0.303|\~0.101|`return\_exceptions=True`; muy limpio|★★★★★ (5)|✅ **Ideal** para I/O concurrente — un solo hilo, mínimo overhead|

\---

### Speedup respecto al modelo secuencial (600 ms)

|Modelo|Speedup|
|-|:-:|
|Callbacks|\~1.92×|
|Futures|\~1.95×|
|**Async/Await**|**\~1.98×**|

> \[!TIP]
> El speedup teórico máximo es \*\*2.0×\*\* (600 ms / 300 ms = 2.0). Todos los modelos se
> aproximan a él porque el tiempo real está dominado por la latencia del request más lento.

\---

### Observaciones clave

* **Callbacks**: El resultado llega vía función de retorno de llamada. El flujo es
invertido ("inversion of control"), lo que hace el código difícil de leer y el
manejo de errores propenso a ser olvidado.
* **Futures**: `as\_completed()` procesa los resultados en el orden de finalización
(categorías → perfil → productos), lo que es intuitivo. Usa hilos reales, por lo
que hay overhead de cambio de contexto del sistema operativo.
* **Async/Await**: Usa un **único hilo** con un event loop cooperativo. No hay
overhead de hilos, el código se lee de forma lineal, y `asyncio.gather()` maneja
la concurrencia de forma transparente. Es la opción óptima para aplicaciones I/O-bound.

\---

### Cuándo usar cada modelo

|Situación|Modelo recomendado|
|-|-|
|API I/O bound (HTTP, DB, archivos)|**Async/Await**|
|Llamada a librería bloqueante sin alternativa async|Futures (`executor.submit`)|
|Integración con framework de eventos legacy|Callbacks|
|Tareas CPU intensivas (cómputo pesado)|`ProcessPoolExecutor` (distinto caso)|



