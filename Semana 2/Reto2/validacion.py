from datetime import datetime

CATEGORIAS_VALIDAS = {"frutas", "verduras", "lacteos", "miel", "conservas"}

def es_iso8601(fecha_str: str) -> bool:
    try:
        datetime.fromisoformat(fecha_str.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False

def validar_producto(data: dict) -> tuple[bool, list]:
    errores = []

    # ─── CAMPOS REQUERIDOS ─────────────────────────────
    campos_requeridos = {
        "id": int,
        "nombre": str,
        "precio": (int, float),
        "categoria": str,
        "productor": dict,
        "disponible": bool,
        "creado_en": str
    }

    for campo, tipo in campos_requeridos.items():
        if campo not in data:
            errores.append(f"Falta el campo requerido: {campo}")
        elif not isinstance(data[campo], tipo):
            errores.append(f"Tipo incorrecto en '{campo}': esperado {tipo}, recibido {type(data[campo])}")

    if errores:
        return False, errores

    # ------------ VALIDACIONES DE NEGOCIO -------------
    if data["precio"] <= 0:
        errores.append("El precio debe ser positivo")

    if data["categoria"] not in CATEGORIAS_VALIDAS:
        errores.append(f"Categoría inválida: {data['categoria']}")

    if not es_iso8601(data["creado_en"]):
        errores.append("Formato de fecha inválido (debe ser ISO 8601)")

    # ------------- VALIDACIÓN DE OBJETO ANIDADO --------------
    productor = data["productor"]

    if not isinstance(productor, dict):
        errores.append("El campo 'productor' debe ser un objeto")
    else:
        if "id" not in productor or not isinstance(productor["id"], int):
            errores.append("productor.id debe ser entero")

        if "nombre" not in productor or not isinstance(productor["nombre"], str):
            errores.append("productor.nombre debe ser string")

    # ------------- CAMPOS OPCIONALES (ejemplo) -----------------
    # Si existieran campos extra como el descuento , se puede validar aqui sin romper la función
    # Ejemplo:
    if "descuento" in data:
        if not isinstance(data["descuento"], (int, float)):
            errores.append("descuento debe ser numérico")
        elif not (0 <= data["descuento"] <= 100):
            errores.append("descuento debe estar entre 0 y 100")

    return len(errores) == 0, errores

#--------Ejemplos de pruebas-----------

if __name__ == "__main__":

    casos = [
        {
            "nombre": "Caso válido ✅",
            "data": {
                "id": 42,
                "nombre": "Miel orgánica",
                "precio": 150.0,
                "categoria": "miel",
                "productor": {"id": 7, "nombre": "Apiarios del Valle"},
                "disponible": True,
                "creado_en": "2024-01-15T10:30:00Z"
            }
        },
        {
            "nombre": "Precio como string ❌",
            "data": {
                "id": 42,
                "nombre": "Miel orgánica",
                "precio": "150",
                "categoria": "miel",
                "productor": {"id": 7, "nombre": "Apiarios del Valle"},
                "disponible": True,
                "creado_en": "2024-01-15T10:30:00Z"
            }
        },
        {
            "nombre": "Precio negativo ❌",
            "data": {
                "id": 42,
                "nombre": "Miel orgánica",
                "precio": -10,
                "categoria": "miel",
                "productor": {"id": 7, "nombre": "Apiarios del Valle"},
                "disponible": True,
                "creado_en": "2024-01-15T10:30:00Z"
            }
        },
        {
            "nombre": "Categoría inválida ❌",
            "data": {
                "id": 42,
                "nombre": "Miel orgánica",
                "precio": 150,
                "categoria": "electronica",
                "productor": {"id": 7, "nombre": "Apiarios del Valle"},
                "disponible": True,
                "creado_en": "2024-01-15T10:30:00Z"
            }
        },
        {
            "nombre": "Fecha inválida ❌",
            "data": {
                "id": 42,
                "nombre": "Miel orgánica",
                "precio": 150,
                "categoria": "miel",
                "productor": {"id": 7, "nombre": "Apiarios del Valle"},
                "disponible": True,
                "creado_en": "15-01-2024"
            }
        },

	 {
            "nombre": "❌ 5. Objeto anidado corrupto",
            "data": {
              "id": 42,
 	      "nombre": "Miel orgánica",
 	      "precio": 150,
 	      "categoria": "miel",
  	      "productor": "Apiarios del Valle",
  	      "disponible": True,
              "creado_en": "2024-01-15T10:30:00Z"
              }
          },

          {
            "nombre": "❌ caso propio, Id invalidad",
            "data": {
              "id": "Cuarenta y Dos",
 	      "nombre": "Miel orgánica",
 	      "precio": 150,
 	      "categoria": "miel",
  	      "productor": {"id": 7, "nombre": "Apiarios del Valle"},
  	      "disponible": True,
              "creado_en": "2024-01-15T10:30:00Z"
              }
          }
    ]

    for caso in casos:
        print(f"\n🔍 Probando: {caso['nombre']}")
        valido, errores = validar_producto(caso["data"])

        if valido:
            print("✅ VÁLIDO")
        else:
            print("❌ INVÁLIDO")
            for e in errores:
                print(f"   - {e}") 