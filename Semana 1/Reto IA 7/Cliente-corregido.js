
const BASE_URL = 'http://localhost:3000';

/**
 * FUNCIÓN CENTRALIZADA (Wrapper HTTP)
 */
async function apiFetch(endpoint, opciones = {}, timeout = 8000) { // se reajusto el timeout para que sea configurable
  const url = `${BASE_URL}${endpoint}`;

  const headersBase = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',      //Se re acomodo el header
    'X-Client-Version': '1.0'
  };

  const configuracion = {
    ...opciones,
    headers: {
      ...headersBase,
      ...opciones.headers
    },
    signal: AbortSignal.timeout(timeout) // llamada del timeout configurable
  };

  const respuesta = await fetch(url, configuracion);

  // Se hizo un reacomodo para manejo uniforme de errores HTTP
  if (!respuesta.ok) {
    const body = await respuesta.text(); // no asumimos JSON
    throw new Error(`API Error ${respuesta.status}: ${body}`);
  }

  return respuesta;
}

/**
 * 1. Listar productos
 */
async function listarProductos() {
  try {
    const res = await apiFetch('/productos');

    // Se hace la validación de Content-Type , para verificar que el contenido si este en json
    const contentType = res.headers.get('content-type');
    if (!contentType?.includes('application/json')) {
      throw new Error('Respuesta no es JSON');
    }

    const productos = await res.json();
    console.table(productos);
    return productos; 
  } catch (err) {
    console.error("Error al listar:", err.message);
    throw err; // mediante este cambio la propagación del error se hace de manera correcta
  }
}

/**
 * 2. Obtener por ID
 */
async function obtenerProductoPorId(id) {
  try {
    const res = await apiFetch(`/productos/${id}`);
    return await res.json();
  } catch (err) {
    if (err.message.includes('404')) {
      console.warn("Producto no encontrado.");
      return null;
    }
    throw err;
  }
}

/**
 * 3. Crear producto
 */
async function crearProducto(nuevoProducto) {
  
  if (!nuevoProducto || typeof nuevoProducto !== 'object') {
    throw new Error("Producto inválido");
  }

  try {
    const res = await apiFetch('/productos', {
      method: 'POST',
      body: JSON.stringify(nuevoProducto)
    });

    if (res.status === 201) {
      console.log("✨ Creado!");
    }

    return await res.json();
  } catch (err) {
    console.error("Error al crear:", err.message);
    throw err;
  }
}

// --- PRUEBAS ---
console.log("🚀 Iniciando pruebas de creación...");

// Prueba 1: Datos correctos
crearProducto({
  nombre: "Café Orgánico",
  precio: 15.0,
  id: 996,
  categoria: "bebidas",
 prodructor_id: 10
});

// Prueba 2: Simulemos un error (mandando el precio como texto en lugar de número)
crearProducto({
  nombre: "Error Test",
  precio: "caro" 
});

listarProductos();
obtenerProductoPorId(996);

