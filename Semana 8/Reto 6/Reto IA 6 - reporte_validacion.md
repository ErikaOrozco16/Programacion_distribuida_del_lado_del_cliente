# Reto IA 6 - Reporte de validacion

| Caso | Resultado obtenido | Coincide |
|---|---|---|
| 1. Token bien formado, no expirado | `decode_payload()` devuelve `{"sub":"user_1","exp":9999999999,"iat":1714000}` e `is_expiring_soon()` devuelve `False`. | Si |
| 2. Token expirado | El payload se decodifica y `is_expiring_soon()` devuelve `True`. | Si |
| 3. Token con solo 2 partes | `decode_payload()` lanza `ValueError` controlado antes de acceder al payload. | Si |
| 4. Payload no JSON | `decode_payload()` lanza `ValueError` controlado por payload invalido. | Si |
| 5. Token sin `exp` | `is_expiring_soon()` devuelve `True`, tratandolo como expirado. | Si |
| 6. Cinco refresh simultaneos | Las 5 llamadas reciben el mismo access token y el contador marca 1 peticion real de refresh. | Si |

## Bug identificado y corregido

Bug inicial: al pensar la primera version de `is_expiring_soon()`, el token sin `exp` podia tratarse como "no expira pronto" si el codigo usaba un valor por defecto alto o ignoraba la ausencia del claim.

Causa raiz: se asumio que todo JWT util para el cliente siempre trae `exp`. Esa suposicion es insegura porque un token sin vencimiento no debe aceptarse como valido desde la perspectiva del cliente.

Fix aplicado: `is_expiring_soon()` ahora devuelve `True` cuando `exp` no existe o no es numerico. Asi el cliente fuerza refresh o logout en lugar de continuar con un token ambiguo.

## Verificacion del singleton

La validacion del Caso 6 usa cinco llamadas concurrentes con `ThreadPoolExecutor`. El mock de refresh tiene un contador protegido por lock. El resultado esperado y obtenido fue `refresh_call_count == 1`, demostrando que las llamadas simultaneas esperaron el mismo refresh.

## Evidencia ejecutable

Archivo: `Reto IA 6/validar_token_manager.py`.
