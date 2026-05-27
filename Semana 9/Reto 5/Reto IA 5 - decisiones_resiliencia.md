# Reto IA 5 - Decisiones de resiliencia

## Umbrales elegidos

El umbral de 3 fallos consecutivos evita abrir el circuito por un incidente
aislado, pero corta pronto una caida sostenida. Para EcoMarket es un buen punto
medio: el operador no queda esperando demasiadas solicitudes fallidas y el
servidor deja de recibir trafico cuando ya mostro una degradacion real.

El timeout de apertura de la demo es de 2 segundos para poder observar la
recuperacion rapido. En produccion se cambiaria a 30-60 segundos con jitter para
evitar que muchas estaciones de trabajo prueben la recuperacion al mismo tiempo.

## Limites del Circuit Breaker

No corrige credenciales invalidas, errores de negocio, datos mal formados ni
problemas de permisos. Tampoco reemplaza retries con backoff, cache, monitoreo o
alertas. Su trabajo es decidir si una llamada remota debe intentarse ahora.

## Respuestas lentas

Una respuesta lenta debe activar el breaker solo si rebasa el timeout definido
por el cliente y se convierte en `asyncio.TimeoutError`. Una respuesta lenta que
aun llega dentro del limite se registra como exito, aunque conviene observarla
con metricas de latencia.
