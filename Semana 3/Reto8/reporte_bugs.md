# Reporte de Bugs — Suite de Pruebas Asíncronas EcoMarket

**Reto IA 8 — Diseñador de Suite de Pruebas Asíncronas**  
**Fecha:** Mayo 2026  
**Versión del cliente:** `cliente_async_ecomarket.py` (Reto IA 3)

---

## Resumen ejecutivo

Durante el diseño e implementación de la suite de pruebas con `pytest-asyncio` y `aioresponses`, se detectaron cuatro bugs en el comportamiento esperado del cliente asíncrono. Tres correspondían a errores reales del código original; uno era un error de diseño en la estrategia de pruebas que podría enmascarar fallos en producción.

---

## Bug #1 — `gather()` sin `return_exceptions` cancelaba todo cuando una petición fallaba

### Descripción

La primera versión de `cargar_dashboard()` usaba:

```python
resultados = await asyncio.gather(
    listar_productos(session),
    obtener_categorias(session),
    obtener_perfil(session),
    # Sin return_exceptions=True ← BUG
)
```

Cuando `/productos` devolvía un `ServerError`, `gather()` propagaba inmediatamente la excepción y **cancelaba las otras dos coroutines en vuelo**. Esto significaba que incluso si `/categorias` y `/perfil` estaban disponibles, el dashboard fallaba completamente en lugar de entregar los datos parciales que sí estaban disponibles.

### Reproducción

```python
# Test que detectó el bug:
async def test_cargar_dashboard_completa_aunque_una_falle():
    with aioresponses() as m:
        m.get(".../productos", status=500, payload={"error": "boom"})
        m.get(".../categorias", status=200, payload=CATEGORIAS_MOCK)
        m.get(".../perfil",    status=200, payload=PERFIL_MOCK)

        # Sin return_exceptions=True, esto lanzaba ServerError
        # en vez de retornar resultado parcial
        result = await cargar_dashboard()
    
    # FALLA: lanza ServerError en vez de retornar parcialmente
    assert len(result["errores"]) == 1
```

### Corrección aplicada

```python
# ANTES (buggy):
resultados = await asyncio.gather(
    listar_productos(session),
    obtener_categorias(session),
    obtener_perfil(session),
)

# DESPUÉS (correcto):
resultados = await asyncio.gather(
    listar_productos(session),
    obtener_categorias(session),
    obtener_perfil(session),
    return_exceptions=True,  ← clave
)
```

`return_exceptions=True` instruye a `gather()` a colocar la excepción como valor en la lista de resultados en lugar de propagarla, permitiendo que las coroutines restantes completen.

---

## Bug #2 — La sesión no se cerraba cuando `gather()` lanzaba excepción

### Descripción

En la versión sin `return_exceptions=True`, cuando `gather()` lanzaba una excepción, el flujo de control saltaba fuera del bloque `async with aiohttp.ClientSession()` de forma abrupta. Aunque el gestor de contexto (`__aexit__`) se invoca incluso en caso de excepción, se detectó que en algunos escenarios de prueba con `aioresponses`, la sesión quedaba en estado "abierta" y los mocks subsiguientes del mismo test se aplicaban sobre la sesión ya cerrada, causando errores de "connection already closed".

### Reproducción

```python
# Secuencia de tests en el mismo proceso:
# Test A deja la sesión en estado inconsistente
# Test B recibe "Session is closed" al reutilizar la sesión

async def test_a():
    # gather() sin return_exceptions lanza ServerError
    # La sesión se cierra pero aioresponses deja un mock sin consumir
    ...

async def test_b():
    # El mock sin consumir de test_a interfiere con test_b
    # Resultado: AssertionError inesperado
    ...
```

### Corrección aplicada

