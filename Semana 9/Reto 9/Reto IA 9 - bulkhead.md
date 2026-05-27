# Reto IA 9 - Bulkhead como complemento

El Bulkhead limita cuantos recursos simultaneos puede consumir un endpoint. Si
inventario tiene limite de 3 conexiones y llegan 5 solicitudes, 3 pueden intentar
pasar al Circuit Breaker y 2 quedan en espera o fallan rapido segun la politica
del cliente.

La interaccion recomendada es:

```text
ClienteRobusto
  -> Bulkhead por endpoint
      -> CircuitBreaker por endpoint
          -> llamada HTTP
```

El Bulkhead es especialmente util con polling frecuente porque muchas peticiones
pueden acumularse durante una degradacion. Con SSE tambien sirve, pero el riesgo
principal cambia: se vigilan reconexiones simultaneas, pings sin respuesta y
colas de eventos no consumidos.

Metricas externas utiles para EcoMarket: tasa de rechazos rapidos del cliente,
conexiones concurrentes por endpoint, latencia percibida, intentos de
reconexion, porcentaje de respuestas desde cache y picos sincronizados despues
de una recuperacion.
