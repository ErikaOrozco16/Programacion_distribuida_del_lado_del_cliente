# ADR — Architecture Decision Records
# EcoMarket · Semana 3 · Concurrencia y coordinación async

---

## Índice

| ID      | Título                                                     | Estado    |
|---------|------------------------------------------------------------|-----------|
| ADR-001 | `gather()` como estrategia de coordinación principal       | Aceptado  |
| ADR-002 | `ClientSession` compartida entre peticiones del dashboard  | Aceptado  |
| ADR-003 | Timeout individual por función vs. timeout global          | Aceptado  |
| ADR-004 | Semáforo de concurrencia máxima en creación masiva         | Aceptado  |
| ADR-005 | Sin reintentos automáticos en la capa de concurrencia      | Aceptado  |

---

## ADR-001: `gather()` como estrategia de coordinación principal

**Fecha:** 2026-05-19  
**Estado:** Aceptado

### Contexto

El dashboard de EcoMarket necesita presentar cuatro fuentes de datos al mismo tiempo:
`/productos`, `/categorias`, `/perfil` y `/notificaciones`. Cada llamada es independiente
(no hay dependencias entre ellas) pero **todas son necesarias** para renderizar la
pantalla completa. El objetivo es minimizar el tiempo total de carga.

### Decisión

Usar **`asyncio.gather(*corrutinas, return_exceptions=True)`** como coordinador principal
de las cuatro peticiones del dashboard.

```python
productos, categorias, perfil, notificaciones = await asyncio.gather(
    obtener_productos(),
    obtener_categorias(),
    obtener_perfil(),
    obtener_notificaciones(),
    return_exceptions=True,
)
```

`return_exceptions=True` garantiza que un fallo en una fuente no cancela las demás.
Las excepciones se detectan e inspeccionan después de que `gather` retorna.

### Alternativas consideradas

| Alternativa                         | Por qué se descartó                                                         |
|-------------------------------------|-----------------------------------------------------------------------------|
| `asyncio.wait(FIRST_COMPLETED)`     | Más compleja; útil cuando queremos mostrar datos progresivamente, no aquí.  |
| `asyncio.as_completed()`            | Ideal para pipelines progresivos; innecesario cuando se necesitan todos.    |
| Llamadas secuenciales               | Tiempo total = suma de todos los tiempos. Inaceptable en UX.                |
| `gather()` sin `return_exceptions`  | Un fallo cancelaría todo. Demasiado frágil para producción.                 |

### Consecuencias

**Positivas:**
- API simple y legible: una sola línea coordina cuatro operaciones asíncronas.
- El tiempo total depende de la fuente **más lenta**, no de la suma.
- Manejo centralizado de errores: un solo bloque `try/except` o revisión post-gather.
- Fácil de extender: agregar una quinta fuente solo requiere añadir un argumento.

**Negativas:**
- No muestra datos parciales: el usuario espera aunque ya tengamos 3/4 fuentes listas.
- El SLA del dashboard queda definido por el endpoint más lento (generalmente `/notificaciones`).
- Si se necesita renderizado progresivo en el futuro, `gather` no se adapta sin refactorización.

### Cuándo cambiar

Si los requisitos de UX evolucionan hacia **renderizado progresivo** (mostrar productos
mientras se siguen cargando notificaciones), migrar a `asyncio.as_completed()` o
`asyncio.wait(return_when=FIRST_COMPLETED)` es el camino natural.

---

## ADR-002: `ClientSession` compartida entre peticiones del dashboard

**Fecha:** 2026-05-19  
**Estado:** Aceptado

### Contexto

El dashboard realiza 4 peticiones HTTP simultáneas. Para cada petición, `aiohttp` puede
abrir una conexión TCP al servidor. Crear y destruir conexiones es costoso en tiempo y
recursos. La pregunta es: ¿cuántas sesiones crear?

### Decisión

Usar **una única `aiohttp.ClientSession`** por invocación del dashboard (no una por
petición, ni una global para toda la aplicación).

