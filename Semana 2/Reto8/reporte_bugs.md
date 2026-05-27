# Reto IA 8 - Reporte de bugs y correcciones

## Pruebas entregadas

La suite `test_cliente.py` contiene 21 pruebas automatizadas. Cubre camino feliz, errores 4xx/5xx, validacion de respuestas, validacion de entradas, filtros, autenticacion y diferencias entre `PUT`, `PATCH` y `DELETE`.

## Bugs encontrados y corregidos

| Bug | Riesgo | Correccion aplicada |
| --- | --- | --- |
| El cliente podia aceptar una respuesta exitosa que no fuera JSON | Fallo tardio o datos corruptos en la interfaz | Se valida `content_type` antes de usar el body |
| `POST`, `PUT`, `PATCH` y `DELETE` podian ejecutarse sin token | Operaciones protegidas sin autorizacion | Se lanza `UnauthorizedError` antes de enviar la peticion |
| `PATCH` aceptaba cuerpo vacio | Peticion ambigua que no cambia nada | Se rechaza payload vacio |
| IDs negativos eran enviados a la URL | Rutas invalidas y errores confusos | Se valida que el id sea entero no negativo |
| La lista de productos no validaba cada elemento | Datos parciales podian llegar a la aplicacion | Se valida cada producto antes de devolverlo |

## Resultado

El cliente queda cubierto por pruebas unitarias sin depender de un servidor real, usando un transporte falso que registra metodo, URL, headers y body.
