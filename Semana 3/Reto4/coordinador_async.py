"""
coordinador_async.py
Reto IA 4 — Ingeniero de Timeouts y Cancelación
Semana 3: Programación Asíncrona y Concurrencia en el Cliente

Entregable: Módulo con 3 estrategias de control de flujo asíncrono.

Estrategias implementadas:
  1. Timeouts individuales por petición (asyncio.wait_for)
  2. Cancelación en cadena al detectar 401 (asyncio.create_task + Task.cancel)
  3. Carga con prioridad — procesar resultados conforme llegan (asyncio.wait)
"""

import asyncio
import aiohttp
import time
import logging


# ──────────────────────────────────────────────────────────────────────────────
# Configuración de logging
# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Configuración global
# ──────────────────────────────────────────────────────────────────────────────

BASE_URL = "http://localhost:3000/api/"
TIMEOUT_POR_DEFECTO = 10  # segundos — fallback si no se especifica uno


# ──────────────────────────────────────────────────────────────────────────────
# ESTRATEGIA 1 — Timeouts individuales por petición
# ──────────────────────────────────────────────────────────────────────────────

async def peticion_con_timeout(
    session: aiohttp.ClientSession,
    metodo: str,
    url: str,
    timeout_s: float,
    nombre: str,
    **kwargs,
):
    """
    Ejecuta una petición HTTP con un timeout independiente por petición.

    A diferencia de configurar el timeout en ClientSession (que aplica a
    todas las peticiones por igual), aquí cada llamada puede tener su
    propio umbral.  Si se agota el tiempo, solo ESA petición falla; las
    demás continúan normalmente.

    Args:
        session:   ClientSession de aiohttp ya abierta.
        metodo:    Verbo HTTP en minúsculas: "get", "post", "put", etc.
        url:       URL absoluta del endpoint.
        timeout_s: Segundos máximos de espera para esta petición.
        nombre:    Nombre descriptivo para logs (p.ej. "productos").
        **kwargs:  Argumentos adicionales para session.request()
                   (json=, params=, headers=, etc.).

    Returns:
        dict | list | None:
          - El body JSON de la respuesta si todo va bien.
          - None si se agota el timeout (el error queda registrado en log).

    Raises:
        asyncio.CancelledError: se re-lanza siempre; nunca se suprime.
        aiohttp.ClientError:    otros errores de red (no timeout).
    """
    http_method = getattr(session, metodo.lower())  # session.get / session.post / …

    try:
        log.info("[%s] Iniciando petición (timeout=%.1fs) → %s", nombre, timeout_s, url)
        inicio = time.perf_counter()

        # wait_for lanza asyncio.TimeoutError si la coroutine no termina a tiempo
        async with await asyncio.wait_for(
            http_method(url, **kwargs),
            timeout=timeout_s,
        ) as response:
            if response.status >= 400:
                log.warning("[%s] Respuesta %d desde %s", nombre, response.status, url)
                # Devolvemos la respuesta igualmente para que el llamador decida
                return {"__status__": response.status, "__url__": str(url)}
            datos = await response.json()
            elapsed = time.perf_counter() - inicio
            log.info("[%s] OK en %.3fs", nombre, elapsed)
            return datos

    except asyncio.TimeoutError:
        log.warning("[TIMEOUT] '%s' superó el límite de %.1fs — se continúa sin sus datos", nombre, timeout_s)
        return None  # las otras peticiones siguen adelante

    except asyncio.CancelledError:
        log.info("[CANCELADO] '%s' fue cancelado externamente", nombre)
        raise  # NUNCA suprimir CancelledError

    except aiohttp.ClientConnectorError as exc:
        log.error("[ERROR RED] '%s': %s", nombre, exc)
        return None

    except Exception as exc:
        log.error("[ERROR] '%s': %s — %s", nombre, type(exc).__name__, exc)
        return None