```python
async def cargar_dashboard() -> dict:
    async with aiohttp.ClientSession(base_url=BASE_URL) as session:
        productos, categorias, perfil, notificaciones = await asyncio.gather(
            obtener_productos(session),
            obtener_categorias(session),
            obtener_perfil(session),
            obtener_notificaciones(session),
            return_exceptions=True,
        )
    return {"productos": productos, "categorias": categorias,
            "perfil": perfil, "notificaciones": notificaciones}
```

### Alternativas consideradas

| Alternativa                        | Por qué se descartó                                                              |
|------------------------------------|----------------------------------------------------------------------------------|
| Sesión por petición                | Abre y cierra 4 conexiones TCP; overhead inútil cuando el servidor es el mismo.  |
| Sesión global de la aplicación     | Ciclo de vida difícil de gestionar; puede filtrarse entre peticiones de usuarios.|
| `requests.Session` (síncrona)      | No es compatible con async; bloquearía el event loop.                            |

### Consecuencias

**Positivas:**
- Reutiliza el pool de conexiones TCP: las 4 peticiones comparten hasta `limit=100`
  conexiones (configurable con `aiohttp.TCPConnector`).
- Headers, cookies y timeouts se configuran una sola vez.
- El ciclo de vida es predecible: la sesión se crea y destruye con el dashboard.

**Negativas:**
- Los headers y cookies son compartidos entre las 4 peticiones: si una petición necesita
  auth diferenciada, habría que pasarla por parámetro, no como header global.
- Un bug que corrompa el estado de la sesión afecta a todas las peticiones simultáneas.
- No escala trivialmente a múltiples usuarios concurrentes (se necesitaría una sesión
  por usuario, no una global).

### Cuándo cambiar

Si distintos endpoints requieren credenciales diferentes, crear una sesión por dominio
o por conjunto de credenciales es la solución correcta.

---

## ADR-003: Timeout individual por función + timeout global del dashboard

**Fecha:** 2026-05-19  
**Estado:** Aceptado

### Contexto

El equipo de producto estableció que el dashboard no debe tardar más de **3 segundos**
en responder al usuario. Sin embargo, algunas fuentes de datos (p.ej. `/notificaciones`)
son secundarias y pueden tolerar más tiempo si se usan solas. ¿Dónde poner los timeouts?

### Decisión

Aplicar **dos niveles de timeout** independientes:

1. **Timeout individual** — configurado en `aiohttp.ClientTimeout` por función:
   - Peticiones primarias (`/productos`, `/categorias`): 2 s
   - Peticiones secundarias (`/notificaciones`): 5 s (cuando se usan solas)

2. **Timeout global** — `asyncio.wait_for(cargar_dashboard(), timeout=3.0)` en la capa
   de presentación, garantizando que el usuario nunca espera más de 3 s.

```python
timeout_principal = aiohttp.ClientTimeout(total=2.0)
timeout_secundario = aiohttp.ClientTimeout(total=5.0)

async def cargar_dashboard():
    async with aiohttp.ClientSession() as session:
        ...  # gather con return_exceptions=True
```

### Alternativas consideradas

| Alternativa                | Por qué se descartó                                                               |
|----------------------------|-----------------------------------------------------------------------------------|
| Solo timeout global        | No controla tiempos de funciones individuales; si gather ya tiene return_exc=True, un timeout global con wait_for lanza CancelledError que mata todo. |
| Solo timeout individual    | No garantiza el SLA de 3 s si varias peticiones empatan en el límite alto.        |
| Sin timeout                | Una petición colgada bloquea el dashboard indefinidamente.                        |

### Consecuencias

**Positivas:**
- Flexibilidad: peticiones secundarias pueden configurarse con más tiempo sin afectar al SLA global.
- Separación de responsabilidades: cada función controla su propio timeout; la capa de UI
  controla el SLA de experiencia de usuario.
- Compatible con `return_exceptions=True`: los timeouts individuales producen excepciones
  capturadas por gather.

