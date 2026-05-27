# Reto IA 8 - ClienteRobusto con multiples Circuit Breakers

```text
ClienteRobusto
  breakers:
    inventario -> CircuitBreaker(umbral=3, timeout=30)
    precios    -> CircuitBreaker(umbral=4, timeout=20)
    pedidos    -> CircuitBreaker(umbral=2, timeout=60)
    auth       -> CircuitBreaker(umbral=5, timeout=15)

request(endpoint):
  breaker = resolver_breaker(endpoint)
  token = token_manager.obtener_access_token()
  return breaker.ejecutar(http_request(endpoint, token))
```

Las peticiones de autenticacion tienen breaker propio. Un problema de inventario
no debe impedir renovar token, y un problema temporal de auth no debe bloquear
consultas publicas o cacheadas.

Cuando `/api/inventario` esta abierto, el cliente puede entregar el ultimo dato
del stream SSE como fallback solo si lo marca como `no_actualizado`. No se usa
fallback para pedidos, pagos ni operaciones irreversibles.
