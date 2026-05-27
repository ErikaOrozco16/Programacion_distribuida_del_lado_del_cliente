# Medición de Tiempos: Síncrono vs Asíncrono
## Reto 3 — EcoMarket Async Client

---

## Tabla Comparativa

| Métrica | Enfoque **Síncrono** | Enfoque **Asíncrono** | Mejora |
|---|---|---|---|
| Nº de peticiones | 3 (productos, categorias, perfil) | 3 (productos, categorias, perfil) | — |
| Tiempo petición 1 (productos) | ~500 ms | ~500 ms | — |
| Tiempo petición 2 (categorias) | ~480 ms | ~480 ms | — |
| Tiempo petición 3 (perfil) | ~520 ms | ~520 ms | — |
| **Tiempo total medido** | **~1 500 ms** | **~530 ms** | **≈ 2.8×** |
| Bloquea el hilo principal | **Sí** ❌ | No ✅ | — |
| Puede hacer otras tareas mientras espera | No ❌ | **Sí** ✅ | — |

> **Nota:** los valores de la tabla son representativos. Los tiempos reales dependen
> de la latencia de red y de la carga del servidor. En una red local (`localhost`)
> los tiempos suelen estar entre 10 ms y 150 ms por petición.

---

## ¿Por Qué el Async es Más Rápido?

### Modelo síncrono (bloqueante)

```
Thread principal
│
├─► GET /productos  ──────────────── 500 ms ──► respuesta
│                                                       │
│                   GET /categorias  ── 480 ms ──► resp │
│                                                       │
│                               GET /perfil  ── 520 ms ──► resp
│
└── TOTAL: 500 + 480 + 520 = 1 500 ms
```

Con `requests.get()`, cada llamada **bloquea el hilo** hasta recibir la respuesta.
Las peticiones se ejecutan en serie: la segunda no comienza hasta que la primera
ha terminado.

### Modelo asíncrono (no bloqueante)

```
Event Loop
│
├─► GET /productos    ────────────────────────────────── 500 ms ──► resp
├─► GET /categorias   ──────────────────────────── 480 ms ──► resp
└─► GET /perfil       ──────────────────────────────────────── 520 ms ──► resp
│
Todas empiezan SIMULTÁNEAMENTE
│
└── TOTAL: max(500, 480, 520) ≈ 530 ms  (+ overhead mínimo del event loop)
```

Con `asyncio.gather()`, el event loop lanza las tres coroutines y **cede el control**
cada vez que una espera I/O (red). Mientras `GET /productos` espera respuesta del
servidor, el event loop avanza con `GET /categorias` y `GET /perfil`.

**La clave**: el tiempo total es ≈ el de la petición **más lenta**, no la *suma* de todas.

---

## Detalles de Implementación — `cargar_dashboard()`

```python
async def cargar_dashboard() -> dict:
    async with aiohttp.ClientSession(timeout=TIMEOUT_POR_PETICION) as session:
        resultados = await asyncio.gather(
            listar_productos(session),    # lanza las 3 coroutines
            obtener_categorias(session),  # en paralelo dentro del
            obtener_perfil(session),      # mismo event loop
            return_exceptions=True,       # ← no abortar si una falla
        )
    return _procesar_resultados(resultados, ["productos", "categorias", "perfil"])
```

### `return_exceptions=True` — Por Qué es Crítico

Sin este parámetro, si **cualquiera** de las tres peticiones lanza una excepción,
`gather()` la propaga inmediatamente y **cancela las otras**. Perderíamos los datos
de las peticiones que sí tuvieron éxito.

Con `return_exceptions=True`:
- Las excepciones se incluyen en la lista de resultados (en el mismo índice).
- `_procesar_resultados()` las separa de los datos válidos.
- El llamador recibe todo lo que se pudo obtener, más la lista de errores.

---

## El Semáforo en `crear_multiples_productos()`

### Problema sin semáforo

Si se crean 100 productos, se lanzarían 100 peticiones HTTP **simultáneas**.
Esto puede:
- Saturar el servidor y provocar errores 429 (Too Many Requests).
- Agotar el pool de conexiones del sistema operativo.
- Generar latencia mayor por congestión que si fueran en lotes.

### Solución: `asyncio.Semaphore(MAX_CONCURRENTE)`

```python
semaforo = asyncio.Semaphore(5)  # máximo 5 peticiones en vuelo

async def _crear_con_limite(session, datos):
    async with semaforo:          # ← bloquea aquí si ya hay 5 activas
        return await crear_producto(session, datos)
```

**Funcionamiento:**

```
t=0ms   Peticiones 1-5 adquieren el semáforo → enviadas
        Peticiones 6-10 ESPERAN (semáforo en 0)

t=80ms  Petición 3 termina → libera semáforo → Petición 6 entra
t=95ms  Petición 1 termina → libera semáforo → Petición 7 entra
...
```

El semáforo garantiza que **como máximo** `MAX_CONCURRENTE = 5` peticiones
estén en vuelo en cualquier instante, respetando al servidor sin sacrificar
el paralelismo.

### Comparativa con semáforo

| Configuración | 10 productos | 50 productos |
|---|---|---|
| Sin semáforo (todo a la vez) | ~150 ms | riesgo de 429 |
| Semáforo(5) | ~300 ms | ~1 500 ms |
| Semáforo(1) = secuencial | ~1 500 ms | ~7 500 ms |

> El semáforo en 5 equilibra **velocidad** y **cortesía con el servidor**.

---

## Cómo Ejecutar la Medición

```powershell
# Asegúrate de que el servidor EcoMarket esté corriendo en localhost:3000
cd "c:\Users\hp\Desktop\6to semestre\Programacion del lado del cliente\semana3\Reto3"
python cliente_async_ecomarket.py
```

Salida esperada:

```
════════════════════════════════════════════════════════════
  PRUEBA 1 — cargar_dashboard() asíncrono
════════════════════════════════════════════════════════════

Tiempo asíncrono (3 peticiones en paralelo): 0.547 s
[Referencia] Si fueran secuenciales, el tiempo sería ≈ 1.532 s
  → El paralelismo reduce el tiempo al de la petición más lenta,
    no a la SUMA de todas.
  ✓ productos: 24 elementos
  ✓ categorias: 5 elementos
  ✓ perfil: {'nombre': 'EcoAdmin', 'email': 'admin@ecomarket.com', ...}

════════════════════════════════════════════════════════════
  PRUEBA 2 — crear_multiples_productos() con 10 productos
════════════════════════════════════════════════════════════

Tiempo total (10 productos, semáforo=5): 0.612 s
  ✓ Creados exitosamente : 10
  ✗ Fallidos             : 0

Primeros 3 creados:
    id=101  nombre='Producto EcoTest 1'  precio=15.49
    id=102  nombre='Producto EcoTest 2'  precio=20.99
    id=103  nombre='Producto EcoTest 3'  precio=26.49

════════════════════════════════════════════════════════════
  RESUMEN
════════════════════════════════════════════════════════════
  Dashboard (3 req en paralelo)  : 0.547 s
  Creación masiva (10 productos) : 0.612 s
  Semáforo usado                 : MAX_CONCURRENTE = 5
```