async def cancel_remaining(tareas: list, motivo: str = "") -> None:
    """
    Cancela todas las tareas asyncio.Task que aún no hayan terminado.

    Después de llamar a Task.cancel(), hay que await la tarea para darle
    oportunidad de limpiar recursos (cerrar conexiones, liberar semáforos,
    etc.).  Se usa gather(return_exceptions=True) para no propagaremos
    los CancelledError de las tareas canceladas.

    Args:
        tareas: lista de asyncio.Task a cancelar (pueden estar completas
                o pendientes; las completas se ignoran).
        motivo: texto libre que aparece en el log para identificar por qué
                se está cancelando (p.ej. "401 en perfil").
    """
    pendientes = [t for t in tareas if not t.done()]
    if not pendientes:
        log.info("[CANCEL] No hay tareas pendientes que cancelar.")
        return

    log.warning("[CANCEL] Cancelando %d tarea(s)%s",
                len(pendientes),
                f" — motivo: {motivo}" if motivo else "")

    for tarea in pendientes:
        nombre = tarea.get_name()
        log.info("[CANCEL]   → cancelando tarea '%s'", nombre)
        tarea.cancel()

    # Esperar a que cada tarea procese su CancelledError internamente
    await asyncio.gather(*pendientes, return_exceptions=True)
    log.info("[CANCEL] Todas las tareas canceladas correctamente.")


async def cargar_con_timeouts_individuales(session: aiohttp.ClientSession) -> dict:
    """
    ESTRATEGIA 1: Cada endpoint tiene su propio deadline independiente.

    Timeouts configurados:
      productos      → 5 s  (dataset grande, necesita más tiempo)
      categorias     → 3 s  (lista corta, debería ser rápida)
      perfil         → 2 s  (solo un objeto, muy rápido normalmente)
      notificaciones → 8 s  (puede incluir polling largo)

    Si *categorias* tarda más de 3 s, el resultado será None para esa clave,
    pero *productos*, *perfil* y *notificaciones* continúan con sus propios
    tiempos; no se ven afectados.

    Returns:
        dict con claves: "productos", "categorias", "perfil", "notificaciones"
        Cada valor es el dato JSON o None si hubo timeout/error.
    """
    log.info("── Estrategia 1: Timeouts individuales ──")

    # Los 4 awaits se lanzan con gather → corren en paralelo
    # Cada uno tiene su propio asyncio.wait_for interno
    resultados = await asyncio.gather(
        peticion_con_timeout(session, "get", f"{BASE_URL}productos",      5.0, "productos"),
        peticion_con_timeout(session, "get", f"{BASE_URL}categorias",     3.0, "categorias"),
        peticion_con_timeout(session, "get", f"{BASE_URL}perfil",         2.0, "perfil"),
        peticion_con_timeout(session, "get", f"{BASE_URL}notificaciones", 8.0, "notificaciones"),
        return_exceptions=False,  # peticion_con_timeout ya maneja sus excepciones
    )

    claves = ["productos", "categorias", "perfil", "notificaciones"]
    return dict(zip(claves, resultados))


# ──────────────────────────────────────────────────────────────────────────────
# ESTRATEGIA 2 — Cancelación en cadena al detectar error de autenticación
# ──────────────────────────────────────────────────────────────────────────────

async def verificar_autenticacion(response: aiohttp.ClientResponse) -> bool:
    """
    Inspecciona el código HTTP de la respuesta para determinar autenticación.

    Args:
        response: objeto ClientResponse de aiohttp (antes de leer el body).

    Returns:
        False si el status es 401 (Unauthorized) — el usuario no está auth.
        True  para cualquier otro código (incluyendo otros errores 4xx/5xx,
              que serán manejados por la capa superior).
    """
    if response.status == 401:
        log.warning("[AUTH] Respuesta 401 Unauthorized — sesión inválida o expirada")
        return False
    return True


