"""
anatomia_event_loop.py — Reto 2: Anatomía del Event Loop de asyncio
====================================================================
Este script DEMUESTRA, paso a paso y con prints detallados, cómo funciona
el event loop de asyncio por dentro cuando se ejecutan múltiples corrutinas
concurrentemente.

Lo que aprenderás
-----------------
  • Qué hace asyncio.run() al iniciar
  • Por qué `await` NO significa "esperar pasivamente"
  • Cómo el event loop INTERCALA la ejecución de corrutinas
  • Por qué /categorias (100 ms) termina ANTES que /productos (300 ms)
    aunque productos fue lanzado primero

No se necesita servidor real: usamos asyncio.sleep() para simular la red.

Semana 3 — Programación del lado del cliente
"""

import asyncio
import time

# ---------------------------------------------------------------------------
# Contador global de pasos para mostrar el orden de ejecución
# ---------------------------------------------------------------------------

_paso = 0

def paso(descripcion: str) -> None:
    """Imprime un paso numerado con timestamp relativo."""
    global _paso
    _paso += 1
    ts = time.perf_counter() - _inicio_global
    print(f"  [PASO {_paso:02d}]  +{ts*1000:6.1f} ms  {descripcion}")


# Marca de tiempo global (se resetea en main)
_inicio_global: float = 0.0


# ===========================================================================
# SECCIÓN 1 — CÓDIGO ORIGINAL (sin prints)
# El gather simple que un estudiante escribiría normalmente
# ===========================================================================

async def _original_obtener_productos() -> dict:
    """Versión limpia (sin prints) — 300 ms de latencia simulada."""
    await asyncio.sleep(0.30)
    return {"endpoint": "/api/productos", "data": ["Laptop", "Camisa", "Aceite"]}


async def _original_obtener_categorias() -> dict:
    """Versión limpia (sin prints) — 100 ms de latencia simulada."""
    await asyncio.sleep(0.10)
    return {"endpoint": "/api/categorias", "data": ["electronica", "ropa", "alimentos"]}


async def _original_obtener_perfil() -> dict:
    """Versión limpia (sin prints) — 200 ms de latencia simulada."""
    await asyncio.sleep(0.20)
    return {"endpoint": "/api/perfil", "data": {"nombre": "Ana García"}}


async def demo_codigo_original() -> None:
    """
    CÓDIGO ORIGINAL — la forma en que lo escribirías normalmente.
    No tiene prints internos; solo muestra la estructura limpia.
    """
    print("\n" + "─" * 64)
    print("  CÓDIGO ORIGINAL (sin instrumentación)")
    print("─" * 64)
    print("""
    async def obtener_productos():
        await asyncio.sleep(0.30)          # simula red 300 ms
        return {...}

    async def obtener_categorias():
        await asyncio.sleep(0.10)          # simula red 100 ms
        return {...}

    async def obtener_perfil():
        await asyncio.sleep(0.20)          # simula red 200 ms
        return {...}

    async def main():
        productos, categorias, perfil = await asyncio.gather(
            obtener_productos(),
            obtener_categorias(),
            obtener_perfil(),
        )
    """)

    t0 = time.perf_counter()
    productos, categorias, perfil = await asyncio.gather(
        _original_obtener_productos(),
        _original_obtener_categorias(),
        _original_obtener_perfil(),
    )
    elapsed = (time.perf_counter() - t0) * 1000

    print(f"  ✓ Completado en {elapsed:.1f} ms (esperado: ~300 ms)")
    print(f"  ✓ productos : {len(productos['data'])} items")
    print(f"  ✓ categorias: {len(categorias['data'])} items")
    print(f"  ✓ perfil    : {perfil['data']['nombre']}")


# ===========================================================================
# SECCIÓN 2 — CÓDIGO INSTRUMENTADO (con prints en cada await)
# Muestra el flujo de ejecución real
# ===========================================================================

