"""
validadores.py — Módulo de validación para el cliente EcoMarket
================================================================
Contiene funciones puras de validación para los datos de productos
que se envían y reciben a través de la API REST de EcoMarket.

Uso:
    from validadores import validar_producto, validar_creacion_producto

Semana 3 — Programación del lado del cliente
"""

from typing import Any


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

CAMPOS_PRODUCTO = {"id", "nombre", "descripcion", "precio", "categoria", "stock"}
CATEGORIAS_VALIDAS = {
    "electronica",
    "ropa",
    "alimentos",
    "hogar",
    "deportes",
    "libros",
    "juguetes",
    "otros",
}


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _es_str_no_vacio(valor: Any) -> bool:
    """Retorna True si *valor* es una cadena no vacía (sin espacios)."""
    return isinstance(valor, str) and bool(valor.strip())


def _es_numero_positivo(valor: Any) -> bool:
    """Retorna True si *valor* es int o float y estrictamente mayor que 0."""
    return isinstance(valor, (int, float)) and not isinstance(valor, bool) and valor > 0


def _es_entero_no_negativo(valor: Any) -> bool:
    """Retorna True si *valor* es un int (no bool) y >= 0."""
    return isinstance(valor, int) and not isinstance(valor, bool) and valor >= 0


# ---------------------------------------------------------------------------
# Función 1: validar_producto
# ---------------------------------------------------------------------------

def validar_producto(datos: dict) -> dict:
    """
    Valida y normaliza un diccionario que representa un producto completo
    tal como viene de la API (incluyendo campos opcionales).

    Campos obligatorios
    -------------------
    - nombre   : str, no vacío
    - precio   : float o int, estrictamente > 0
    - categoria: str, no vacía

    Campos opcionales
    -----------------
    - id          : cualquier valor (generado por el servidor)
    - descripcion : str (puede estar vacío)
    - stock       : int, >= 0  (default 0 si ausente)

    Retorna
    -------
    dict
        Diccionario validado y normalizado.

    Lanza
    -----
    TypeError
        Si *datos* no es un dict.
    ValueError
        Si algún campo obligatorio falta o tiene un valor inválido.
    """
    if not isinstance(datos, dict):
        raise TypeError(
            f"Se esperaba un dict para el producto, se recibió {type(datos).__name__}"
        )

    errores: list[str] = []

    # — nombre —
    nombre = datos.get("nombre")
    if nombre is None:
        errores.append("El campo 'nombre' es obligatorio.")
    elif not _es_str_no_vacio(nombre):
        errores.append(
            f"El campo 'nombre' debe ser una cadena no vacía. Se recibió: {nombre!r}"
        )

    # — precio —
    precio = datos.get("precio")
    if precio is None:
        errores.append("El campo 'precio' es obligatorio.")
    elif not _es_numero_positivo(precio):
        errores.append(
            f"El campo 'precio' debe ser un número mayor que 0. Se recibió: {precio!r}"
        )

    # — categoria —
    categoria = datos.get("categoria")
    if categoria is None:
        errores.append("El campo 'categoria' es obligatorio.")
    elif not _es_str_no_vacio(categoria):
        errores.append(
            f"El campo 'categoria' debe ser una cadena no vacía. Se recibió: {categoria!r}"
        )

    # — stock (opcional, default 0) —
    stock = datos.get("stock", 0)
    if not _es_entero_no_negativo(stock):
        errores.append(
            f"El campo 'stock' debe ser un entero >= 0. Se recibió: {stock!r}"
        )

    if errores:
        raise ValueError("Datos de producto inválidos:\n  " + "\n  ".join(errores))

    # Construir y retornar el dict normalizado
    validado: dict = {
        "nombre": str(nombre).strip(),
        "precio": float(precio),
        "categoria": str(categoria).strip().lower(),
        "stock": int(stock),
    }

    # Preservar campos opcionales si existen
    if "id" in datos:
        validado["id"] = datos["id"]
    if "descripcion" in datos:
        validado["descripcion"] = str(datos["descripcion"]).strip()

    return validado


# ---------------------------------------------------------------------------
# Función 2: validar_lista_productos
# ---------------------------------------------------------------------------

