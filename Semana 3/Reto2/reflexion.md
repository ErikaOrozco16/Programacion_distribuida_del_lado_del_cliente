# Reflexión: ¿Qué hace realmente el Event Loop de asyncio?
## Reto 2 · Semana 3 · EcoMarket — Programación del lado del cliente

---

## 1. ¿Qué pasa cuando se llama `asyncio.run()`?

Cuando escribimos `asyncio.run(main())`, Python ejecuta los siguientes pasos internos:

1. **Crea un nuevo event loop** (`asyncio.new_event_loop()`) y lo configura como el loop del hilo actual.
2. **Envuelve `main()` en una Task** — la Task #0, la tarea raíz del programa.
3. **Inicia el bucle principal** (`loop.run_until_complete(task_main)`):
   - El event loop corre de forma continua procesando eventos.
   - Cada vez que una corrutina hace `await`, se suspende y el loop puede ejecutar otras tareas pendientes.
   - Cuando no hay ninguna tarea lista, el loop **duerme** (bloqueando el hilo en `select()`/`epoll()`/`IOCP` según el OS) hasta que algún I/O está listo.
4. **Cuando `main()` retorna**, `run_until_complete()` retorna su resultado.
5. **Limpia el loop**: cancela tasks pendientes, cierra generadores async, cierra el loop.

```
asyncio.run(main())
    │
    ├─ Crear EventLoop
    ├─ Crear Task(main)
    ├─ loop.run_until_complete(Task(main))
    │       │
    │       ├─ [ciclo] Ejecutar tareas listas en la cola
    │       ├─ [ciclo] Esperar I/O (select/epoll/IOCP)
    │       ├─ [ciclo] Reactivar corrutinas con I/O listo
    │       └─ [fin] main() retornó → salir del loop
    └─ loop.close()
```

---

## 2. ¿Qué hace `await` realmente?

> **Concepto corregido:** `await` NO significa "esperar pasivamente". Significa **CEDER EL CONTROL AL EVENT LOOP**.

Cuando una corrutina ejecuta `await algo`, ocurren tres cosas:

1. **La corrutina se suspende**: Python guarda su estado interno (variables locales, posición en el código) en el objeto corrutina.
2. **El control regresa al event loop**: el loop puede ahora ejecutar otras corrutinas que estén listas.
3. **Cuando el awaitable termina**: el event loop **reanuda** la corrutina desde donde se suspendió, como si nada hubiera pasado.

Esto es **concurrencia cooperativa**: cada corrutina *coopera* cediendo el control voluntariamente en cada `await`. Si una corrutina nunca hace `await`, bloquea el event loop completo (por eso se dice que el código CPU-bound es peligroso en asyncio).

---

## 3. Diagrama temporal ASCII — Ejecución intercalada

```
 TIEMPO →    0ms      50ms     100ms    150ms    200ms    250ms    300ms
             │         │        │         │        │         │       │
═════════════╪═════════╪════════╪═════════╪════════╪═════════╪═══════╪═══
 HILO ÚNICO  ║                                                           ║
─────────────╫───────────────────────────────────────────────────────────╫
 Event Loop  ║  lanza  │        │  react. │        │  react. │   react. ║
             ║  3 tasks│        │  categ. │        │  perfil │   prod.  ║
─────────────╫─────────┼────────┼─────────┼────────┼─────────┼──────────╫
 [productos] ║ INICIO  │SUSPEND.│         │         │         │  FIN ✓  ║
             ║  await  │sleep   │ (durmiendo, event loop libre) │ reanuda║
─────────────╫─────────┼────────┼─────────┼────────┼─────────┼──────────╫
 [categorias]║ INICIO  │SUSPEND.│ FIN ✓   │         │         │         ║
             ║  await  │sleep   │reanuda  │ retorna │         │         ║
─────────────╫─────────┼────────┼─────────┼────────┼─────────┼──────────╫
 [perfil]    ║ INICIO  │SUSPEND.│         │         │  FIN ✓  │         ║
             ║  await  │sleep   │(dormida)│         │ reanuda │         ║
═════════════╪═════════╪════════╪═════════╪════════╪═════════╪══════════╪
```

**Observaciones clave del diagrama:**
- Las 3 corrutinas se inician casi simultáneamente (diferencia de nanosegundos).
- Todas hacen `await` inmediatamente → el event loop queda libre.
- El event loop no hace nada en los periodos en blanco: duerme eficientemente.
- A t=100ms: el timer de categorias expira → event loop reanuda esa corrutina.
- A t=200ms: el timer de perfil expira → event loop reanuda esa corrutina.
- A t=300ms: el timer de productos expira → event loop reanuda esa corrutina.
- **Tiempo total ≈ 300ms** (el más lento), no 600ms (suma secuencial).

---

## 4. El concepto que se corrige: await NO es espera pasiva

### ❌ Concepto incorrecto (intuitivo pero erróneo)

> *"await hace que el programa espere ahí parado, como un `time.sleep()` asíncrono."*

Si fuera así, `asyncio.gather(A, B, C)` tomaría el mismo tiempo que ejecutarlos en secuencia.

### ✅ Concepto correcto

> **`await` significa: "cedo el control al event loop hasta que este awaitable esté listo. Mientras tanto, el event loop puede ejecutar otras tareas."**

La diferencia crucial:

| | `time.sleep(0.3)` (síncrono) | `await asyncio.sleep(0.3)` (asíncrono) |
|---|---|---|
| ¿Bloquea el hilo? | **Sí** — nada más puede ejecutarse | **No** — el event loop sigue libre |
| ¿Otras corrutinas corren? | **No** | **Sí** |
| ¿Es concurrente? | No | **Sí** |
| Mecanismo | `select(fd, timeout=0.3)` bloqueante | callback registrado en el event loop |

### Analogía

Imagina un cocinero (el hilo único):
- **Síncrono**: pone el agua a hervir y **se queda parado** mirando la olla durante 10 minutos.
- **Asíncrono**: pone el agua a hervir, `await` → va a cortar verduras, lavar platos, preparar la salsa... Cuando el timer del agua suena (evento), regresa a atenderla.

`await` es el equivalente de *"pon esto en el fuego y avísame cuando esté listo"*.

---

## 5. ¿Por qué esto importa para EcoMarket?

En EcoMarket, el cliente necesita consultar simultáneamente:
- `/api/productos` (el endpoint más lento)
- `/api/categorias`
- `/api/perfil`
- `/api/notificaciones`

Con `await` síncrono en secuencia, el tiempo total sería la **suma** de todas las latencias. Con `asyncio.gather()`, el tiempo total es solo el de la **petición más lenta**. Para una aplicación web real con decenas de llamadas por carga de página, esto puede representar la diferencia entre 2 segundos y 300 ms de tiempo de respuesta percibido por el usuario.

El event loop de asyncio permite que un **único proceso Python** maneje miles de conexiones concurrentes, algo imposible con el modelo de hilos tradicional bajo el GIL de Python.
