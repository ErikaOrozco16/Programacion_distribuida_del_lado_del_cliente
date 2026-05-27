# Configuración Óptima del Pool de Conexiones
**EcoMarket · Semana 3**

En este documento se describe cómo el cliente de EcoMarket utiliza un pool de conexiones inteligente, extendiendo el comportamiento base de `aiohttp.ClientSession` mediante un `SmartSession`.

## Conceptos Clave

*   **`TCPConnector`**: Es la clase de `aiohttp` responsable de mantener y administrar un pool interno de conexiones HTTP/HTTPS abiertas (keep-alive) para su reutilización a lo largo de la sesión.
*   **`limit`**: Especifica el número total de conexiones simultáneas que el pool permite mantener en vuelo al mismo tiempo para todas las combinaciones de host/puerto.
*   **`keepalive_timeout`**: Determina cuántos segundos se mantendrá abierta una conexión TCP inactiva antes de que el conector la cierre automáticamente. 

## Benchmark de Configuraciones

Se simuló la carga de 50 peticiones concurrentes para probar tres configuraciones distintas de pool.

| Configuración | Descripción | Tiempo (s) | Req/s |
|---|---|---|---|
| Pool Pequeño | `limit=5` | ~1.01 s | ~49.5 |
| Pool Mediano | `limit=20` | ~0.31 s | ~161.2 |
| Ilimitado | `limit=0` | ~0.10 s | ~500.0 |

*   *Pool Pequeño (5)*: Actúa como un cuello de botella. Las 50 peticiones deben esperar en cola a que se desocupen los 5 slots disponibles, demorando la carga total de manera secuencial (10 bloques de 5).
*   *Pool Mediano (20)*: Mejora considerablemente el throughput.
*   *Ilimitado (0)*: Dispara todas las peticiones a la vez. En simulación es el más rápido, pero en el mundo real, disparar un número muy grande de conexiones ahoga los puertos disponibles en el cliente, consume sockets locales y resulta en respuestas 429 Too Many Requests o caída del servidor HTTP (`ConnectionResetError`).

## Fórmula Recomendada
La regla heurística común para decidir el tamaño del pool (conexiones) es estimar la concurrencia esperada y multiplicarla por un factor de seguridad:

`pool_size = expected_concurrent_requests * 1.5`

## Recomendación para EcoMarket

Para la aplicación cliente de EcoMarket, donde las pantallas como el dashboard hacen 4-5 requests y las cargas masivas tienen un semáforo de 5, el `expected_concurrent_requests` se estima en aproximadamente 10 peticiones (si el usuario hace cargas masivas de fondo mientras navega). 

Configuración recomendada para la instanciación del `SmartSession`:
*   `limit = 15`: 10 * 1.5. Proporciona espacio suficiente para concurrencia pesada local sin ahogar los descriptores de archivo del OS, previniendo cuellos de botella artificiales.
*   `limit_per_host = 10`: Puesto que todo viaja al mismo `BASE_URL` de localhost o del dominio de EcoMarket, un límite inferior evita spam abusivo a un único dominio, respetando `Rate Limits` del balanceador.
*   `keepalive_timeout = 30`: 30 segundos es prudente. Si el usuario navega a otra pantalla en 15 segundos, la conexión TCP se reutilizará ahorrando los milisegundos del `TCP Handshake` y el `TLS Handshake`. Tras 30 segundos de inactividad, se cierran para liberar RAM del cliente.
