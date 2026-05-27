# Reto IA 7 - Diseno de integracion SSE + Auth

## Decision de mecanismo para abrir SSE

Para la ruta Python se usara header `Authorization: Bearer <access_token>` al abrir la conexion SSE, porque un cliente Python no tiene la limitacion de `EventSource` del navegador y puede enviar headers personalizados.

Para ruta Browser usaria cookie HttpOnly con `SameSite=Strict` cuando el servidor y el panel comparten origen. Si tecnicamente solo estuviera disponible `EventSource` y no hubiera cookie, `?token=...` seria una salida posible, pero con riesgo claro: el token queda en logs, historial y referers. Por eso no es la primera opcion.

## Politica ante expiracion

Se elige la opcion B: el servidor cierra la conexion o envia un evento especial cuando el token expira. Es mas estricta que dejar viva la conexion indefinidamente, porque obliga a revalidar la sesion. El cliente paga un poco mas de complejidad, pero mantiene el mismo modelo de seguridad que las peticiones HTTP normales.

## Flujo de reconexion autenticada

```text
iniciar_sse():
    si token_manager.is_expiring_soon():
        token_manager.refresh_access_token()

    headers = token_manager.get_auth_header()
    conexion = abrir_sse("/api/ecomarket/eventos", headers=headers)

    mientras conexion activa:
        evento = leer_evento()

        si evento.tipo == "auth_expired":
            cerrar conexion
            manejar_expiracion_auth()
            salir del ciclo

        si evento.tipo == "mensaje":
            routear evento en ClienteSSEMultiplex

        si ocurre error de red:
            manejar_error_red()
            salir del ciclo

manejar_expiracion_auth():
    intentar:
        token_manager.refresh_access_token()
        esperar backoff corto
        iniciar_sse()
    excepto refresh_fallido:
        token_manager.logout()
        notificar "Sesion expirada"

manejar_error_red():
    si token_manager.is_expiring_soon():
        intentar token_manager.refresh_access_token()
        si falla: logout y detener reconexion

    esperar backoff exponencial
    iniciar_sse()
```

## Como distinguir expiracion de error de red

El mejor diseno es que el servidor mande un evento final `auth_expired` antes de cerrar la conexion. Si no puede hacerlo, el cliente clasifica un cierre con 401 como expiracion y un cierre sin codigo HTTP claro como error de red. En ambos casos puede revisar `is_expiring_soon()` antes de reconectar, pero solo el caso de expiracion fuerza refresh inmediato.

## Integracion con ClienteSSEMultiplex de Semana 7

`ClienteSSEMultiplex` no deberia saber detalles del JWT. Solo recibe una funcion `obtener_headers_auth()` o una referencia a `TokenManager`. Antes de cada reconexion, pide headers nuevos. Si una reconexion ocurre despues de refresh, el header ya contiene el nuevo `access_token`.

```text
ClienteSSEMultiplex
    depende de TokenManager solo para:
        - get_auth_header()
        - is_expiring_soon()
        - refresh_access_token()

    no hace:
        - decodificar JWT por su cuenta
        - verificar firmas
        - almacenar refresh_token directamente
```