async def obtener_datos_con_prints_productos() -> dict:
    """
    Versión instrumentada de GET /api/productos.
    Latencia: 300 ms — será la ÚLTIMA en terminar.
    """
    paso("→ [productos] Corrutina INICIADA — va a hacer la petición HTTP")
    paso("→ [productos] ANTES del await asyncio.sleep(300ms)")
    paso("→ [productos] *** YIELD — cede el control al event loop ***")
    paso("               El event loop puede ejecutar OTRAS corrutinas ahora")

    # ─── EL EVENT LOOP CORRE OTRAS CORRUTINAS MIENTRAS ESPERAMOS ───
    await asyncio.sleep(0.30)
    # ────────────────────────────────────────────────────────────────

    paso("→ [productos] DESPUÉS del await — la respuesta llegó (t+300ms)")
    paso("→ [productos] Procesando datos recibidos...")

    datos = {"endpoint": "/api/productos", "data": ["Laptop", "Camisa", "Aceite"]}
    paso(f"→ [productos] Corrutina TERMINADA — retorna {len(datos['data'])} productos")
    return datos


async def obtener_datos_con_prints_categorias() -> dict:
    """
    Versión instrumentada de GET /api/categorias.
    Latencia: 100 ms — será la PRIMERA en terminar.
    """
    paso("→ [categorias] Corrutina INICIADA — va a hacer la petición HTTP")
    paso("→ [categorias] ANTES del await asyncio.sleep(100ms)")
    paso("→ [categorias] *** YIELD — cede el control al event loop ***")

    # ─── EL EVENT LOOP CORRE OTRAS CORRUTINAS MIENTRAS ESPERAMOS ───
    await asyncio.sleep(0.10)
    # ────────────────────────────────────────────────────────────────

    paso("→ [categorias] DESPUÉS del await — respuesta llegó (t+100ms) ← PRIMERO!")
    datos = {"endpoint": "/api/categorias", "data": ["electronica", "ropa", "alimentos"]}
    paso(f"→ [categorias] Corrutina TERMINADA — retorna {len(datos['data'])} categorías")
    return datos


async def obtener_datos_con_prints_perfil() -> dict:
    """
    Versión instrumentada de GET /api/perfil.
    Latencia: 200 ms — termina SEGUNDA.
    """
    paso("→ [perfil]     Corrutina INICIADA — va a hacer la petición HTTP")
    paso("→ [perfil]     ANTES del await asyncio.sleep(200ms)")
    paso("→ [perfil]     *** YIELD — cede el control al event loop ***")

    # ─── EL EVENT LOOP CORRE OTRAS CORRUTINAS MIENTRAS ESPERAMOS ───
    await asyncio.sleep(0.20)
    # ────────────────────────────────────────────────────────────────

    paso("→ [perfil]     DESPUÉS del await — respuesta llegó (t+200ms)")
    datos = {"endpoint": "/api/perfil", "data": {"nombre": "Ana García", "rol": "admin"}}
    paso("→ [perfil]     Corrutina TERMINADA")
    return datos


async def demo_con_prints() -> None:
    """
    Ejecuta las 3 corrutinas con gather() y muestra el orden real
    de ejecución con pasos numerados.

    CONCEPTOS CLAVE que se demuestran aquí:
    ─────────────────────────────────────────
    1. gather() LANZA las 3 corrutinas casi simultáneamente
    2. Cada await SUSPENDE la corrutina y devuelve el control al event loop
    3. El event loop DECIDE cuál corrutina reanudar (la que tiene I/O listo)
    4. categorias termina primero (100ms) aunque fue lanzada después de productos
    5. Todo ocurre en UN SOLO HILO — no hay paralelismo real, sino concurrencia
    """
    global _paso, _inicio_global
    _paso = 0

    print("\n" + "─" * 64)
    print("  CÓDIGO INSTRUMENTADO — Orden real de ejecución")
    print("─" * 64)
    print()
    print("  INICIO: asyncio.gather() lanza las 3 corrutinas...")
    print()

    _inicio_global = time.perf_counter()

    # gather() crea 3 Tasks y las programa en el event loop.
    # Luego hace await, cediendo el control para que el event loop
    # las ejecute de forma intercalada.
    productos, categorias, perfil = await asyncio.gather(
        obtener_datos_con_prints_productos(),
        obtener_datos_con_prints_categorias(),
        obtener_datos_con_prints_perfil(),
    )

    elapsed = (time.perf_counter() - _inicio_global) * 1000
    print()
    print(f"  FIN: gather() completado en {elapsed:.1f} ms")
    print(f"  ✓ productos : {productos['data']}")
    print(f"  ✓ categorias: {categorias['data']}")
    print(f"  ✓ perfil    : {perfil['data']}")


