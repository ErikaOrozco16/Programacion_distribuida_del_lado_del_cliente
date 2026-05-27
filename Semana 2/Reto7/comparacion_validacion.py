# -*- coding: utf-8 -*-
"""
Módulo de Comparación de Estrategias de Validación de Datos
Proyecto: EcoMarket
Contiene las 3 implementaciones (Manual, Pydantic v2, JSON Schema) y el script de Benchmark.
"""

import timeit
import json
from typing import List, Optional

# =====================================================================
# 1. ESTRATEGIA: VALIDACIÓN MANUAL (if/else)
# =====================================================================
def validar_producto_manual(data: dict) -> dict:
    """
    Valida la estructura de un producto manualmente mediante condicionales nativos.
    Lanza ValueError si el esquema o los tipos de datos no son válidos.
    """
    errores = []
    
    # Validaciones de nivel superior (Presencia y Tipo)
    if "id" not in data or not isinstance(data["id"], int):
        errores.append("'id' es requerido y debe ser un número entero.")
        
    if "nombre" not in data or not isinstance(data["nombre"], str):
        errores.append("'nombre' es requerido y debe ser una cadena de texto.")
    elif len(data["nombre"]) < 2 or len(data["nombre"]) > 100:
        errores.append("'nombre' debe tener entre 2 y 100 caracteres.")
        
    if "precio" not in data or not isinstance(data["precio"], (int, float)):
        errores.append("'precio' es requerido y debe ser un número decimal/entero.")
    elif data["precio"] <= 0:
        errores.append("'precio' debe ser un valor estrictamente numérico positivo mayor a 0.")
        
    # Validaciones de campos opcionales y listas
    if "etiquetas" in data:
        if not isinstance(data["etiquetas"], list):
            errores.append("'etiquetas' debe ser una lista.")
        elif not all(isinstance(x, str) for x in data["etiquetas"]):
            errores.append("Todas las 'etiquetas' dentro de la lista deben ser cadenas de texto.")
            
    # Validaciones de objetos anidados
    if "detalles" in data and data["detalles"] is not None:
        detalles = data["detalles"]
        if not isinstance(detalles, dict):
            errores.append("'detalles' debe ser un diccionario/objeto anidado.")
        else:
            if "peso_kg" not in detalles or not isinstance(detalles["peso_kg"], (int, float)):
                errores.append("'detalles.peso_kg' es requerido dentro de detalles y debe ser numérico.")
            elif detalles["peso_kg"] <= 0:
                errores.append("'detalles.peso_kg' debe ser mayor a 0.")
                
    if errores:
        raise ValueError(f"Errores detectados de forma manual: {errores}")
    
    return data


# =====================================================================
# 2. ESTRATEGIA: PYDANTIC V2
# =====================================================================
try:
    from pydantic import BaseModel, Field, ValidationError
    
    class DetallesModel(BaseModel):
        peso_kg: float = Field(..., gt=0, description="Peso del producto en kilogramos")
        dimensiones: Optional[str] = Field(None, description="Dimensiones físicas del producto")

    class ProductoModel(BaseModel):
        id: int
        nombre: str = Field(..., min_length=2, max_length=100)
        precio: float = Field(..., gt=0)
        etiquetas: List[str] = Field(default_factory=list)
        detalles: Optional[DetallesModel] = None

    def validar_producto_pydantic(data: dict):
        # Valida e hidrata el modelo
        return ProductoModel(**data)
        
except ImportError:
    ProductoModel = None
    print("[AVISO] La librería 'pydantic' v2 no está instalada en este entorno.")
    print("        Por favor instala la dependencia con: pip install pydantic")


