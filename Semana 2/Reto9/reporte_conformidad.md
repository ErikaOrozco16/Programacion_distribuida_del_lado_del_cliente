# Reto IA 9 - Reporte de conformidad

## Resultado de auditoria

El script `auditar_contrato.py` compara el contrato `Reto1/openapi_ver2.yaml` contra el cliente corregido `cliente_corregido.py`.

Resultado esperado:

```json
{
  "checked_operations": 6,
  "findings": [],
  "conformity": "100%"
}
```

## Operaciones verificadas

| Funcion del cliente | Metodo y ruta del contrato | Estado esperado | Resultado |
| --- | --- | --- | --- |
| `listar_productos` | `GET /productos` | `200` | Conforme |
| `crear_producto` | `POST /productos` | `201` | Conforme |
| `obtener_producto` | `GET /productos/{id}` | `200` | Conforme |
| `actualizar_producto_total` | `PUT /productos/{id}` | `200` | Conforme |
| `actualizar_producto_parcial` | `PATCH /productos/{id}` | `200` | Conforme |
| `eliminar_producto` | `DELETE /productos/{id}` | `204` | Conforme |

## Correcciones aplicadas

- El cliente usa exactamente las rutas declaradas en OpenAPI.
- Las operaciones protegidas requieren token.
- Los estados de exito coinciden con el contrato.
- Los ids de path se validan y codifican antes de construir la URL.