# ===========================================================================
# SECCIÓN 3 — Demostración de Tasks explícitas con create_task
# ===========================================================================

async def demo_create_task() -> None:
    """
    Muestra la diferencia entre await directo y asyncio.create_task().

    create_task() es lo que gather() hace internamente: convierte una
    corrutina en una Task que el event loop puede ejecutar de forma
    independiente.
    """
    global _paso, _inicio_global
    _paso = 0
    _inicio_global = time.perf_counter()

    print("\n" + "─" * 64)
    print("  DEMO: create_task() — Cómo el event loop maneja Tasks")
    print("─" * 64)
    print()

    paso("asyncio.run() → crea el event loop → programa main() como Task #0")
    paso("create_task(productos)  → Task #1 en cola del event loop")
    paso("create_task(categorias) → Task #2 en cola del event loop")
    paso("create_task(perfil)     → Task #3 en cola del event loop")
    paso("await task_productos → YIELD: event loop toma el control")
    paso("Event loop ejecuta Task #2 (categorias) — asyncio.sleep(100ms)")
    paso("Event loop ejecuta Task #3 (perfil)     — asyncio.sleep(200ms)")
    paso("t+100ms: categorias I/O listo → event loop reanuda Task #2")
    paso("t+200ms: perfil I/O listo     → event loop reanuda Task #3")
    paso("t+300ms: productos I/O listo  → event loop reanuda Task #1")
    paso("Todas las Tasks terminadas → gather() retorna resultados")
    print()

    t0 = time.perf_counter()

    # Crear tasks explícitas (es lo que gather hace internamente)
    task_productos  = asyncio.create_task(
        _original_obtener_productos(),  name="Task-productos"
    )
    task_categorias = asyncio.create_task(
        _original_obtener_categorias(), name="Task-categorias"
    )
    task_perfil     = asyncio.create_task(
        _original_obtener_perfil(),     name="Task-perfil"
    )

    # Esperar a que todas terminen
    productos  = await task_productos
    categorias = await task_categorias
    perfil     = await task_perfil

    elapsed = (time.perf_counter() - t0) * 1000
    print(f"  ✓ Completado con create_task() en {elapsed:.1f} ms")
    print(f"  ✓ Nombres de tasks: {task_productos.get_name()}, "
          f"{task_categorias.get_name()}, {task_perfil.get_name()}")


# ===========================================================================
# SECCIÓN 4 — Diagrama temporal ASCII
# ===========================================================================

def imprimir_diagrama_temporal() -> None:
    """
    Imprime un diagrama ASCII que muestra la ejecución intercalada
    de las tres corrutinas en el tiempo.
    """
    print("\n" + "─" * 64)
    print("  DIAGRAMA TEMPORAL — Ejecución concurrente en un solo hilo")
    print("─" * 64)
    print("""
  Tiempo →   0ms         100ms        200ms        300ms
             |            |            |            |
  HILO 1     ─────────────────────────────────────────────
  (único)    ↑            ↑            ↑            ↑
             │            │            │            │
  productos  [inicio]     [esperando] [esperando]  [FIN ✓]
             ─────────────────────────────────────────────

  categorias [inicio][FIN ✓]
             ──────────────

  perfil     [inicio]     [esperando] [FIN ✓]
             ───────────────────────────────

  Event      lanza        reactiva     reactiva    reactiva
  Loop:      3 tasks      categorias   perfil      productos

  TIEMPO TOTAL: ~300 ms (no 600 ms = 300+100+200)
  ¡Ahorramos ~300 ms sin usar múltiples hilos!
""")
    print("  CONCEPTO CORREGIDO:")
    print("  ┌─────────────────────────────────────────────────────┐")
    print("  │  ❌ INCORRECTO: 'await espera pasivamente'          │")
    print("  │  ✅ CORRECTO:   'await CEDE EL CONTROL al event     │")
    print("  │                  loop para que ejecute otras tasks'  │")
    print("  └─────────────────────────────────────────────────────┘")
    print()
    print("  Cuando una corrutina hace `await asyncio.sleep(300ms)`:")
    print("  1. La corrutina SE SUSPENDE (no bloquea el hilo)")
    print("  2. El event loop CONTINÚA ejecutando otras corrutinas")
    print("  3. A los 300ms, el event loop REANUDA la corrutina suspendida")
    print("  4. Todo esto en un ÚNICO HILO de Python")
    print()