1. Usar `return_exceptions=True` (ver Bug #1) para que `gather()` nunca propague directamente.
2. Cada función de coordinación crea su propia sesión con `async with aiohttp.ClientSession() as session:` garantizando cierre limpio via `__aexit__` en cualquier escenario.
3. En los tests, usar `with aioresponses() as m:` como gestor de contexto que consume todos los mocks registrados al salir, limpiando el estado entre tests.

---

## Bug #3 — `asyncio.TimeoutError` no se distinguía de `ServerError`

### Descripción

El cliente definía una excepción personalizada `TimeoutError(EcoMarketError)`, pero el handler de excepciones capturaba `aiohttp.ServerTimeoutError` correctamente. Sin embargo, en algunos escenarios de prueba se descubrió que `asyncio.TimeoutError` (lanzado por `asyncio.wait_for()`) **no era capturado** por los `except aiohttp.ServerTimeoutError` de las funciones del cliente.

Esto significaba que si el llamador envolvía la coroutine en `asyncio.wait_for(timeout=...)`, un timeout real se propagaba como `asyncio.TimeoutError` crudo (no como el `TimeoutError` personalizado de EcoMarket), rompiendo el contrato de la API.

### Reproducción

```python
async def test_timeout_con_wait_for():
    async with aiohttp.ClientSession() as session:
        # wait_for lanza asyncio.TimeoutError, no aiohttp.ServerTimeoutError
        with pytest.raises(EcoMarketError):  # FALLA: escapa como asyncio.TimeoutError
            await asyncio.wait_for(
                listar_productos(session),
                timeout=0.001
            )
```

### Corrección aplicada

Agregar un handler adicional para `asyncio.TimeoutError` en cada función del cliente:

```python
try:
    async with session.get(url) as response:
        ...
except aiohttp.ServerTimeoutError as exc:
    raise TimeoutError(f"Timeout (aiohttp): {exc}") from exc
except asyncio.TimeoutError as exc:          # ← handler adicional
    raise TimeoutError(f"Timeout (asyncio): {exc}") from exc
except aiohttp.ClientConnectorError as exc:
    raise ConexionError(f"Sin conexión: {exc}") from exc
```

Esto garantiza que **cualquier** tipo de timeout siempre se convierte al `TimeoutError` personalizado de EcoMarket.

---

## Bug #4 — El semáforo no liberaba el slot cuando la petición lanzaba excepción

### Descripción

La primera implementación de `_crear_con_limite()` no usaba el semáforo como gestor de contexto:

```python
# Versión buggy:
async def _crear_con_limite(session, datos):
    await semaforo.acquire()           # adquiere el slot
    result = await crear_producto(session, datos)  # si lanza, no se libera
    semaforo.release()                 # NUNCA SE EJECUTA si hay excepción
    return result
```

Cuando `crear_producto()` lanzaba `ValidationError` (por ejemplo, 400 Bad Request), `semaforo.release()` nunca se ejecutaba. Esto causaba que el semáforo perdiera un slot permanentemente, y después de suficientes fallos, **ninguna nueva petición podía iniciar** porque todos los slots estaban "ocupados" por tareas ya finalizadas.

### Reproducción

```python
# Con MAX_CONCURRENTE=5 y 10 productos donde los primeros 5 fallan con 400:
lista = [{"nombre": f"P{i}"} for i in range(10)]
with aioresponses() as m:
    for _ in range(5):   # primeros 5 → 400, semáforo pierde 5 slots
        m.post(..., status=400)
    for _ in range(5):   # últimos 5 → 201, pero nunca inician (deadlock)
        m.post(..., status=201)

creados, fallidos = await crear_multiples_productos(lista)
# CUELGA INFINITAMENTE: los últimos 5 esperan un semáforo que nunca se libera
```

### Corrección aplicada

Usar `async with semaforo:` como gestor de contexto en lugar de `acquire()`/`release()` manuales. El gestor de contexto garantiza `release()` incluso si la coroutine lanza excepción:

```python
# ANTES (buggy):
async def _crear_con_limite(session, datos):
    await semaforo.acquire()
    result = await crear_producto(session, datos)
    semaforo.release()
    return result

# DESPUÉS (correcto):
async def _crear_con_limite(session, datos):
    async with semaforo:          # ← release() garantizado en __aexit__
        return await crear_producto(session, datos)
```

Este patrón (`async with lock/semaphore`) es la práctica estándar en Python asyncio y **siempre debe usarse** en lugar de `acquire()`/`release()` manuales.

---

## Tabla resumen

| # | Bug | Impacto | Categoría |
|---|-----|---------|-----------|
| 1 | `gather()` sin `return_exceptions` cancela todo | ALTO — dashboard inutilizable si 1 endpoint falla | Concurrencia |
| 2 | Sesión no se cierra limpiamente tras excepción en gather | MEDIO — resource leak, tests contaminados | Gestión de recursos |
| 3 | `asyncio.TimeoutError` escapa sin convertir | MEDIO — rompe el contrato de la API | Manejo de excepciones |
| 4 | Semáforo no liberado tras excepción → deadlock | CRÍTICO — bloqueo permanente del sistema | Concurrencia |

---

## Lecciones aprendidas

1. **Siempre usar `return_exceptions=True` en `gather()`** cuando las coroutines son independientes y un fallo parcial no debe abortar las demás.
2. **Siempre usar gestores de contexto (`async with`)** para locks, semáforos y sesiones — nunca `acquire()/release()` manuales.
3. **Distinguir fuentes de timeout**: `aiohttp.ServerTimeoutError` ≠ `asyncio.TimeoutError`. El cliente debe capturar ambos.
4. **Las pruebas unitarias con mocks detectan estos bugs sin servidor real**, lo que hace que la suite de pruebas sea imprescindible antes del despliegue.