async def cargar_con_cancelacion_en_cadena() -> dict:
    """
    ESTRATEGIA 2: Si /perfil responde 401, cancelar TODAS las demás tareas.

    Razonamiento: si el usuario no está autenticado, no tiene sentido
    procesar productos, categorías ni notificaciones, ya que el servidor
    probablemente devolverá 401 en todos ellos también.

    Flujo:
      1. Se crean 4 Tasks independientes con asyncio.create_task().
      2. Se espera SOLO la tarea de perfil con asyncio.wait().
      3. Si perfil devuelve 401 → cancel_remaining() cancela las otras 3.
      4. Si perfil es OK → se espera a que terminen las demás.

    Returns:
        dict con "productos", "categorias", "perfil", "notificaciones".
        Claves con tareas canceladas contendrán None.
        Si hubo 401, "autenticado" será False.
    """
    log.info("── Estrategia 2: Cancelación en cadena ──")

    resultado = {
        "productos": None,
        "categorias": None,
        "perfil": None,
        "notificaciones": None,
        "autenticado": True,
    }

    async with aiohttp.ClientSession() as session:

        # ── Coroutines internas ──────────────────────────────────────────────
        async def _fetch_json(url: str, nombre: str):
            """Petición simple que devuelve (nombre, datos_o_None, status)."""
            try:
                async with session.get(url) as resp:
                    if resp.status >= 400:
                        return nombre, None, resp.status
                    datos = await resp.json()
                    return nombre, datos, resp.status
            except asyncio.CancelledError:
                log.info("[CANCEL] Tarea '%s' cancelada", nombre)
                raise
            except Exception as exc:
                log.error("[ERROR] '%s': %s", nombre, exc)
                return nombre, None, -1

        async def _fetch_perfil(url: str):
            """Petición especial: retorna también el status 401."""
            try:
                async with session.get(url) as resp:
                    auth_ok = await verificar_autenticacion(resp)
                    if not auth_ok:
                        return "perfil", None, 401
                    datos = await resp.json()
                    return "perfil", datos, resp.status
            except asyncio.CancelledError:
                log.info("[CANCEL] Tarea 'perfil' cancelada")
                raise
            except Exception as exc:
                log.error("[ERROR] 'perfil': %s", exc)
                return "perfil", None, -1

        # ── Crear tareas ─────────────────────────────────────────────────────
        tarea_productos = asyncio.create_task(
            _fetch_json(f"{BASE_URL}productos", "productos"),
            name="task-productos"
        )
        tarea_categorias = asyncio.create_task(
            _fetch_json(f"{BASE_URL}categorias", "categorias"),
            name="task-categorias"
        )
        tarea_perfil = asyncio.create_task(
            _fetch_perfil(f"{BASE_URL}perfil"),
            name="task-perfil"
        )
        tarea_notificaciones = asyncio.create_task(
            _fetch_json(f"{BASE_URL}notificaciones", "notificaciones"),
            name="task-notificaciones"
        )

        otras_tareas = [tarea_productos, tarea_categorias, tarea_notificaciones]

        # ── Esperar primero a perfil ─────────────────────────────────────────
        log.info("[ESTRATEGIA2] Esperando resultado de /perfil...")
        done, pending = await asyncio.wait(
            [tarea_perfil],
            timeout=TIMEOUT_POR_DEFECTO,
        )

        if not done:
            # perfil no respondió a tiempo
            log.warning("[ESTRATEGIA2] /perfil no respondió — cancelando todo")
            await cancel_remaining(otras_tareas + [tarea_perfil], "timeout en perfil")
            return resultado

        # Obtener resultado de perfil
        _, datos_perfil, status_perfil = tarea_perfil.result()

        if status_perfil == 401:
            # Sin autenticación → cancelar inmediatamente las demás
            resultado["autenticado"] = False
            log.warning("[ESTRATEGIA2] 401 detectado — cancelando %d tareas", len(otras_tareas))
            await cancel_remaining(otras_tareas, "401 en perfil")
            return resultado

        # Perfil OK → esperar el resto
        resultado["perfil"] = datos_perfil
        log.info("[ESTRATEGIA2] Perfil OK — esperando otras tareas...")

        done2, _ = await asyncio.wait(otras_tareas, timeout=TIMEOUT_POR_DEFECTO)
        for tarea in done2:
            try:
                nombre, datos, _ = tarea.result()
                resultado[nombre] = datos
            except Exception as exc:
                log.error("[ESTRATEGIA2] Error al obtener resultado: %s", exc)

        # Cancelar las que todavía no terminaron (si las hay)
        pendientes_restantes = [t for t in otras_tareas if not t.done()]
        if pendientes_restantes:
            await cancel_remaining(pendientes_restantes, "timeout global")

    return resultado


