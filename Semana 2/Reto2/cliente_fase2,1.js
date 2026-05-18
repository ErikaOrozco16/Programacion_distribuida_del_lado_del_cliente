// ===================== LOGGER =====================

const LOG_LEVELS = {
  DEBUG: 10,
  INFO: 20,
  WARN: 30,
  ERROR: 40
};

const CURRENT_LEVEL = LOG_LEVELS.DEBUG;

function log(level, message, metadata = {}) {
  if (LOG_LEVELS[level] < CURRENT_LEVEL) return;

  console.log(JSON.stringify({
    timestamp: new Date().toISOString(),
    level,
    message,
    ...metadata
  }));
}

function sanitizeHeaders(headers = {}) {
  const clean = {};
  for (const [k, v] of Object.entries(headers || {})) {
    if (k.toLowerCase() === 'authorization') {
      clean[k] = v ? v.substring(0, 10) + '***' : undefined;
    } else {
      clean[k] = v;
    }
  }
  return clean;
}

// ===================== CONFIG =====================

const BASE_URL = 'http://localhost:3000';

// ===================== WRAPPER ORIGINAL (NO TOCADO) =====================

async function apiFetch(endpoint, opciones = {}, timeout = 8000) {
  const url = `${BASE_URL}${endpoint}`;

  const headersBase = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'X-Client-Version': '1.0'
  };

  const configuracion = {
    ...opciones,
    headers: {
      ...headersBase,
      ...opciones.headers
    },
    signal: AbortSignal.timeout(timeout)
  };

  const respuesta = await fetch(url, configuracion);

  if (!respuesta.ok) {
    const body = await respuesta.text();
    throw new Error(`API Error ${respuesta.status}: ${body}`);
  }

  return respuesta;
}

// ===================== NUEVO WRAPPER CON LOGGING =====================

async function apiFetchConLogging(endpoint, opciones = {}, timeout = 8000) {
  const start = Date.now();
  const method = opciones.method || 'GET';
  const url = `${BASE_URL}${endpoint}`;

  try {
    const response = await apiFetch(endpoint, opciones, timeout);

    const duration = Date.now() - start;

    const clone = response.clone();
    const text = await clone.text();
    const size = Buffer.byteLength(text);

    const metadata = {
      method,
      url,
      headers: sanitizeHeaders(opciones.headers),
      duration_ms: duration,
      status: response.status,
      response_size_bytes: size
    };

    if (duration > 2000) {
      log('WARN', 'Slow HTTP Request', metadata);
    } else {
      log('INFO', 'HTTP Request Success', metadata);
    }

    log('DEBUG', 'HTTP Detailed Trace', metadata);

    return response;

  } catch (error) {
    const duration = Date.now() - start;

    log('ERROR', 'HTTP Request Failed', {
      method,
      url,
      duration_ms: duration,
      error_message: error.message
    });

    throw error;
  }
}

// ===================== MÉTODOS DE NEGOCIO =====================

async function listarProductos() {
  try {
    const res = await apiFetchConLogging('/productos');

    const contentType = res.headers.get('content-type');
    if (!contentType?.includes('application/json')) {
      throw new Error('Respuesta no es JSON');
    }

    const productos = await res.json();
    console.table(productos);
    return productos;

  } catch (err) {
    console.error("Error al listar:", err.message);
    throw err;
  }
}

async function obtenerProductoPorId(id) {
  try {
    const res = await apiFetchConLogging(`/productos/${id}`);
    return await res.json();

  } catch (err) {
    if (err.message.includes('404')) {
      console.warn("Producto no encontrado.");
      return null;
    }
    throw err;
  }
}

async function crearProducto(nuevoProducto) {

  const [valido, errores] = validarProductoJS(nuevoProducto);

  if (!valido) {
    console.error("❌ Validación fallida:");
    errores.forEach(e => console.error(" -", e));
    return;
  }

  try {
    const res = await apiFetchConLogging('/productos', {
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
 
const CATEGORIAS_VALIDAS = ["frutas", "verduras", "lacteos", "miel", "bebidas", "conservas"];

function esISO8601(fecha) {
  return !isNaN(Date.parse(fecha));
}

function validarProductoJS(data) {
  const errores = [];

  const campos = {
    id: "number",
    nombre: "string",
    precio: "number",
    categoria: "string",
    productor: "object",
    disponible: "boolean",
    creado_en: "string"
  };

  for (const campo in campos) {
    if (!(campo in data)) {
      errores.push(`Falta el campo: ${campo}`);
    } else if (typeof data[campo] !== campos[campo]) {
      errores.push(`Tipo incorrecto en ${campo}`);
    }
  }

  if (errores.length) return [false, errores];

  // Reglas de negocio
  if (data.precio <= 0) {
    errores.push("El precio debe ser positivo");
  }

  if (!CATEGORIAS_VALIDAS.includes(data.categoria)) {
    errores.push("Categoría inválida");
  }

  if (!esISO8601(data.creado_en)) {
    errores.push("Fecha inválida");
  }

  // Objeto anidado
  if (typeof data.productor !== "object") {
    errores.push("productor debe ser objeto");
  } else {
    if (typeof data.productor.id !== "number") {
      errores.push("productor.id inválido");
    }
    if (typeof data.productor.nombre !== "string") {
      errores.push("productor.nombre inválido");
    }
  }

  return [errores.length === 0, errores];
}

// ===================== PRUEBAS =====================

console.log("🚀 Iniciando pruebas de creación...");

crearProducto({
  id: 996,
  nombre: "Café Orgánico",
  precio: 15.0,
  categoria: "bebida",
  disponible: true,
  creado_en: new Date().toISOString(),
  productor: {
    id: 10,
    nombre: "Productor Local"
  }
});

crearProducto({
  nombre: "Error Test",
  precio: "caro"
}).catch(() => {});

listarProductos().catch(() => {});
obtenerProductoPorId(996).catch(() => {});