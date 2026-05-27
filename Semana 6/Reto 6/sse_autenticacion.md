# Reto IA 6 - Autenticacion en clientes SSE

## Pregunta central

La API nativa `EventSource` del navegador **no permite enviar headers personalizados** como `Authorization: Bearer TOKEN`. Su constructor solo recibe la URL y una opcion limitada (`withCredentials`) para incluir cookies. Por eso, si un backend exige Bearer Token en header, `EventSource` nativo no puede cumplirlo directamente.

## Contexto A: cliente Python/Node.js con parseo manual

En Python o Node.js si se controla la peticion HTTP manualmente, el header se agrega al abrir la conexion:

```python
headers = {
    "Accept": "text/event-stream",
    "Authorization": f"Bearer {access_token}",
}
request = Request(url, headers=headers)
```

Si el servidor responde `401` al inicio, el cliente debe renovar token y abrir otra conexion. Si el token expira durante el stream, normalmente el servidor cierra la conexion; el cliente detecta el cierre o el `401`, renueva el token y reconecta enviando tambien `Last-Event-ID`.

## Contexto B: alternativas reales en navegador

| Alternativa | Pros desde el cliente | Contras desde el cliente |
| --- | --- | --- |
| `withCredentials: true` con cookies | Nativo, simple y compatible con cookies `HttpOnly` | Requiere backend con sesiones/cookies y CORS bien configurado; no sirve para Bearer header |
| Token en query param | Funciona con `EventSource` nativo | Expone el token en historial, logs, proxies y capturas; no recomendado |
| `@microsoft/fetch-event-source` | Usa `fetch`, permite `Authorization` y mantiene estilo SSE | Agrega dependencia y la reconexion queda en una libreria externa |
| Service Worker | Puede interceptar peticiones y modificar comportamiento | Mucha complejidad para un proyecto estudiantil; dificil de depurar |

Para un panel interno corporativo recomendaria `@microsoft/fetch-event-source` si la autenticacion ya esta basada en Bearer Token. Mantiene el token fuera de la URL y permite usar headers como en el resto de la API.

## Pseudocodigo de renovacion de token

```text
token = obtener_access_token()
ultimo_id = null

mientras cliente_activo:
    headers = {
        Accept: text/event-stream,
        Authorization: Bearer token
    }
    si ultimo_id existe:
        headers["Last-Event-ID"] = ultimo_id

    abrir conexion SSE con headers

    si respuesta inicial es 401:
        token = renovar_con_refresh_token()
        continuar

    por cada evento recibido:
        guardar ultimo_id
        procesar evento

    si el servidor cierra porque el token expiro:
        token = renovar_con_refresh_token()
        reconectar usando Last-Event-ID
```

## Limitacion fundamental

En polling, cada peticion es corta y puede salir con un token nuevo. En SSE y WebSocket, la autenticacion ocurre al abrir una conexion que puede durar mucho tiempo. Si el token vence mientras la conexion sigue abierta, el cliente no puede "cambiar el header" dentro de esa misma conexion: debe cerrar, renovar credenciales y reconectar sin perder posicion, normalmente con `Last-Event-ID`.
