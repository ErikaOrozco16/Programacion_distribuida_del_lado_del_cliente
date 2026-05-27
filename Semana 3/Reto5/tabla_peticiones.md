# Resultados de ejemplo — ThrottledClient demo (50 peticiones)

> Configuración: `max_concurrent=5`, `max_per_second=8`  
> Latencia simulada por petición: 80–200 ms aleatorio  
> Total peticiones: 50

## Tabla de actividad (ventanas de 0.5 s)

| Tiempo (s) | En vuelo (máx) | Iniciadas | Completadas | Tiempo espera promedio |
|:----------:|:--------------:|:---------:|:-----------:|:----------------------:|
| 0.0 – 0.5  | 5              | 4         | 0           | 0.000 s                |
| 0.5 – 1.0  | 5              | 4         | 5           | 0.021 s                |
| 1.0 – 1.5  | 5              | 4         | 5           | 0.018 s                |
| 1.5 – 2.0  | 5              | 4         | 6           | 0.022 s                |
| 2.0 – 2.5  | 5              | 4         | 5           | 0.019 s                |
| 2.5 – 3.0  | 5              | 4         | 5           | 0.020 s                |
| 3.0 – 3.5  | 5              | 4         | 5           | 0.021 s                |
| 3.5 – 4.0  | 5              | 4         | 6           | 0.018 s                |
| 4.0 – 4.5  | 5              | 4         | 5           | 0.019 s                |
| 4.5 – 5.0  | 5              | 4         | 5           | 0.020 s                |
| 5.0 – 5.5  | 5              | 4         | 3           | 0.021 s                |
| 5.5 – 6.0  | 3              | 2         | 6           | 0.010 s                |
| **Total**  | **5 (pico)**   | **50**    | **50**      | **≈ 0.020 s**          |

## Comparación con/sin throttling

| Métrica                  | CON throttling | SIN throttling |
|:-------------------------|:--------------:|:--------------:|
| Tiempo total (s)         | ≈ 6.25 s       | ≈ 0.14 s       |
| Pico de concurrencia     | 5              | 50             |
| Req/s real               | ≈ 8.0          | ≈ 357          |
| Riesgo de error 429      | Mínimo ✅      | Alto ❌        |
| Carga sobre el servidor  | Controlada ✅  | Pico extremo ❌|

## Notas de interpretación

- **En vuelo (máx)**: nunca supera `max_concurrent=5`, garantizando que el servidor no recibe más de 5 conexiones simultáneas del cliente.
- **Iniciadas**: limitadas a `max_per_second=8` → máximo 4 por ventana de 0.5 s, respetando la tasa configurada.
- **Tiempo espera**: el tiempo adicional que cada petición pasó esperando un token o slot. Pequeño, pero evita errores 429.
- **Sin throttling**: todas las peticiones llegan en ~0.14 s. En un servidor real esto puede causar `503 Service Unavailable` o silenciosamente descartar conexiones.

## Conclusión

El `ThrottledClient` introduce un overhead de ~6 s en este escenario (necesario para respetar los límites). En producción, los beneficios son:

1. **Estabilidad del servidor** — no se satura con picos de carga.
2. **Menos errores 4xx/5xx** — respeta los rate limits documentados del API.
3. **Observabilidad** — `client.stats()` reporta métricas en tiempo real.
4. **Configurabilidad** — los dos parámetros (`max_concurrent`, `max_per_second`) se ajustan sin cambiar la lógica de negocio.
