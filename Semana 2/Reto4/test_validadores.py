# test_validadores.py

import pytest
from validadores import validar_producto, validar_lista_productos, ValidationError


def test_falta_campo_requerido():
    data = {"nombre": "Manzana", "precio": 10}
    
    with pytest.raises(ValidationError) as e:
        validar_producto(data)
    
    assert "id" in str(e.value)


def test_id_no_es_entero():
    data = {"id": "1", "nombre": "Manzana", "precio": 10, "categoria": "frutas"}
    
    with pytest.raises(ValidationError) as e:
        validar_producto(data)
    
    assert "id" in str(e.value)


def test_precio_negativo():
    data = {"id": 1, "nombre": "Manzana", "precio": -5, "categoria": "frutas"}
    
    with pytest.raises(ValidationError) as e:
        validar_producto(data)
    
    assert "precio" in str(e.value)


def test_categoria_invalida():
    data = {"id": 1, "nombre": "Manzana", "precio": 10, "categoria": "electronica"}
    
    with pytest.raises(ValidationError) as e:
        validar_producto(data)
    
    assert "Categoría inválida" in str(e.value)


def test_productor_invalido():
    data = {
        "id": 1,
        "nombre": "Manzana",
        "precio": 10,
        "categoria": "frutas",
        "productor": {"id": "abc", "nombre": 123}
    }
    
    with pytest.raises(ValidationError) as e:
        validar_producto(data)
    
    assert "productor.id" in str(e.value)


#----------------------------------------------------
# EXTRA (muy recomendado)
#----------------------------------------------------

def test_lista_no_es_lista():
    with pytest.raises(ValidationError):
        validar_lista_productos("no es lista")


def test_lista_con_producto_invalido():
    data = [
        {"id": 1, "nombre": "Manzana", "precio": 10, "categoria": "frutas"},
        {"id": 2, "nombre": "Pera", "precio": -1, "categoria": "frutas"}  # inválido
    ]
    
    with pytest.raises(ValidationError) as e:
        validar_lista_productos(data)
    
    assert "posición 1" in str(e.value)