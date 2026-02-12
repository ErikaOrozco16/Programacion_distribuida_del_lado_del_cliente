const BASE_URL = `http://127.0.0.1:4010`;

async function apiFetch(endpoint, opciones = {}) {
  const url = `${BASE_URL}${endpoint}`;

  const headersBase = {
    'Content-Type': 'application/json',
    'X-Client-Version': '1.1',         // Actualizamos versión
    'X-User-Name': 'Erika-Dev',       //  identificador personalizado
    'Authorization': 'Bearer mi-token-secreto-123'
  };

  const configuracion = {
    ...opciones,
    headers: {
      ...headersBase,
      ...opciones.headers
    },
    signal: AbortSignal.timeout(5000)
  };

  return await fetch(url, configuracion);
}
 /**
 * 1. Listar productos
 */
async function listarProductos() {
  try {
    const res = await apiFetch('/productos');
    const productos = await res.json();
    console.table(productos);
  } catch (err) {
    console.error("Error al listar:", err.message);
  }
}

/**
 * 2. Obtener por ID
 */
async function obtenerProductoPorId(id) {
  try {
    
    const res = await apiFetch(`/productos/${id}`);
    
    if (res.status === 404) {
      return console.warn("Producto no encontrado.");
    }

    const producto = await res.json();
    console.log("✅ Producto encontrado:", producto);
  } catch (err) {
    console.error("Error al buscar:", err.message);
  }
}

/**
 * 3. Crear producto (MEJORADO)
 */
async function crearProducto(nuevoProducto) {
  try {
    const res = await apiFetch('/productos', {
      method: 'POST',
      body: JSON.stringify(nuevoProducto)
    });

    const data = await res.json(); 

    if (res.status === 201) {
      console.log("✨ ¡Éxito! Producto creado:", data.nombre);
    } else if (res.status === 400) {
      // Prism te dirá qué campo está mal según tu openapi.yaml
      console.error("🚫 Error de validación:", data.detail || "Revisa los campos enviados");
    } else {
      console.error(`⚠️ Error inesperado: ${res.status}`);
    }
  } catch (err) {
    console.error("❌ Fallo crítico de red:", err.message);
  }
}

// --- NUEVA PRUEBA ---
console.log("🚀 Iniciando pruebas de creación...");

// Prueba 1: Datos correctos
crearProducto({
  nombre: "Café Orgánico",
  precio: 15.0,
  id: 996,
  categoria: "bebidas",
 prodructor_id: 10
});

// Prueba 2: Simulacion de un error (mandando el precio como texto en lugar de número)
crearProducto({
  nombre: "Error Test",
  precio: "caro" 
});
// Prueba 3: Mostrar productos guardados
listarProductos();
obtenerProductoPorId(996);
