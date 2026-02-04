const BASE_URL = 'https://127.0.0.1:4010';

/**
 * FUNCIÓN CENTRALIZADA (Wrapper)
 * Se encarga de la configuración común para todas las llamadas.
 */
async function apiFetch(endpoint, opciones = {}) {
  const url = ${BASE_URL}${endpoint};

  // Definimos los headers base
  const headersBase = {
    'Content-Type': 'application/json',
    'X-Client-Version': '1.0'
  };

  // Combinamos la configuración base con lo que nos pasen
  const configuracion = {
    ...opciones, // Copia el método, body, etc.
    headers: {
      ...headersBase,
      ...opciones.headers // Permite sobrescribir headers si fuera necesario
    },
    signal: AbortSignal.timeout(5000) // Timeout global de 5 segundos
  };

  const respuesta = await fetch(url, configuracion);

  // Si el servidor responde con error, lanzamos una excepción con el status
  if (!respuesta.ok && respuesta.status !== 404) {
    throw new Error(Error API: ${respuesta.status});
  }

  return respuesta;
}

---

### Funciones simplificadas

Mira qué limpio queda el código ahora:

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
    const res = await apiFetch(/productos/${id});
    
    if (res.status === 404) {
      return console.warn("Producto no encontrado.");
    }

    const producto = await res.json();
    console.log("Producto:", producto);
  } catch (err) {
    console.error("Error al buscar:", err.message);
  }
}

/**
 * 3. Crear producto
 */
async function crearProducto(nuevoProducto) {
  try {
    const res = await apiFetch('/productos', {
      method: 'POST',
      body: JSON.stringify(nuevoProducto)
    });

    if (res.status === 201) console.log("✨ Creado!");
  } catch (err) {
    console.error("Error al crear:", err.message);
  }
}