# =====================================================================
# 3. ESTRATEGIA: JSON SCHEMA (jsonschema)
# =====================================================================
try:
    from jsonschema import Draft7Validator
    
    schema_producto = {
        "type": "object",
        "properties": {
            "id": {"type": "integer"},
            "nombre": {"type": "string", "minLength": 2, "maxLength": 100},
            "precio": {"type": "number", "exclusiveMinimum": 0},
            "etiquetas": {
                "type": "array",
                "items": {"type": "string"}
            },
            "detalles": {
                "type": ["object", "null"],
                "properties": {
                    "peso_kg": {"type": "number", "exclusiveMinimum": 0},
                    "dimensiones": {"type": "string"}
                },
                "required": ["peso_kg"]
            }
        },
        "required": ["id", "nombre", "precio"]
    }
    
    # Pre-compilar el validador para optimizar el rendimiento en producción
    validador_json = Draft7Validator(schema_producto)
    
    def validar_producto_jsonschema(data: dict) -> dict:
        errores = list(validador_json.iter_errors(data))
        if errores:
            raise ValueError([e.message for e in errores])
        return data

except ImportError:
    validador_json = None
    print("[AVISO] La librería 'jsonschema' no está instalada en este entorno.")
    print("        Por favor instala la dependencia con: pip install jsonschema")


# =====================================================================
# SCRIPT DE BENCHMARK / MEDICIÓN DE RENDIMIENTO
# =====================================================================
if __name__ == "__main__":
    print("-" * 70)
    print(" BENCHMARK DE VALIDACIÓN DE DATOS (EcoMarket) ")
    print("-" * 70)
    
    # Definición de payloads de prueba
    payload_valido = {
        "id": 1052,
        "nombre": "Café Orgánico de Comercio Justo",
        "precio": 18.50,
        "etiquetas": ["eco", "organico", "desayuno"],
        "detalles": {
            "peso_kg": 0.5,
            "dimensiones": "12x8x20 cm"
        }
    }
    
    payload_invalido = {
        "id": "ID_NO_VALIDO_STRING",  # Error de tipo (debe ser int)
        "nombre": "X",                  # Error de longitud (mínimo 2)
        "precio": -4.50,               # Error de valor (debe ser > 0)
        "etiquetas": "no-es-una-lista", # Error de estructura
        "detalles": {
            "peso_kg": -1.2             # Error de valor interno
        }
    }
    
    # Generamos un lote simulado de 1,000 respuestas de API
    # 90% válidos y 10% inválidos para emular un escenario realista de errores
    lote_productos = [payload_valido if i % 10 != 0 else payload_invalido for i in range(1000)]
    
    # Envoltorios tolerantes a excepciones para medir el flujo completo de la aplicación
    def test_manual():
        for prod in lote_productos:
            try:
                validar_producto_manual(prod)
            except ValueError:
                pass

    def test_pydantic():
        if ProductoModel is None:
            return
        for prod in lote_productos:
            try:
                ProductoModel(**prod)
            except Exception:
                pass

    def test_jsonschema():
        if validador_json is None:
            return
        for prod in lote_productos:
            try:
                validar_producto_jsonschema(prod)
            except ValueError:
                pass

    # Configuración de repeticiones (100 ejecuciones del lote de 1,000 = 100,000 iteraciones)
    numero_corridas = 100
    total_validaciones = numero_corridas * len(lote_productos)
    print(f"Procesando: {numero_corridas} repeticiones de un lote de 1,000 productos.")
    print(f"Total de validaciones ejecutadas: {total_validaciones:,}\\n")

    # Ejecución de tiempos
    tiempo_manual = timeit.timeit(test_manual, number=numero_corridas)
    print(f"1. Estrategia Manual     : {tiempo_manual:.5f} segundos")
    
    if ProductoModel is not None:
        tiempo_pydantic = timeit.timeit(test_pydantic, number=numero_corridas)
        ratio_pydantic = tiempo_pydantic / tiempo_manual
        print(f"2. Estrategia Pydantic v2: {tiempo_pydantic:.5f} segundos ({ratio_pydantic:.2f}x respecto a Manual)")
    else:
        print("2. Estrategia Pydantic v2: No ejecutada (Librería faltante)")
        
    if validador_json is not None:
        tiempo_jsonschema = timeit.timeit(test_jsonschema, number=numero_corridas)
        ratio_json = tiempo_jsonschema / tiempo_manual
        print(f"3. Estrategia JSON Schema: {tiempo_jsonschema:.5f} segundos ({ratio_json:.2f}x respecto a Manual)")
    else:
        print("3. Estrategia JSON Schema: No ejecutada (Librería faltante)")
        
    print("-" * 70)
