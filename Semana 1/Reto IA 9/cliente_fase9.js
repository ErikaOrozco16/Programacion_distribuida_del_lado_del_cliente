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

const BASE_URL = 'http://127.0.0.1:4010';

// ===================== WRAPPER YA EXISTENTE =====================

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

// =================== Funciones para llamar al  servidos (productos) =====================  

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

  if (!nuevoProducto || typeof nuevoProducto !== 'object') {
    throw new Error("Producto inválido");
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

// ===================== PRUEBAS =====================

console.log("🚀 Iniciando pruebas de creación...");

async function main() {

// INFO + DEBUG
console.log("INFO y DEBUG");
try {
await apiFetchConLogging('/productos');
} catch (e){}

// ERROR 401
console.log("ERROR 401");
try {
await apiFetchConLogging('/productos', {
  method: 'POST',
  body: JSON.stringify({})
});
} catch (e){}

//  (WARN)
console.log("WARN");
try {
await apiFetchConLogging('/debug/slow?delay=6000');
} catch (e){}

}

main();
