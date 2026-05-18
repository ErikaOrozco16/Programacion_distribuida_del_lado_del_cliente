# validadores.py

from datetime import datetime

CATEGORIAS_VALIDAS = {"frutas", "verduras", "lacteos", "miel", "conservas"}


class ValidationError(Exception):
    pass


#------------------------------------------------
# UTILIDADES
#------------------------------------------------
def es_iso8601(fecha_str: str) -> bool:
    if not isinstance(fecha_str, str):
        return False
    try:
        datetime.fromisoformat(fecha_str.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


#---------------------------------------------------
# VALIDADOR PRINCIPAL
#---------------------------------------------------
def validar_producto(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValidationError("El producto debe ser un objeto tipo dict")

    #------- CAMPOS REQUERIDOS ----------------------
    requeridos = ["id", "nombre", "precio", "categoria"]
    for campo in requeridos:
        if campo not in data:
            raise ValidationError(f"Falta el campo requerido: '{campo}'")

    #------- TIPOS ------------------------------------
    if not isinstance(data["id"], int):
        raise ValidationError("El campo 'id' debe ser entero")

    if not isinstance(data["nombre"], str):
        raise ValidationError("El campo 'nombre' debe ser string")

    if not isinstance(data["precio"], (int, float)):
        raise ValidationError("El campo 'precio' debe ser numérico")

    if "disponible" in data and not isinstance(data["disponible"], bool):
        raise ValidationError("El campo 'disponible' debe ser boolean")

    #------ REGLAS DE NEGOCIO -------------------------
    if data["precio"] <= 0:
        raise ValidationError("El campo 'precio' debe ser mayor a 0")

    if data["categoria"] not in CATEGORIAS_VALIDAS:
        raise ValidationError(
            f"Categoría inválida: '{data['categoria']}'. Permitidas: {', '.join(CATEGORIAS_VALIDAS)}"
        )

    #------ OPCIONALES -------------------------------
    if "descripcion" in data and not isinstance(data["descripcion"], str):
        raise ValidationError("El campo 'descripcion' debe ser string")

    if "productor" in data:
        prod = data["productor"]
        if not isinstance(prod, dict):
            raise ValidationError("El campo 'productor' debe ser un objeto")

        if "id" not in prod or not isinstance(prod["id"], int):
            raise ValidationError("El campo 'productor.id' debe ser entero")

        if "nombre" not in prod or not isinstance(prod["nombre"], str):
            raise ValidationError("El campo 'productor.nombre' debe ser string")

    if "creado_en" in data and not es_iso8601(data["creado_en"]):
        raise ValidationError("El campo 'creado_en' debe estar en formato ISO 8601")

    return data


#---------------------------------------------------------------
# VALIDAR LISTA
#---------------------------------------------------------------
def validar_lista_productos(data: list) -> list:
    if not isinstance(data, list):
        raise ValidationError("Se esperaba una lista de productos")

    resultado = []
    for i, producto in enumerate(data):
        try:
            resultado.append(validar_producto(producto))
        except ValidationError as e:
            raise ValidationError(f"Error en producto en posición {i}: {str(e)}")

    return resultado
