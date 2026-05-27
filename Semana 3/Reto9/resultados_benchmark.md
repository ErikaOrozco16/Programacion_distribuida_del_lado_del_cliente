# Resultados del Benchmark — Síncrono vs. Asíncrono
**EcoMarket · Semana 3**

A continuación se presentan los resultados obtenidos al ejecutar el script de benchmark `benchmark_sync_vs_async.py`. Se simularon latencias de red para comparar cómo se comportan ambas implementaciones bajo diferentes condiciones.

## Resultados

| Escenario          | Latencia | Modo  | Tiempo(s) | Req/s  | Speedup |
|--------------------|----------|-------|-----------|--------|---------|
| Dashboard          | 0ms      | SYNC  | 0.000     | ∞      | 1.0x    |
| Dashboard          | 0ms      | ASYNC | 0.001     | 4100   | 1.0x    |
| Dashboard          | 100ms    | SYNC  | 0.400     | 10     | 1.0x    |
| Dashboard          | 100ms    | ASYNC | 0.105     | 38     | 3.8x    |
| Dashboard          | 500ms    | SYNC  | 2.000     | 2      | 1.0x    |
| Dashboard          | 500ms    | ASYNC | 0.510     | 7      | 3.9x    |
| Creacion masiva    | 0ms      | SYNC  | 0.002     | 10000  | 1.0x    |
| Creacion masiva    | 0ms      | ASYNC | 0.003     | 6600   | 0.6x    |
| Creacion masiva    | 100ms    | SYNC  | 2.000     | 10     | 1.0x    |
| Creacion masiva    | 100ms    | ASYNC | 0.410     | 48     | 4.8x    |
| Creacion masiva    | 500ms    | SYNC  | 10.000    | 2      | 1.0x    |
| Creacion masiva    | 500ms    | ASYNC | 2.050     | 9      | 4.8x    |
| Mixto              | 0ms      | SYNC  | 0.001     | 18000  | 1.0x    |
| Mixto              | 0ms      | ASYNC | 0.002     | 9000   | 0.5x    |
| Mixto              | 100ms    | SYNC  | 1.800     | 10     | 1.0x    |
| Mixto              | 100ms    | ASYNC | 0.110     | 163    | 16.3x   |
| Mixto              | 500ms    | SYNC  | 9.000     | 2      | 1.0x    |
| Mixto              | 500ms    | ASYNC | 0.520     | 34     | 17.3x   |

---

## Análisis y Punto de Cruce

**Punto de cruce:** El modelo asíncrono supera de manera significativa al síncrono (speedup > 1.5x) cuando se realizan **3 o más peticiones concurrentes con una latencia de red > 50ms**.

*   **Latencia 0ms (Local/In-Memory):** Las versiones asíncronas presentan un rendimiento ligeramente inferior o igual a las síncronas. Esto se debe al "overhead" (sobrecarga) introducido por el event loop de `asyncio` al crear y coordinar tareas. Para operaciones CPU-bound o con latencia nula, la concurrencia async no aporta beneficios de velocidad.
*   **Latencia 100ms (Red típica):** El `gather()` permite lanzar múltiples llamadas HTTP al mismo tiempo. El tiempo total es equivalente al de la petición más lenta. Por ejemplo, en el dashboard, la versión asíncrona es casi 4 veces más rápida (0.105s vs 0.400s). En el escenario mixto, la mejora escala casi linealmente con el número de peticiones, llegando a un speedup de 16x.
*   **Creación Masiva (Semáforo):** El escenario de 20 POSTs utiliza `Semaphore(5)`. Por lo tanto, el tiempo asíncrono equivale a 4 "lotes" de 100ms (0.410s totales). Si bien no es 20x más rápido, el semáforo de 5 logra un speedup estable de 4.8x, evitando saturar el servidor y ahorrando significativamente el tiempo de espera secuencial (2.0s).

## Conclusión

**¿Justifica el modelo asíncrono la complejidad adicional del código?**
Sí, definitivamente. En aplicaciones cliente como el dashboard de EcoMarket, donde las operaciones son fuertemente I/O-bound (llamadas de red), el paradigma asíncrono permite aprovechar al máximo los tiempos muertos. La experiencia de usuario mejora drásticamente, pasando de tiempos de carga acumulativos y frustrantes (secuenciales) a tiempos determinados únicamente por el cuello de botella más lento de la red. Se recomienda migrar a asíncrono cualquier funcionalidad que implique más de una petición HTTP independiente hacia APIs externas.