# ──────────────────────────────────────────────────────────────────────────────
# ESTRATEGIA 3 — Carga con prioridad: procesar conforme llegan
# ──────────────────────────────────────────────────────────────────────────────

async def cargar_con_prioridad() -> dict:
    """
    ESTRATEGIA 3: asyncio.wait(FIRST_COMPLETED) — dashboard parcial progresivo.

    En lugar de esperar a que TODAS las peticiones terminen para mostrar
    algo al usuario, procesamos cada resultado en cuanto llega.

    Hitos especiales:
      - Cuando *productos* Y *perfil* están listos → "DASHBOARD PARCIAL DISPONIBLE"
        (el usuario puede ver la tienda aunque categorías/notificaciones esperen)

    Flujo:
      1. Crear 4 Tasks.
      2. Bucle: asyncio.wait(FIRST_COMPLETED) hasta que no queden pendientes
         o se agote el timeout global.
      3. En cada iteración, procesar las tareas que terminaron.
      4. Registrar el hito de dashboard parcial cuando corresponda.

    Returns:
        dict con "productos", "categorias", "perfil", "notificaciones",
        "dashboard_parcial_disponible" (bool), y "duracion_total_s" (float).
    """
    log.info("── Estrategia 3: Carga con prioridad (FIRST_COMPLETED) ──")

    TIMEOUT_GLOBAL = 10.0   # s — tiempo máximo total
    inicio_global = time.perf_counter()

    resultado = {
        "productos": None,
        "categorias": None,
        "perfil": None,
        "notificaciones": None,
        "dashboard_parcial_disponible": False,
        "duracion_total_s": 0.0,
    }

    async with aiohttp.ClientSession() as session:

        async def _fetch(url: str, nombre: str):
            """Coroutine simple de fetch; retorna (nombre, datos)."""
            try:
                async with session.get(url) as resp:
                    if resp.status >= 400:
                        log.warning("[PRIORIDAD][%s] status %d", nombre, resp.status)
                        return nombre, None
                    datos = await resp.json()
                    elapsed = time.perf_counter() - inicio_global
                    log.info("[PRIORIDAD][%s] Recibido en %.3fs", nombre, elapsed)
                    return nombre, datos
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.error("[PRIORIDAD][%s] Error: %s", nombre, exc)
                return nombre, None

        # Crear las 4 tareas con nombres descriptivos
        pendientes: set = {
            asyncio.create_task(_fetch(f"{BASE_URL}productos",      "productos"),      name="p-productos"),
            asyncio.create_task(_fetch(f"{BASE_URL}categorias",     "categorias"),     name="p-categorias"),
            asyncio.create_task(_fetch(f"{BASE_URL}perfil",         "perfil"),         name="p-perfil"),
            asyncio.create_task(_fetch(f"{BASE_URL}notificaciones", "notificaciones"), name="p-notificaciones"),
        }

        # ── Bucle FIRST_COMPLETED ────────────────────────────────────────────
        while pendientes:
            tiempo_restante = TIMEOUT_GLOBAL - (time.perf_counter() - inicio_global)
            if tiempo_restante <= 0:
                log.warning("[PRIORIDAD] Timeout global alcanzado — cancelando %d tarea(s)", len(pendientes))
                await cancel_remaining(list(pendientes), "timeout global estrategia 3")
                break

            # Esperar a que al menos UNA tarea termine
            done, pendientes = await asyncio.wait(
                pendientes,
                timeout=tiempo_restante,
                return_when=asyncio.FIRST_COMPLETED,
            )

            if not done:
                # Tiempo agotado sin que terminara ninguna
                log.warning("[PRIORIDAD] Timeout sin nuevas respuestas — abortando")
                await cancel_remaining(list(pendientes), "timeout interno")
                break

            # Procesar las que terminaron en esta ronda
            for tarea in done:
                try:
                    nombre, datos = tarea.result()
                    resultado[nombre] = datos
                    log.info("[PRIORIDAD] Procesado '%s' (acumulado: %s)",
                             nombre,
                             [k for k, v in resultado.items() if v is not None and k not in ("dashboard_parcial_disponible", "duracion_total_s")])
                except Exception as exc:
                    log.error("[PRIORIDAD] Error al leer resultado de tarea: %s", exc)

            # ── Comprobar hito de dashboard parcial ──────────────────────────
            if (
                not resultado["dashboard_parcial_disponible"]
                and resultado["productos"] is not None
                and resultado["perfil"] is not None
            ):
                hito_t = time.perf_counter() - inicio_global
                resultado["dashboard_parcial_disponible"] = True
                log.info(
                    "★ DASHBOARD PARCIAL DISPONIBLE en %.3fs "
                    "(productos + perfil listos; esperando categorias/notificaciones)",
                    hito_t,
                )

    resultado["duracion_total_s"] = round(time.perf_counter() - inicio_global, 3)
    return resultado


