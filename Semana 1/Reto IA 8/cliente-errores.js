const BASE_URL = 'http://localhost:3000';

/**
 * 1. FUNCIÓN CENTRALIZADA 
 */
async function apiFetch(endpoint, opciones = {}, timeout = 8000, reintentos = 2) {
  const url = `${BASE_URL}${endpoint}`;

  const configuracion = {
    ...opciones,
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      'X-Client-Version': '1.0', // Conservamos tu header personalizado
      ...opciones.headers
    },
    signal: AbortSignal.timeout(timeout) 
  };

  try {
    const respuesta = await fetch(url, configuracion);

    if (!respuesta.ok) {
      // Si el servidor falla (5xx), reintentamos
      if (respuesta.status >= 500 && reintentos > 0) {
        console.warn(`⚠️ Error ${respuesta.status} en ${endpoint}. Reintentando... (${reintentos} restantes)`);
        await new Promise(res => setTimeout(res, 1000)); // Backoff de 1 segundo
        return apiFetch(endpoint, opciones, timeout, reintentos - 1);
      }
      
      // Si es otro error (ej. 400, 404), capturamos el texto sin romper el flujo
      const body = await respuesta.text().catch(() => "Cuerpo ilegible"); 
      throw new Error(`API Error ${respuesta.status}: ${body}`);
    }

    return respuesta;

  } catch (error) {
    // Manejo de Timeout
    if (error.name === 'TimeoutError' || error.name === 'AbortError') {
      if (reintentos > 0) {
        console.warn(`⏳ Timeout detectado en ${endpoint}. Reintentando...`);
        return apiFetch(endpoint, opciones, timeout, reintentos - 1);
      }
      throw new Error(`⏳ El servidor tardó demasiado (Límite: ${timeout}ms)`);
    }

    // Manejo de conexión caída a la mitad
    if (error.name === 'TypeError') {
      throw new Error('🔌 Error de red: La conexión se perdió abruptamente.');
    }

    throw error; // Propagamos otros errores
  }
}

/**
 * 2. HELPER: Parseo Seguro de JSON
 */
async function procesarRespuestaJSON(respuesta) {
  const contentType = respuesta.headers.get('content-type');
  if (!contentType || !contentType.includes('application/json')) {
    throw new Error('👽 Formato inesperado: La respuesta no es JSON válido.');
  }

  try {
    return await respuesta.json();
  } catch (error) {
    throw new Error('✂️ Respuesta truncada: El JSON llegó incompleto o corrupto.');
  }
}

/**
 * 3. MÉTODOS O FUNCIONES PARA LOS PRODUCTOS
 */

async function listarProductos() {
  try {
    const res = await apiFetch('/productos');
    // Usamos el helper en lugar de hacer res.json() manual
    const productos = await procesarRespuestaJSON(res); 
    console.table(productos);
    return productos; 
  } catch (err) {
    console.error("Error al listar:", err.message);
    throw err; 
  }
}

async function obtenerProductoPorId(id) {
  try {
    const res = await apiFetch(`/productos/${id}`);
    return await procesarRespuestaJSON(res);
  } catch (err) {
    // Conservamos tu lógica para ignorar el 404
    if (err.message.includes('404')) {
      console.warn(`Producto ${id} no encontrado.`);
      return null;
    }
    throw err;
  }
}

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
      console.log("✨ Creado exitosamente!");
    }

    return await procesarRespuestaJSON(res);
  } catch (err) {
    console.error("Error al crear:", err.message);
    throw err;
  }
}

// --- PRUEBAS ---
console.log("🚀 Iniciando pruebas de caos y creación...");

// Prueba 1: Datos correctos
crearProducto({
  nombre: "Café Orgánico",
  precio: 15.0,
  id: 996,
  categoria: "bebidas",
  productor_id: 10
}).catch(() => {}); // Atrapamos el error aquí si falla el mock

// Prueba 2: Simularemos un error (mandando el precio como texto)
crearProducto({
  nombre: "Error Test",
  precio: "caro" 
}).catch(() => {});

listarProductos().catch(() => {});
obtenerProductoPorId(996).catch(() => {});