**Negativas:**
- Mayor complejidad: dos lugares donde revisar/ajustar timeouts puede causar confusión.
- Posible inconsistencia: si el timeout individual (5 s) supera el global (3 s), el
  individual nunca actúa (el global lo cancela antes).
- Requiere documentación clara de los valores y sus relaciones.

### Cuándo cambiar

Si el equipo adopta un sistema de feature flags o configuración remota, externalizar
todos los timeouts a un objeto de configuración centralizado sería la siguiente mejora.

---

## ADR-004: Semáforo de 5 conexiones máximas en creación masiva

**Fecha:** 2026-05-19  
**Estado:** Aceptado

### Contexto

La función `crear_multiples_productos(lista)` puede recibir listas de longitud arbitraria
(en pruebas se usó con 50–200 productos). Sin control, lanzaría N peticiones simultáneas,
lo que puede:
- Saturar el servidor EcoMarket (que en desarrollo corre con 1 worker).
- Recibir errores 429 (Too Many Requests) o 503 (Service Unavailable).
- Agotar el file descriptor limit del SO.

### Decisión

Usar **`asyncio.Semaphore(5)`** para limitar la concurrencia máxima de peticiones POST
en `crear_multiples_productos()`.

```python
semaforo = asyncio.Semaphore(5)

async def crear_producto_limitado(datos: dict) -> dict:
    async with semaforo:
        return await session.post("/api/productos", json=datos)

resultados = await asyncio.gather(
    *[crear_producto_limitado(p) for p in lista_productos],
    return_exceptions=True,
)
```

### Cómo se eligió el número 5

El valor se eligió empíricamente y mediante análisis del entorno:
- El servidor de desarrollo usa **Express.js con 1 proceso** → max ~8–10 conexiones concurrentes manejadas fluidamente.
- Con 5 conexiones simultáneas, el CPU del servidor se mantiene bajo 60 % en las pruebas.
- Por encima de 10, el tiempo de respuesta promedio aumenta un 40 % (contención en el ORM).
- Se eligió 5 como margen conservador que maximiza throughput sin degradar latencias.

### Alternativas consideradas

| Alternativa            | Por qué se descartó                                                      |
|------------------------|--------------------------------------------------------------------------|
| Sin límite (N = lista) | Inestable; probado con 100 peticiones → errores 503 esporádicos.         |
| Semáforo de 20         | Mejor throughput pero aumenta latencias y riesgo de errores del servidor.|
| Rate limiter temporal  | Más preciso pero más complejo; adecuado si el API documenta req/s. Para crear productos en lote, la concurrencia es más relevante que la tasa. |
| `asyncio.Queue`        | Viable pero más verboso; Semaphore es idiomático para este patrón.       |

### Consecuencias

**Positivas:**
- El servidor recibe como máximo 5 peticiones simultáneas, independientemente del tamaño de la lista.
- Fácil de ajustar: cambiar el número no requiere modificar la lógica de negocio.
- Compatible con `gather()` y `return_exceptions=True`.

**Negativas:**
- El tiempo total de carga masiva = `ceil(N / 5) × latencia_promedio`. Para 200 productos a 150 ms/petición: `ceil(200/5) × 0.15 s = 6 s`.
- El número 5 es arbitrario y puede quedar obsoleto si el servidor escala o cambia.
- No adapta la concurrencia dinámicamente a la carga actual del servidor (sin feedback loop).

### Cuándo cambiar

Cuando el API de EcoMarket documente un rate limit explícito (p.ej. "100 req/min"),
migrar a `RateLimiter` (ver `Reto5/throttle.py`) es más preciso que un semáforo fijo.

---

## ADR-005: Sin reintentos automáticos en la capa de concurrencia

**Fecha:** 2026-05-19  
**Estado:** Aceptado

### Contexto

En Semana 2 se implementó lógica de **retry con backoff exponencial** para errores HTTP
5xx transitorios. Al introducir `asyncio.gather()` y semáforos en Semana 3, surge la
pregunta: ¿debería el código async reintentar automáticamente las peticiones fallidas?