# ──────────────────────────────────────────────────────────────────────────────
# Punto de entrada — prueba de las 3 estrategias
# ──────────────────────────────────────────────────────────────────────────────

async def main() -> None:
    """
    Ejecuta y mide las 3 estrategias de coordinación asíncrona.
    """

    def separador(n: int, titulo: str) -> None:
        print(f"\n{'═'*65}")
        print(f"  ESTRATEGIA {n}: {titulo}")
        print(f"{'═'*65}")

    def imprimir_resultado(r: dict) -> None:
        for clave, valor in r.items():
            if isinstance(valor, list):
                print(f"    {clave:25s}: lista con {len(valor)} elementos")
            elif isinstance(valor, dict):
                print(f"    {clave:25s}: dict con {len(valor)} clave(s)")
            else:
                print(f"    {clave:25s}: {valor!r}")

    # ── Estrategia 1 ─────────────────────────────────────────────────────────
    separador(1, "Timeouts Individuales")
    async with aiohttp.ClientSession() as session:
        t1 = time.perf_counter()
        resultado1 = await cargar_con_timeouts_individuales(session)
        duracion1 = time.perf_counter() - t1

    print(f"\n  Tiempo total: {duracion1:.3f} s")
    imprimir_resultado(resultado1)

    # ── Estrategia 2 ─────────────────────────────────────────────────────────
    separador(2, "Cancelación en Cadena (401 → cancel todo)")
    t2 = time.perf_counter()
    resultado2 = await cargar_con_cancelacion_en_cadena()
    duracion2 = time.perf_counter() - t2

    print(f"\n  Tiempo total: {duracion2:.3f} s")
    imprimir_resultado(resultado2)

    if not resultado2.get("autenticado"):
        print("\n  ⚠  Se detectó 401 — las otras tareas fueron canceladas.")
        print("     Redirigir al usuario a la pantalla de login.")

    # ── Estrategia 3 ─────────────────────────────────────────────────────────
    separador(3, "Carga con Prioridad (FIRST_COMPLETED)")
    resultado3 = await cargar_con_prioridad()

    print(f"\n  Tiempo total: {resultado3['duracion_total_s']} s")
    parcial = resultado3.pop("dashboard_parcial_disponible")
    duracion = resultado3.pop("duracion_total_s")
    imprimir_resultado(resultado3)
    print(f"\n  Dashboard parcial disponible: {'Sí ✓' if parcial else 'No ✗'}")
    print(f"  Duración total              : {duracion} s")

    # ── Comparativa ──────────────────────────────────────────────────────────
    print(f"\n{'═'*65}")
    print("  COMPARATIVA DE ESTRATEGIAS")
    print(f"{'═'*65}")
    print(f"  Estrategia 1 (timeouts indiv.) : {duracion1:.3f} s")
    print(f"  Estrategia 2 (cancelación 401) : {duracion2:.3f} s")
    print(f"  Estrategia 3 (prioridad)       : {duracion} s")
    print()


if __name__ == "__main__":
    asyncio.run(main())
