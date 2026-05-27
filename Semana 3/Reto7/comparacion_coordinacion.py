"""
comparacion_coordinacion.py — Reto 7, Semana 3 · EcoMarket
============================================================
Mide y compara las cuatro estrategias de coordinación async de Python:

  1. asyncio.gather()                      — espera todos
  2. asyncio.wait(FIRST_COMPLETED)         — procesa en orden de llegada
  3. asyncio.as_completed()               — iterador en orden de llegada
  4. asyncio.wait(FIRST_EXCEPTION)         — aborta al primer error

Las "peticiones" son SIMULADAS con asyncio.sleep() para poder ejecutar
este archivo sin un servidor real.

Latencias simuladas:
  - productos:      200 ms  (rápido)
  - categorias:     100 ms  (el más rápido)
  - perfil:         500 ms  (lento)
  - notificaciones: TIMEOUT (dura 10 s pero hay timeout de 3 s)

Ejecutar:
    python comparacion_coordinacion.py
"""

import asyncio
import time
import logging
from dataclasses import dataclass, field
from typing import Any

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("coordinacion")

# ─── Constantes de simulación ─────────────────────────────────────────────────
BASE_URL = "http://localhost:3000/api"   # solo referencia; no se usa
TIMEOUT_DASHBOARD = 3.0                  # segundos — SLA del dashboard

# Latencias en milisegundos para cada "endpoint"
LATENCIAS_MS = {
    "productos":      200,
    "categorias":     100,
    "perfil":         500,
    "notificaciones": 10_000,  # simula endpoint muy lento / colgado
}

TIMEOUT_INDIVIDUAL = {
    "productos":      3.0,
    "categorias":     3.0,
    "perfil":         3.0,
    "notificaciones": 3.0,   # se agotará porque dura 10 s
}