### Decisión

**No** implementar retry automático en la capa de concurrencia (Semana 3). Los errores
se propagan como excepciones y el llamador decide qué hacer.

### Razonamiento detallado

La interacción entre retry y concurrencia introduce complejidad no trivial:

1. **Retry + `gather()` + timeout global**: si una de las 4 corrutinas del dashboard
   reintenta (con backoff de 1 s, 2 s, 4 s), puede exceder el timeout global de 3 s y
   causar `asyncio.CancelledError` en las otras corrutinas que ya terminaron exitosamente.

2. **Retry + Semáforo**: una corrutina que reintenta retiene el slot del semáforo durante
   el backoff, bloqueando otras peticiones que podrían ejecutarse.

3. **Retry + errores 4xx**: reintentar un error 404 o 400 es incorrecto. Distinguir
   qué códigos son "retriable" requiere lógica adicional que pertenece a una capa dedicada.

4. **Amplificación de carga**: si 5 peticiones simultáneas fallan y todas reintentan,
   el servidor recibe 5× la carga justo cuando está bajo estrés.

### Alternativas consideradas

| Alternativa                             | Por qué se descartó                                                   |
|-----------------------------------------|-----------------------------------------------------------------------|
| Retry inline en cada función async      | Mezcla responsabilidades; difícil de probar; amplifica carga.         |
| Retry en un decorador sobre gather      | El decorador no sabe cuáles tareas fallaron individualmente.           |
| Reintentar solo errores 5xx sin backoff | Sin backoff, amplifica la carga en el momento de mayor estrés.        |

### Cuándo agregar retry

En **Semana 9** se prevé implementar una capa de resiliencia con:
- Decorador `@retry(max_attempts=3, backoff=exponential)` aplicado a funciones individuales.
- Integración con `tenacity` o `aiohttp-retry`.
- Coordinación con los timeouts globales para evitar sobrepasar SLAs.
- Circuit breaker para endpoints que fallan repetidamente.

Esta separación de capas (concurrencia en Semana 3, resiliencia en Semana 9) sigue
el principio de responsabilidad única y facilita el testing independiente de cada capa.

### Consecuencias

**Positivas:**
- La capa de concurrencia es simple y predecible.
- Los tests de concurrencia no necesitan simular comportamiento de red inestable.
- No hay riesgo de exceder timeouts globales por reintentos inesperados.

**Negativas:**
- Errores transitorios de red (timeout de 1 petición en un gather de 4) no se recuperan automáticamente.
- El llamador debe implementar su propio manejo de errores si necesita resiliencia.

---

## Decisión que cambiaría

> _Reflexión honesta para el equipo y para evaluación académica_

**Cambiaría: el valor fijo del semáforo en ADR-004.**

Elegir `Semaphore(5)` fue pragmático para el entorno de desarrollo, pero en producción
este número debería ser **configurable externamente** (variable de entorno, archivo de
configuración) en lugar de estar hardcodeado. Un servidor de producción con múltiples
workers podría tolerar 20–30 conexiones concurrentes; uno con rate limiting explícito
podría requerir 2 o 3.

La lección es que los "números mágicos" en concurrencia son los más difíciles de
diagnosticar cuando fallan. Hubiera preferido introducir desde el principio:

```python
MAX_CONCURRENCIA = int(os.getenv("ECOMARKET_MAX_CONCURRENT", "5"))
semaforo = asyncio.Semaphore(MAX_CONCURRENCIA)
```

Esto habría hecho el sistema más adaptable sin cambios de código, siguiendo el
principio de [The Twelve-Factor App — Config](https://12factor.net/config).

**También reconsideraría: no usar `return_exceptions=True` por defecto (ADR-001).**

Si bien es robusto, oculta errores fácilmente: un desarrollador que olvide revisar
si cada resultado es una excepción puede trabajar con datos corruptos silenciosamente.
Una alternativa más explícita habría sido un wrapper que siempre registra en log
los resultados fallidos antes de devolverlos.
