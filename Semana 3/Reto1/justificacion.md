# Justificación: ¿Por qué async/await para EcoMarket?

## Reto 1 · Semana 3 · Programación del lado del cliente

\---

## Justificación técnica

EcoMarket es una aplicación de catálogo de productos cuyo cliente necesita realizar
**múltiples peticiones HTTP concurrentes** hacia una API REST: consultar el listado de
productos, obtener las categorías disponibles, cargar el perfil del usuario autenticado
y procesar notificaciones, todo ello antes de renderizar la interfaz. Este patrón de
acceso es característico de las aplicaciones **I/O-bound** (limitadas por entrada/salida),
donde el tiempo de CPU es mínimo y la mayor parte del tiempo se espera la respuesta de
la red o el disco.

El modelo **async/await** con `asyncio` y `aiohttp` es la elección correcta para EcoMarket
por las siguientes razones:

**1. Eficiencia con un solo hilo.**  
A diferencia de `ThreadPoolExecutor`, que crea uno o más hilos del sistema operativo para
cada tarea concurrente, `asyncio` ejecuta toda la lógica concurrente en un **único hilo**.
El event loop de Python coordina cuándo cada corrutina puede avanzar, eliminando el overhead
de cambio de contexto entre hilos (*context switching*) y el riesgo de condiciones de carrera
(*race conditions*) sobre estado compartido.

**2. Escalabilidad real.**  
Con hilos, el límite práctico de concurrencia en Python es bajo (decenas de hilos) debido al
GIL (*Global Interpreter Lock*) y al costo de memoria. Con `asyncio`, un solo proceso puede
manejar **miles de conexiones abiertas simultáneamente**, lo que es esencial si el cliente
necesita escalar (por ejemplo, un backend que actúa como BFF —*Backend for Frontend*—
consultando múltiples microservicios a la vez).

**3. Legibilidad y mantenibilidad.**  
El código async/await se lee de forma casi secuencial (`await peticion()`), aunque en
realidad sea concurrente. Esto contrasta con los callbacks —donde la lógica queda
fragmentada en funciones anidadas o en closures— y con los Futures explícitos, que
requieren bucles de control adicionales. La legibilidad es crítica en un proyecto educativo
y en equipos de desarrollo que deben mantener el código a largo plazo.

**4. Manejo de errores limpio.**  
`asyncio.gather(return\_exceptions=True)` permite que una petición fallida (por ejemplo,
un timeout en `/api/categorias`) **no cancele** las demás corrutinas en vuelo. Los errores
se reciben como valores normales en la lista de resultados y se procesan con `isinstance(r, Exception)`,
manteniendo la estructura de control lineal y evitando la complejidad de los callbacks de error.

**5. Ecosistema maduro.**  
`aiohttp` ofrece un cliente HTTP asíncrono completo, con soporte de sesiones reutilizables
(`aiohttp.ClientSession`), control de timeouts a nivel de conexión y lectura, y reintentos
configurables. Bibliotecas como `aiomysql`, `asyncpg` o `motor` (MongoDB) siguen el mismo
patrón, lo que permite construir un stack completamente no bloqueante de extremo a extremo.

\---

## Conclusión

Para EcoMarket, **async/await** no es solo una preferencia de estilo: es la herramienta
correcta para el trabajo. Reduce la latencia percibida por el usuario al cargar datos de
múltiples endpoints en paralelo, mantiene el código legible y mantenible, y abre la puerta
a escalar el cliente a miles de conexiones simultáneas sin necesidad de gestionar pools
de hilos o procesos. Los modelos de callbacks y futures tienen su lugar (integración con
código bloqueante, tareas CPU-intensivas), pero para I/O de red concurrente, `asyncio`
es el estándar moderno en Python.