def validar_lista_productos(datos: Any) -> list:
    """
    Valida que *datos* sea una lista y que cada elemento sea un producto válido.

    Retorna
    -------
    list[dict]
        Lista de productos validados y normalizados.

    Lanza
    -----
    TypeError
        Si *datos* no es una lista.
    ValueError
        Si algún elemento de la lista es un producto inválido.
    """
    if not isinstance(datos, list):
        raise TypeError(
            f"Se esperaba una lista de productos, se recibió {type(datos).__name__}"
        )

    productos_validados: list[dict] = []
    errores_acumulados: list[str] = []

    for indice, item in enumerate(datos):
        try:
            producto_ok = validar_producto(item)
            productos_validados.append(producto_ok)
        except (TypeError, ValueError) as exc:
            errores_acumulados.append(f"  [índice {indice}] {exc}")

    if errores_acumulados:
        raise ValueError(
            f"La lista contiene {len(errores_acumulados)} producto(s) inválido(s):\n"
            + "\n".join(errores_acumulados)
        )

    return productos_validados


# ---------------------------------------------------------------------------
# Función 3: validar_creacion_producto
# ---------------------------------------------------------------------------

def validar_creacion_producto(datos: dict) -> dict:
    """
    Valida el cuerpo de una solicitud POST /api/productos.

    Reglas específicas para creación
    ---------------------------------
    - nombre   : obligatorio, str no vacío
    - precio   : obligatorio, > 0
    - categoria: obligatorio, str no vacía
    - stock    : opcional, int >= 0 (default 0)
    - descripcion: opcional, str

    No se permiten campos desconocidos para evitar inyecciones.

    Retorna
    -------
    dict
        Payload limpio y listo para enviarse al servidor.

    Lanza
    -----
    TypeError / ValueError según corresponda.
    """
    if not isinstance(datos, dict):
        raise TypeError(
            f"El cuerpo de creación debe ser un dict, se recibió {type(datos).__name__}"
        )

    # Detectar campos desconocidos
    campos_conocidos = {"nombre", "precio", "categoria", "stock", "descripcion"}
    desconocidos = set(datos.keys()) - campos_conocidos
    if desconocidos:
        raise ValueError(
            f"Campos no permitidos en la creación: {desconocidos}. "
            f"Campos aceptados: {campos_conocidos}"
        )

    errores: list[str] = []

    # — nombre —
    nombre = datos.get("nombre")
    if nombre is None:
        errores.append("'nombre' es requerido para crear un producto.")
    elif not _es_str_no_vacio(nombre):
        errores.append(f"'nombre' debe ser texto no vacío. Recibido: {nombre!r}")

    # — precio —
    precio = datos.get("precio")
    if precio is None:
        errores.append("'precio' es requerido para crear un producto.")
    elif not _es_numero_positivo(precio):
        errores.append(f"'precio' debe ser mayor que 0. Recibido: {precio!r}")

    # — categoria —
    categoria = datos.get("categoria")
    if categoria is None:
        errores.append("'categoria' es requerida para crear un producto.")
    elif not _es_str_no_vacio(categoria):
        errores.append(f"'categoria' debe ser texto no vacío. Recibido: {categoria!r}")

    # — stock —
    stock = datos.get("stock", 0)
    if not _es_entero_no_negativo(stock):
        errores.append(f"'stock' debe ser entero >= 0. Recibido: {stock!r}")

    # — descripcion —
    descripcion = datos.get("descripcion", "")
    if not isinstance(descripcion, str):
        errores.append(f"'descripcion' debe ser texto. Recibido: {descripcion!r}")

    if errores:
        raise ValueError(
            "Error de validación en la creación del producto:\n  "
            + "\n  ".join(errores)
        )

    payload: dict = {
        "nombre": str(nombre).strip(),
        "precio": float(precio),
        "categoria": str(categoria).strip().lower(),
        "stock": int(stock),
        "descripcion": str(descripcion).strip(),
    }

    return payload


# ---------------------------------------------------------------------------
# Función 4: validar_actualizacion_parcial
# ---------------------------------------------------------------------------

