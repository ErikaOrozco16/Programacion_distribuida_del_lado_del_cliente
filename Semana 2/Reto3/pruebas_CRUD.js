const BASE_URL = "http://127.0.0.1:4010";

const headers_autorizados = {
    "Content-Type": "application/json",
    "Authorization": "Bearer token-123"
};

// ─────────────────────────────────────────────
// EXCEPCIONES PERSONALIZADAS
// ─────────────────────────────────────────────
class ApiError extends Error {}
class NotFoundError extends Error {}
class ConflictError extends Error {}


// ─────────────────────────────────────────────
// CREAR PRODUCTO (POST)
// ─────────────────────────────────────────────
async function crear_producto(datos) {
    const response = await fetch(`${BASE_URL}/productos`, {
        method: "POST",
        headers: headers_autorizados, // ✅ FIX AQUÍ
        body: JSON.stringify(datos)
    });

    if (response.status === 201) {
        return await response.json();
    } else if (response.status === 409) {
        throw new ConflictError("El producto ya existe (conflicto).");
    } else if (response.status === 401) {
        throw new ApiError("No autorizado (401). Falta token.");
    } else {
        throw new ApiError(`Error al crear producto: ${response.status}`);
    }
}

// ─────────────────────────────────────────────
// OBTENER PRODUCTO (GET)
// ─────────────────────────────────────────────
async function obtener_producto(producto_id) {
    const response = await fetch(`${BASE_URL}/productos/${producto_id}`);

    if (response.status === 200) {
        return await response.json();
    } else if (response.status === 404) {
        throw new NotFoundError("Producto no encontrado.");
    } else {
        throw new ApiError(`Error al obtener producto: ${response.status}`);
    }
}

// ─────────────────────────────────────────────
// ACTUALIZAR PRODUCTO TOTAL (PUT)
// ─────────────────────────────────────────────
async function actualizar_producto_total(producto_id, datos) {

    const response = await fetch(`${BASE_URL}/productos/${producto_id}`, {
        method: "PUT",
        headers: headers_autorizados, // ✅ FIX
        body: JSON.stringify(datos)
    });

    if (response.status === 200) {
        return await response.json();
    } else if (response.status === 404) {
        throw new NotFoundError("Producto no encontrado.");
    } else if (response.status === 409) {
        throw new ConflictError("Conflicto al actualizar.");
    } else if (response.status === 401) {
        throw new ApiError("No autorizado (401).");
    } else {
        throw new ApiError(`Error en actualización total: ${response.status}`);
    }
}


// ─────────────────────────────────────────────
// ACTUALIZAR PRODUCTO PARCIAL (PATCH)
// ─────────────────────────────────────────────
async function actualizar_producto_parcial(producto_id, campos) {

    const response = await fetch(`${BASE_URL}/productos/${producto_id}`, {
        method: "PATCH",
        headers: headers_autorizados, // ✅ FIX
        body: JSON.stringify(campos)
    });

    if (response.status === 200) {
        return await response.json();
    } else if (response.status === 404) {
        throw new NotFoundError("Producto no encontrado.");
    } else if (response.status === 409) {
        throw new ConflictError("Conflicto al actualizar parcialmente.");
    } else if (response.status === 401) {
        throw new ApiError("No autorizado (401).");
    } else {
        throw new ApiError(`Error en actualización parcial: ${response.status}`);
    }
}


// ─────────────────────────────────────────────
// ELIMINAR PRODUCTO (DELETE)
// ─────────────────────────────────────────────
async function eliminar_producto(producto_id) {

    const response = await fetch(`${BASE_URL}/productos/${producto_id}`, {
        method: "DELETE",
        headers: headers_autorizados // ✅ FIX (también requiere auth)
    });

    if (response.status === 204) {
        return true;
    } else if (response.status === 404) {
        throw new NotFoundError("Producto no encontrado.");
    } else if (response.status === 401) {
        throw new ApiError("No autorizado (401).");
    } else {
        throw new ApiError(`Error al eliminar: ${response.status}`);
    }
}

// ─────────────────────────────────────────────
//                    Pruebas 
// ─────────────────────────────────────────────
(async () => {
    try {
        console.log("🟢 CREAR");
        const creado = await crear_producto({
            nombre: "Manzana orgánica",
            descripcion: "Muy fresca",
            precio: 25,
            categoria: "frutas",
            productor_id: 1
        });
        console.log(creado);

        console.log("🟡 OBTENER");
        const obtenido = await obtener_producto(0);
        console.log(obtenido);

        console.log("🔵 PUT (TOTAL)");
        const actualizado = await actualizar_producto_total(0, {
            nombre: "Manzana premium",
            descripcion: "Más fresca",
            precio: 30,
            categoria: "frutas",
            productor_id: 1
        });
        console.log(actualizado);

        console.log("🟣 PATCH (PARCIAL)");
        const parcial = await actualizar_producto_parcial(0, {
            precio: 35
        });
        console.log(parcial);

        console.log("🔴 DELETE");
        const eliminado = await eliminar_producto(0);
        console.log(eliminado);

    } catch (error) {
        console.error("❌ ERROR:", error);
    }
})();