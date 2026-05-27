# Reto IA 5 - Documento de decisiones de diseno

## 1. Almacenamiento de tokens

Esta entrega usa la ruta Python, por coherencia con el cliente SSE de Semana 7. El `access_token` y el `refresh_token` se guardan en memoria del proceso durante la ejecucion. Para una app de terminal de laboratorio es suficiente porque al terminar el proceso los tokens desaparecen, reduciendo persistencia accidental en disco.

En un cliente real de escritorio no guardaria el `refresh_token` en texto plano. Usaria el keychain del sistema operativo o un archivo cifrado con permisos restrictivos para el usuario propietario. El escenario de fallo que se evita es que otro usuario o proceso lea un archivo con refresh token y mantenga acceso durante dias.

## 2. Margen de refresh proactivo

El margen elegido es de 300 segundos. Un token de 15 minutos no debe renovarse justo al ultimo segundo, porque puede existir diferencia de reloj entre cliente y servidor o latencia de red. Cinco minutos dan espacio para renovar sin que la experiencia del usuario caiga en 401 frecuentes.

No elegi 60 segundos porque un reloj del cliente atrasado por dos minutos seguiria enviando tokens que el servidor ya puede rechazar. Tampoco elegi 10 minutos porque renovaria cuando el token todavia tiene dos tercios de vida, aumentando carga innecesaria en el servidor.

## 3. Refresh singleton

El mecanismo usado es `threading.Condition` con la bandera `_is_refreshing`. Si una llamada ya esta renovando el token, las demas esperan el resultado y reutilizan el mismo `access_token` nuevo. Esto evita el problema de cinco peticiones simultaneas disparando cinco refresh contra el servidor.

Este lock protege concurrencia dentro del mismo proceso. Si la aplicacion corriera con varios procesos, cada proceso tendria su propio lock y podria haber refresh duplicado. Para un caso multiproceso se necesitaria coordinacion externa, por ejemplo un lock distribuido, una cola centralizada o mover el refresh a un servicio compartido.

## 4. Refresh fallido

Si `refresh_access_token()` falla porque el servidor devuelve 401 o no entrega `access_token`, el cliente ejecuta `logout()`. La razon es que un refresh fallido indica que la sesion ya no puede renovarse con confianza. Mantener el estado anterior podria dejar un cliente aparentemente autenticado pero incapaz de operar.

El interceptor tambien evita un bucle infinito: si el 401 ocurre en el endpoint de refresh, no intenta refrescar otra vez. Limpia el estado y deja que el usuario vuelva a autenticarse.

## 5. Lectura del payload JWT

El cliente decodifica el payload para calcular `exp`, pero no verifica la firma. Esto es intencional: la firma es una validacion de seguridad que corresponde al servidor, que tiene la clave y autoridad para aceptar o rechazar el token. El cliente solo usa `exp` para mejorar la experiencia, anticipando renovaciones.