# ─── Datos simulados que devolvería el API ────────────────────────────────────
DATOS_SIMULADOS = {
    "productos": {
        "total": 42,
        "items": [
            {"id": 1, "nombre": "Manzana Orgánica", "precio": 25.0, "categoria": "Frutas"},
            {"id": 2, "nombre": "Leche de Almendra", "precio": 89.0, "categoria": "Lácteos"},
        ],
    },
    "categorias": {
        "total": 8,
        "items": ["Frutas", "Verduras", "Lácteos", "Granos", "Bebidas", "Snacks", "Carnes", "Otros"],
    },
    "perfil": {
        "id": 7,
        "nombre": "María García",
        "email": "maria@ecomarket.mx",
        "rol": "admin",
        "ultima_sesion": "2026-05-18T10:30:00Z",
    },
    "notificaciones": {
        "total": 3,
        "items": [
            {"id": 101, "mensaje": "Stock bajo en Manzana Orgánica", "tipo": "alerta"},
            {"id": 102, "mensaje": "Nuevo pedido #8821",             "tipo": "info"},
        ],
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIÓN SIMULADORA DE PETICIÓN HTTP
# ═══════════════════════════════════════════════════════════════════════════════

async def simular_peticion(nombre: str, duracion_ms: int, datos: dict) -> dict:
    """
    Simula una petición HTTP con latencia realista y logging detallado.

    Args:
        nombre:      Nombre del endpoint (p.ej. "productos").
        duracion_ms: Milisegundos que tarda en responder.
        datos:       Payload que devolvería el servidor.

    Returns:
        dict con 'endpoint', 'datos' y 'duracion_ms'.

    Raises:
        asyncio.TimeoutError si se cancela desde fuera (via wait_for).
    """
    t0 = time.monotonic()
    logger.info("  → [%s] iniciando petición (latencia simulada: %d ms)", nombre, duracion_ms)

    await asyncio.sleep(duracion_ms / 1000)  # ← simula la latencia de red

    t1 = time.monotonic()
    duracion_real = (t1 - t0) * 1000
    logger.info("  ← [%s] respuesta recibida en %.0f ms ✓", nombre, duracion_real)

    return {
        "endpoint": nombre,
        "datos": datos,
        "duracion_ms": round(duracion_real),
    }


async def simular_peticion_con_timeout(nombre: str) -> dict:
    """
    Wrapper que aplica el timeout individual definido en TIMEOUT_INDIVIDUAL.
    Lanza asyncio.TimeoutError si el endpoint supera su límite.
    """
    duracion_ms = LATENCIAS_MS[nombre]
    datos = DATOS_SIMULADOS[nombre]
    timeout_s = TIMEOUT_INDIVIDUAL[nombre]

    try:
        return await asyncio.wait_for(
            simular_peticion(nombre, duracion_ms, datos),
            timeout=timeout_s,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "  ✗ [%s] TIMEOUT tras %.1f s (latencia: %d ms)",
            nombre, timeout_s, duracion_ms,
        )
        raise


# ═══════════════════════════════════════════════════════════════════════════════
# DATACLASS DE RESULTADOS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ResultadoEstrategia:
    """Métricas capturadas durante la ejecución de una estrategia."""
    nombre: str
    tiempo_primer_dato_s: float | None = None   # tiempo hasta recibir el 1er dato
    tiempo_total_s: float = 0.0                  # tiempo hasta que la estrategia terminó
    datos_obtenidos: int = 0                     # cuántos endpoints respondieron con éxito
    comportamiento_timeout: str = ""             # descripción de cómo manejó el timeout
    errores: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
# ESTRATEGIA 1: asyncio.gather()
# ═══════════════════════════════════════════════════════════════════════════════

async def estrategia_gather() -> ResultadoEstrategia:
    """
    Estrategia 1: gather() — espera TODOS los resultados antes de continuar.

    Usa return_exceptions=True para que un timeout en 'notificaciones' no
    cancele las demás tareas. Analiza los resultados post-gather.

    Característica clave: el tiempo total es el de la tarea más lenta
    que no haga timeout (aquí: perfil a 500 ms, porque notificaciones
    tiene timeout a 3 s pero está limitado a 3 s).
    """
    resultado = ResultadoEstrategia(nombre="gather(return_exceptions=True)")
    t0 = time.monotonic()
    primer_dato_registrado = False

    logger.info("\n[Estrategia 1] asyncio.gather() con return_exceptions=True")

    nombres = ["productos", "categorias", "perfil", "notificaciones"]
    corrutinas = [simular_peticion_con_timeout(n) for n in nombres]

    # gather NO entrega resultados parciales: esperamos todos antes de procesar
    resultados_raw = await asyncio.gather(*corrutinas, return_exceptions=True)

    t_gather_fin = time.monotonic() - t0

    for nombre, raw in zip(nombres, resultados_raw):
        if isinstance(raw, Exception):
            resultado.errores.append(f"{nombre}: {type(raw).__name__}")
            logger.info("  ⚠ [%s] excepción: %s", nombre, type(raw).__name__)
        else:
            resultado.datos_obtenidos += 1
            if not primer_dato_registrado:
                # Con gather no hay "primer dato real" hasta que termina todo;
                # anotamos el momento en que procesamos el primer éxito post-gather
                resultado.tiempo_primer_dato_s = round(t_gather_fin, 3)
                primer_dato_registrado = True
            logger.info("  ✓ [%s] datos procesados", nombre)

    resultado.tiempo_total_s = round(t_gather_fin, 3)
    resultado.comportamiento_timeout = (
        "Continúa con los demás — el timeout de 'notificaciones' se convierte en "
        "excepción capturada. El dashboard carga en max(200, 100, 500) ≈ 500 ms + overhead."
    )
    return resultado


# ═══════════════════════════════════════════════════════════════════════════════
# ESTRATEGIA 2: asyncio.wait(FIRST_COMPLETED)
# ═══════════════════════════════════════════════════════════════════════════════

async def estrategia_wait_first_completed() -> ResultadoEstrategia:
    """
    Estrategia 2: wait(FIRST_COMPLETED) — procesa cada resultado en cuanto llega.

    Permite renderizado progresivo: mostramos categorías apenas llegan (100 ms)
    sin esperar a perfil (500 ms) ni a notificaciones (timeout).

    Característica clave: `tiempo_primer_dato` ≈ 100 ms (categorias).
    """
    resultado = ResultadoEstrategia(nombre="wait(FIRST_COMPLETED)")
    t0 = time.monotonic()

    logger.info("\n[Estrategia 2] asyncio.wait(return_when=FIRST_COMPLETED)")

    nombres = ["productos", "categorias", "perfil", "notificaciones"]
    tareas = {
        asyncio.create_task(simular_peticion_con_timeout(n), name=n): n
        for n in nombres
    }
    pendientes = set(tareas.keys())

    while pendientes:
        completadas, pendientes = await asyncio.wait(
            pendientes,
            return_when=asyncio.FIRST_COMPLETED,
        )

        for tarea in completadas:
            nombre_tarea = tarea.get_name()
            t_ahora = time.monotonic() - t0

            if tarea.exception():
                exc = tarea.exception()
                resultado.errores.append(f"{nombre_tarea}: {type(exc).__name__}")
                logger.info(
                    "  ⚠ [%s] excepción en t=%.3f s: %s",
                    nombre_tarea, t_ahora, type(exc).__name__,
                )
            else:
                resultado.datos_obtenidos += 1
                if resultado.tiempo_primer_dato_s is None:
                    resultado.tiempo_primer_dato_s = round(t_ahora, 3)
                    logger.info(
                        "  🎯 PRIMER DATO [%s] disponible en %.3f s — podría renderizarse ya",
                        nombre_tarea, t_ahora,
                    )
                else:
                    logger.info("  ✓ [%s] datos disponibles en t=%.3f s", nombre_tarea, t_ahora)

    resultado.tiempo_total_s = round(time.monotonic() - t0, 3)
    resultado.comportamiento_timeout = (
        "Continúa procesando — cada resultado llega individualmente. "
        "El UI puede mostrar categorías en ~100 ms y perfil en ~500 ms "
        "sin esperar el timeout de notificaciones."
    )
    return resultado


# ═══════════════════════════════════════════════════════════════════════════════
# ESTRATEGIA 3: asyncio.as_completed()
# ═══════════════════════════════════════════════════════════════════════════════

async def estrategia_as_completed() -> ResultadoEstrategia:
    """
    Estrategia 3: as_completed() — iterador que entrega futuros en orden de finalización.

    Similar a FIRST_COMPLETED pero más pythónico: un bucle `for` sobre el iterador.
    Cada iteración obtiene el SIGUIENTE futuro que terminó (sea éxito o excepción).

    Característica clave: más legible que wait() en bucle; mismo comportamiento temporal.
    """
    resultado = ResultadoEstrategia(nombre="as_completed()")
    t0 = time.monotonic()

    logger.info("\n[Estrategia 3] asyncio.as_completed()")

    nombres = ["productos", "categorias", "perfil", "notificaciones"]
    corrutinas = [simular_peticion_con_timeout(n) for n in nombres]

    for futuro in asyncio.as_completed(corrutinas):
        t_ahora = time.monotonic() - t0
        try:
            datos = await futuro
            resultado.datos_obtenidos += 1
            if resultado.tiempo_primer_dato_s is None:
                resultado.tiempo_primer_dato_s = round(t_ahora, 3)
                logger.info(
                    "  🎯 PRIMER DATO [%s] en %.3f s",
                    datos["endpoint"], t_ahora,
                )
            else:
                logger.info(
                    "  ✓ [%s] disponible en t=%.3f s",
                    datos["endpoint"], t_ahora,
                )
        except asyncio.TimeoutError:
            resultado.errores.append(f"timeout en t={t_ahora:.3f}s")
            logger.info("  ⚠ TIMEOUT en t=%.3f s", t_ahora)
        except Exception as exc:
            resultado.errores.append(str(exc))
            logger.info("  ✗ Error en t=%.3f s: %s", t_ahora, exc)

    resultado.tiempo_total_s = round(time.monotonic() - t0, 3)
    resultado.comportamiento_timeout = (
        "El iterador simplemente devuelve la excepción de timeout como el "
        "último elemento; los demás endpoints ya fueron procesados antes. "
        "Código más limpio que FIRST_COMPLETED para este patrón."
    )
    return resultado


# ═══════════════════════════════════════════════════════════════════════════════
# ESTRATEGIA 4: asyncio.wait(FIRST_EXCEPTION)
# ═══════════════════════════════════════════════════════════════════════════════

async def estrategia_wait_first_exception() -> ResultadoEstrategia:
    """
    Estrategia 4: wait(FIRST_EXCEPTION) — retorna al primer error O al terminar todas.

    Si alguna tarea lanza excepción, `wait` retorna inmediatamente con las tareas
    completadas hasta ese momento. Las tareas pendientes se cancelan explícitamente.

    Característica clave: reacciona rápido a fallos, pero sacrifica datos parciales.
    Si notificaciones falla (timeout) antes que perfil termine, perdemos el perfil.

    NOTA: En nuestro escenario, categorías (100ms) y productos (200ms) terminan ANTES
    del timeout de notificaciones (3s), así que se obtienen. Perfil (500ms) también
    termina antes. El timeout ocurre a los 3s y cancela solo a notificaciones.
    """
    resultado = ResultadoEstrategia(nombre="wait(FIRST_EXCEPTION)")
    t0 = time.monotonic()

    logger.info("\n[Estrategia 4] asyncio.wait(return_when=FIRST_EXCEPTION)")

    nombres = ["productos", "categorias", "perfil", "notificaciones"]
    tareas = {
        asyncio.create_task(simular_peticion_con_timeout(n), name=n): n
        for n in nombres
    }

    completadas, pendientes = await asyncio.wait(
        tareas.keys(),
        return_when=asyncio.FIRST_EXCEPTION,
    )

    t_retorno = time.monotonic() - t0

    # Procesar tareas completadas (pueden ser éxitos o la excepción que disparó el retorno)
    for tarea in completadas:
        nombre_tarea = tarea.get_name()
        if tarea.exception():
            exc = tarea.exception()
            resultado.errores.append(f"{nombre_tarea}: {type(exc).__name__}")
            logger.info(
                "  ⚠ [%s] excepción que disparó FIRST_EXCEPTION: %s",
                nombre_tarea, type(exc).__name__,
            )
        else:
            resultado.datos_obtenidos += 1
            if resultado.tiempo_primer_dato_s is None:
                resultado.tiempo_primer_dato_s = round(t_retorno, 3)
            logger.info("  ✓ [%s] completada antes de la excepción", nombre_tarea)

    # Cancelar tareas que siguen pendientes
    for tarea in pendientes:
        nombre_tarea = tarea.get_name()
        tarea.cancel()
        try:
            await tarea
        except (asyncio.CancelledError, asyncio.TimeoutError):
            resultado.errores.append(f"{nombre_tarea}: CancelledError")
            logger.info("  ✗ [%s] cancelada (estaba pendiente)", nombre_tarea)

    resultado.tiempo_total_s = round(time.monotonic() - t0, 3)
    resultado.comportamiento_timeout = (
        "wait() retorna en el momento de la primera excepción. "
        "Como categorías (100ms), productos (200ms) y perfil (500ms) "
        "terminan antes del timeout de notificaciones (3s), los 3 se obtienen. "
        "Notificaciones se cancela cuando su wait_for lanza TimeoutError."
    )
    return resultado


# ═══════════════════════════════════════════════════════════════════════════════
# FORMATEO DE RESULTADOS
# ═══════════════════════════════════════════════════════════════════════════════

def _barra(valor: float, maximo: float, ancho: int = 20) -> str:
    """Genera una barra ASCII proporcional al valor."""
    lleno = int((valor / maximo) * ancho) if maximo > 0 else 0
    return "█" * lleno + "░" * (ancho - lleno)


def _score_latencia(r: ResultadoEstrategia) -> int:
    """Puntúa la latencia percibida (primer dato): menor tiempo → mayor puntaje."""
    if r.tiempo_primer_dato_s is None:
        return 1
    t = r.tiempo_primer_dato_s
    if t < 0.15:   return 5
    if t < 0.30:   return 4
    if t < 0.60:   return 3
    if t < 1.50:   return 2
    return 1


def _score_robustez(r: ResultadoEstrategia) -> int:
    """Puntúa robustez: cuántos datos obtuvo ante el timeout."""
    n = r.datos_obtenidos
    if n == 3:   return 5   # obtuvo todos los no-timeout
    if n == 2:   return 3
    if n >= 1:   return 2
    return 1


COMPLEJIDAD_SCORES = {
    "gather(return_exceptions=True)": 5,   # más simple
    "as_completed()":                 4,
    "wait(FIRST_EXCEPTION)":          3,
    "wait(FIRST_COMPLETED)":          2,   # más complejo (bucle manual)
}

MANTENIBILIDAD_SCORES = {
    "gather(return_exceptions=True)": 5,
    "as_completed()":                 4,
    "wait(FIRST_COMPLETED)":          3,
    "wait(FIRST_EXCEPTION)":          3,
}


def imprimir_tabla_comparacion(resultados: list[ResultadoEstrategia]) -> None:
    """Imprime la tabla de comparación de las cuatro estrategias."""
    print("\n" + "═" * 100)
    print("  COMPARACIÓN DE ESTRATEGIAS DE COORDINACIÓN ASYNC — EcoMarket Dashboard")
    print("═" * 100)

    col_est  = 32
    col_t1   = 12
    col_tot  = 10
    col_ok   = 10
    col_comp = 40

    # Encabezado
    print(
        f"  {'Estrategia':<{col_est}} "
        f"{'Primer Dato':>{col_t1}} "
        f"{'Total':>{col_tot}} "
        f"{'Datos OK':>{col_ok}} "
        f"{'Comportamiento ante Timeout':<{col_comp}}"
    )
    print("  " + "─" * 98)

    for r in resultados:
        primer = f"{r.tiempo_primer_dato_s:.3f}s" if r.tiempo_primer_dato_s is not None else "N/A"
        # Truncar el comportamiento para que entre en la tabla
        comp_corto = r.comportamiento_timeout[:col_comp - 3] + "..."  \
                     if len(r.comportamiento_timeout) > col_comp else r.comportamiento_timeout
        print(
            f"  {r.nombre:<{col_est}} "
            f"{primer:>{col_t1}} "
            f"{r.tiempo_total_s:>{col_tot}.3f}s "
            f"{r.datos_obtenidos:>{col_ok}} "
            f"{comp_corto:<{col_comp}}"
        )

    print("  " + "─" * 98)

    # Tabla de puntajes
    print("\n  TABLA DE PUNTAJES (1 = peor, 5 = mejor)")
    print(
        f"  {'Estrategia':<{col_est}} "
        f"{'Lat. Percibida':>15} "
        f"{'Robustez':>9} "
        f"{'Complejidad':>12} "
        f"{'Mantenibilidad':>15} "
        f"{'TOTAL':>7}"
    )
    print("  " + "─" * 66)

    for r in resultados:
        s_lat  = _score_latencia(r)
        s_rob  = _score_robustez(r)
        s_comp = COMPLEJIDAD_SCORES.get(r.nombre, 3)
        s_man  = MANTENIBILIDAD_SCORES.get(r.nombre, 3)
        total  = s_lat + s_rob + s_comp + s_man
        print(
            f"  {r.nombre:<{col_est}} "
            f"{'★' * s_lat + '☆' * (5 - s_lat):>15} "
            f"{'★' * s_rob + '☆' * (5 - s_rob):>9} "
            f"{'★' * s_comp + '☆' * (5 - s_comp):>12} "
            f"{'★' * s_man + '☆' * (5 - s_man):>15} "
            f"{total:>7}/20"
        )

    # Línea de tiempo visual
    print("\n  LÍNEA DE TIEMPO (cada █ ≈ 100 ms, timeout a 3000 ms)")
    max_t = max(r.tiempo_total_s for r in resultados) + 0.1
    for r in resultados:
        barra = _barra(r.tiempo_total_s, max_t, ancho=30)
        primer = (
            f"1er dato: {r.tiempo_primer_dato_s:.0f}ms"
            if r.tiempo_primer_dato_s is not None else "sin datos"
        )
        print(f"  {r.nombre:<32} [{barra}] {r.tiempo_total_s:.2f}s  ({primer})")

    print("═" * 100)


def imprimir_recomendacion(resultados: list[ResultadoEstrategia]) -> None:
    """Imprime la recomendación final para EcoMarket."""
    print("\n" + "─" * 70)
    print("  RECOMENDACIÓN PARA ECOMARKET")
    print("─" * 70)
    print("""
  Para el dashboard de EcoMarket se recomienda una estrategia HÍBRIDA:

  1. NÚCLEO — asyncio.gather(return_exceptions=True)
     Para las 4 peticiones del dashboard. Simple, robusto, fácil de mantener.
     El timeout de notificaciones no cancela productos ni categorías.

  2. PROGRESIVO (futuro) — asyncio.as_completed()
     Cuando el frontend soporte renderizado incremental, migrar a as_completed()
     permite mostrar categorías en ~100 ms sin esperar a perfil (500 ms).

  3. EVITAR wait(FIRST_EXCEPTION) para el dashboard principal
     El dashboard necesita los datos que SÍ están disponibles; abortar todo
     al primer fallo contradice la política de degradación elegante del equipo.

  4. EVITAR wait(FIRST_COMPLETED) como primera opción
     Más potente que gather pero con complejidad extra (bucle manual, gestión
     de conjuntos). Reservar para casos donde realmente se necesite el bucle.

  Regla de oro EcoMarket:
    "Usar gather() por defecto. Migrar a as_completed() cuando el UX
     demande renderizado progresivo. Documentar cada migración como ADR."
""")
    print("─" * 70)


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

async def main() -> None:
    """Ejecuta las cuatro estrategias secuencialmente y compara sus resultados."""
    print("\n" + "═" * 70)
    print("  EcoMarket — Comparación de estrategias de coordinación async")
    print("  Peticiones simuladas (sin servidor real)")
    print("  Latencias: productos=200ms, categorias=100ms, perfil=500ms,")
    print("             notificaciones=TIMEOUT (10s real, límite 3s)")
    print("═" * 70)

    # Ejecutar cada estrategia de forma secuencial para que el output sea legible
    resultados: list[ResultadoEstrategia] = []

    for estrategia_fn in [
        estrategia_gather,
        estrategia_wait_first_completed,
        estrategia_as_completed,
        estrategia_wait_first_exception,
    ]:
        print(f"\n{'─' * 50}")
        resultado = await estrategia_fn()
        resultados.append(resultado)
        print(
            f"  Resultado: {resultado.datos_obtenidos}/3 datos OK, "
            f"tiempo total={resultado.tiempo_total_s:.3f}s, "
            f"errores={len(resultado.errores)}"
        )
        # Pequeña pausa para que los logs sean más legibles
        await asyncio.sleep(0.1)

    # Imprimir la tabla comparativa
    imprimir_tabla_comparacion(resultados)
    imprimir_recomendacion(resultados)


if __name__ == "__main__":
    asyncio.run(main())