def validar_actualizacion_parcial(campos: dict) -> dict:
    """
    Valida el cuerpo de una solicitud PATCH /api/productos/{id}.

    Reglas
    ------
    - Al menos un campo debe estar presente.
    - Solo se aceptan campos conocidos del modelo de producto.
    - Cada campo presente debe tener un valor válido según su tipo.

    Retorna
    -------
    dict
        Dict con solo los campos que se van a actualizar, normalizados.

    Lanza
    -----
    TypeError / ValueError según corresponda.
    """
    if not isinstance(campos, dict):
        raise TypeError(
            f"El cuerpo de actualización parcial debe ser un dict, "
            f"se recibió {type(campos).__name__}"
        )

    if not campos:
        raise ValueError(
            "La actualización parcial (PATCH) requiere al menos un campo. "
            "Se recibió un dict vacío."
        )

    campos_permitidos = {"nombre", "precio", "categoria", "stock", "descripcion"}
    desconocidos = set(campos.keys()) - campos_permitidos
    if desconocidos:
        raise ValueError(
            f"Campos no permitidos en la actualización parcial: {desconocidos}. "
            f"Campos válidos: {campos_permitidos}"
        )

    errores: list[str] = []
    resultado: dict = {}

    if "nombre" in campos:
        if not _es_str_no_vacio(campos["nombre"]):
            errores.append(f"'nombre' debe ser texto no vacío. Recibido: {campos['nombre']!r}")
        else:
            resultado["nombre"] = str(campos["nombre"]).strip()

    if "precio" in campos:
        if not _es_numero_positivo(campos["precio"]):
            errores.append(f"'precio' debe ser mayor que 0. Recibido: {campos['precio']!r}")
        else:
            resultado["precio"] = float(campos["precio"])

    if "categoria" in campos:
        if not _es_str_no_vacio(campos["categoria"]):
            errores.append(f"'categoria' debe ser texto no vacío. Recibido: {campos['categoria']!r}")
        else:
            resultado["categoria"] = str(campos["categoria"]).strip().lower()

    if "stock" in campos:
        if not _es_entero_no_negativo(campos["stock"]):
            errores.append(f"'stock' debe ser entero >= 0. Recibido: {campos['stock']!r}")
        else:
            resultado["stock"] = int(campos["stock"])

    if "descripcion" in campos:
        if not isinstance(campos["descripcion"], str):
            errores.append(f"'descripcion' debe ser texto. Recibido: {campos['descripcion']!r}")
        else:
            resultado["descripcion"] = str(campos["descripcion"]).strip()

    if errores:
        raise ValueError(
            "Error de validación en actualización parcial:\n  "
            + "\n  ".join(errores)
        )

    return resultado


# ---------------------------------------------------------------------------
# Demo / pruebas rápidas cuando se ejecuta directamente
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("  DEMO — Módulo validadores.py")
    print("=" * 60)

    # ── validar_producto ──────────────────────────────────────────
    print("\n[1] validar_producto — caso exitoso")
    p = validar_producto(
        {"id": 1, "nombre": "Laptop  ", "precio": 999.99,
         "categoria": "Electronica", "stock": 5}
    )
    print("  Resultado:", p)

    print("\n[2] validar_producto — caso con error")
    try:
        validar_producto({"nombre": "", "precio": -10, "categoria": "ropa"})
    except ValueError as e:
        print(" ", e)

    # ── validar_lista_productos ───────────────────────────────────
    print("\n[3] validar_lista_productos — caso exitoso")
    lista = validar_lista_productos([
        {"nombre": "Camisa", "precio": 25.0, "categoria": "ropa", "stock": 100},
        {"nombre": "Libro Python", "precio": 45.0, "categoria": "libros"},
    ])
    print(f"  Validados: {len(lista)} productos")

    # ── validar_creacion_producto ─────────────────────────────────
    print("\n[4] validar_creacion_producto — caso exitoso")
    payload = validar_creacion_producto(
        {"nombre": "Mouse inalámbrico", "precio": 35.5,
         "categoria": "electronica", "stock": 20}
    )
    print("  Payload:", payload)

    print("\n[5] validar_creacion_producto — campo desconocido")
    try:
        validar_creacion_producto({"nombre": "X", "precio": 10, "categoria": "ropa", "id": 99})
    except ValueError as e:
        print(" ", e)

    # ── validar_actualizacion_parcial ─────────────────────────────
    print("\n[6] validar_actualizacion_parcial — caso exitoso")
    patch = validar_actualizacion_parcial({"precio": 19.99, "stock": 50})
    print("  Patch:", patch)

    print("\n[7] validar_actualizacion_parcial — dict vacío")
    try:
        validar_actualizacion_parcial({})
    except ValueError as e:
        print(" ", e)

    print("\n" + "=" * 60)
    print("  Todas las validaciones ejecutadas correctamente.")
    print("=" * 60)