# ===========================================================================
# SECCIÓN 5 — Comparación await secuencial vs gather
# ===========================================================================

async def demo_secuencial_vs_concurrente() -> None:
    """
    Muestra la diferencia de tiempo entre esperar en secuencia
    (un await tras otro) y esperar en paralelo (gather).

    Esta es la demostración más importante: el MISMO código asíncrono
    puede ser lento si no se usa gather() correctamente.
    """
    print("\n" + "─" * 64)
    print("  ⚠  TRAMPA COMÚN: await secuencial NO es concurrente")
    print("─" * 64)

    # ── Secuencial (MAL) ────────────────────────────────────────
    print("\n  ❌ Forma INCORRECTA (secuencial — pierde la concurrencia):")
    print("     productos  = await obtener_productos()   # espera 300ms")
    print("     categorias = await obtener_categorias()  # luego 100ms")
    print("     perfil     = await obtener_perfil()      # luego 200ms")
    print("     # Total: 600ms — igual que síncrono")

    t0 = time.perf_counter()
    p = await _original_obtener_productos()
    c = await _original_obtener_categorias()
    f = await _original_obtener_perfil()
    t_secuencial = (time.perf_counter() - t0) * 1000
    print(f"     → Tiempo real: {t_secuencial:.1f} ms")

    # ── Concurrente (BIEN) ───────────────────────────────────────
    print("\n  ✅ Forma CORRECTA (concurrente con gather):")
    print("     productos, categorias, perfil = await asyncio.gather(")
    print("         obtener_productos(),")
    print("         obtener_categorias(),")
    print("         obtener_perfil(),")
    print("     )")
    print("     # Total: ~300ms — solo el más lento")

    t0 = time.perf_counter()
    p, c, f = await asyncio.gather(
        _original_obtener_productos(),
        _original_obtener_categorias(),
        _original_obtener_perfil(),
    )
    t_concurrente = (time.perf_counter() - t0) * 1000
    print(f"     → Tiempo real: {t_concurrente:.1f} ms")

    speedup = t_secuencial / t_concurrente
    print(f"\n  📊 Speedup: {speedup:.1f}x más rápido con gather()")
    print(f"     ({t_secuencial:.0f} ms → {t_concurrente:.0f} ms)")


# ===========================================================================
# main — Ejecuta todas las demos en orden
# ===========================================================================

async def main() -> None:
    print("=" * 64)
    print("  Reto 2 — Anatomía del Event Loop de asyncio")
    print("  EcoMarket — Semana 3")
    print("=" * 64)

    # 1. Código original limpio
    await demo_codigo_original()

    # 2. Código instrumentado con pasos
    await demo_con_prints()

    # 3. Diagrama temporal ASCII
    imprimir_diagrama_temporal()

    # 4. Demo con create_task explícito
    await demo_create_task()

    # 5. Trampa: await secuencial vs gather
    await demo_secuencial_vs_concurrente()

    print("\n" + "=" * 64)
    print("  Resumen de conceptos demostrados:")
    print("  ✓ asyncio.run() crea el event loop y ejecuta main()")
    print("  ✓ gather() convierte corrutinas en Tasks concurrentes")
    print("  ✓ await YIELD el control — no bloquea el hilo")
    print("  ✓ El event loop reactiva corrutinas cuando el I/O está listo")
    print("  ✓ categorias terminó antes aunque productos fue lanzado primero")
    print("  ✓ await secuencial = secuencial; gather = concurrente")
    print("=" * 64)


if __name__ == "__main__":
    asyncio.run(main())
