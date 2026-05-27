# Comparación de estrategias de coordinación async — EcoMarket Dashboard

> **Contexto:** El dashboard de EcoMarket carga 4 fuentes de datos simultáneamente.  
> Las latencias simuladas son: `productos=200ms`, `categorias=100ms`, `perfil=500ms`,  
> `notificaciones=TIMEOUT` (el endpoint tarda 10 s pero el timeout está en 3 s).

## Tabla de comparación

| Estrategia                        | Primer Dato | Tiempo Total | Datos OK | Comportamiento ante Timeout |
|:----------------------------------|:-----------:|:------------:|:--------:|:----------------------------|
| `gather(return_exceptions=True)`  | ~500 ms     | ~500 ms      | 3 / 3    | Continúa — timeout capturado como excepción en el resultado; los demás endpoints no se cancelan. |
| `wait(FIRST_COMPLETED)`           | ~100 ms     | ~3 000 ms    | 3 / 3    | Progresivo — cada resultado disponible al instante; el timeout llega al final sin bloquear los anteriores. |
| `as_completed()`                  | ~100 ms     | ~3 000 ms    | 3 / 3    | Igual que FIRST_COMPLETED pero con API de iterador; el timeout se captura como excepción en el `await`. |
| `wait(FIRST_EXCEPTION)`           | ~3 000 ms   | ~3 000 ms    | 3 / 3    | Retorna al primer error (el timeout); como los otros 3 terminaron antes, se obtienen. Si el timeout fuera más rápido que perfil, perfil se cancelaría. |

> **Nota:** "Primer Dato" con `gather()` es el tiempo hasta que **todo el gather termina**,
> porque no entrega datos parciales. Con las otras estrategias, el primer dato se entrega
> cuando el endpoint más rápido (categorías ≈ 100 ms) termina.

---

## Tabla de puntajes (1 = peor, 5 = mejor)

| Estrategia                        | Latencia Percibida | Robustez | Complejidad del código | Mantenibilidad | **Total** |
|:----------------------------------|:------------------:|:--------:|:---------------------:|:--------------:|:---------:|
| `gather(return_exceptions=True)`  | ★★★☆☆ (3)         | ★★★★★ (5)| ★★★★★ (5)             | ★★★★★ (5)      | **18/20** |
| `as_completed()`                  | ★★★★★ (5)         | ★★★★★ (5)| ★★★★☆ (4)             | ★★★★☆ (4)      | **18/20** |
| `wait(FIRST_COMPLETED)`           | ★★★★★ (5)         | ★★★★★ (5)| ★★☆☆☆ (2)             | ★★★☆☆ (3)      | **15/20** |
| `wait(FIRST_EXCEPTION)`           | ★★★☆☆ (3)         | ★★★☆☆ (3)| ★★★☆☆ (3)             | ★★★☆☆ (3)      | **12/20** |

**Criterios de puntuación:**
- **Latencia Percibida:** qué tan pronto puede el UI mostrar el primer dato al usuario.
- **Robustez:** cuántos datos obtiene ante un fallo parcial (el timeout de notificaciones).
- **Complejidad:** cuántas líneas / construcciones especiales necesita la implementación.
- **Mantenibilidad:** qué tan fácil es añadir un quinto endpoint o cambiar el timeout.

---

## Recomendación para EcoMarket

Para el dashboard de EcoMarket, **la recomendación es usar `asyncio.gather()` con
`return_exceptions=True` como estrategia base**, y planear una migración a
`asyncio.as_completed()` cuando el frontend soporte renderizado progresivo.

### Por qué `gather()` ahora

`gather()` tiene el mayor puntaje combinado (18/20) gracias a su simplicidad y robustez.
El código resultante es fácil de leer, fácil de testear y fácil de explicar a un nuevo
desarrollador. El único costo es que el usuario espera al endpoint más lento que no haga
timeout (aquí: `perfil` a ≈500 ms), pero esto es aceptable dado que el SLA del dashboard
es de 3 segundos.

```python
# ✅ Implementación recomendada para el dashboard
async def cargar_dashboard(session: aiohttp.ClientSession) -> dict:
    productos, categorias, perfil, notificaciones = await asyncio.gather(
        obtener_productos(session),
        obtener_categorias(session),
        obtener_perfil(session),
        obtener_notificaciones(session),
        return_exceptions=True,
    )
    return {
        "productos":      productos      if not isinstance(productos, Exception)      else None,
        "categorias":     categorias     if not isinstance(categorias, Exception)     else None,
        "perfil":         perfil         if not isinstance(perfil, Exception)         else None,
        "notificaciones": notificaciones if not isinstance(notificaciones, Exception) else [],
    }
```

### Cuándo migrar a `as_completed()`

Si el equipo de frontend implementa **Server-Sent Events (SSE)** o **WebSocket streaming**
para renderizar el dashboard de forma incremental, `asyncio.as_completed()` es el paso
natural: misma robustez que `gather()`, pero entrega cada dato en cuanto está disponible.
Esto reduciría la latencia percibida de ~500 ms a ~100 ms sin cambiar la lógica de negocio.

### Cuándo NO usar `wait(FIRST_EXCEPTION)`

`FIRST_EXCEPTION` es adecuado para pipelines donde **un fallo hace inútil el resto**
(por ejemplo, validar → transformar → guardar: si la validación falla, no tiene sentido
continuar). En un dashboard donde cada sección es independiente, abortar todo por el
timeout de notificaciones sería una regresión de experiencia de usuario.

---

*Generado por: `comparacion_coordinacion.py` · EcoMarket · Semana 3 · 2026-05-19*
