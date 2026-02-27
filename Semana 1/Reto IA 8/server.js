// server.js
const express = require('express');
const cors = require('cors'); // Importante para que tu cliente no bloquee las peticiones
const app = express();

app.use(cors()); // Permite peticiones desde tu cliente local
app.use(express.json());

let requestCounter = 0; // Contador para el escenario intermitente

// --- ESCENARIOS DE CAOS ---

// 1. ESCENARIO: RED LENTA (Latencia Alta)
// Simula obtener la lista de productos
app.get('/api/products', (req, res) => {
    console.log('🐌 Escenario: La Tortuga (5s delay)');
    setTimeout(() => {
        res.json([
            { id: 1, name: "EcoManzana", price: 1.50 },
            { id: 2, name: "Bolsa Reutilizable", price: 3.00 }
        ]);
    }, 5000); // 5 segundos de espera
});

// 2. ESCENARIO: FALLA INTERMITENTE (Cada 3ra petición)
// Simula agregar al carrito
app.post('/api/cart', (req, res) => {
    requestCounter++;
    console.log(`🎲 Escenario: Intermitente (Petición #${requestCounter})`);
    
    if (requestCounter % 3 === 0) {
        console.log('💥 BOOM! Fallo simulado 503');
        return res.status(503).json({ error: "Servicio no disponible temporalmente" });
    }
    
    res.json({ status: "success", message: "Producto agregado" });
});

// 3. ESCENARIO: RESPUESTA TRUNCADA (Socket Hang Up)
// Simula perfil de usuario
app.get('/api/user/profile', (req, res) => {
    console.log('✂️ Escenario: Cortocircuito');
    res.status(200);
    res.write('{"id": 123, "name": "Usuario Eco", "preferenc'); // JSON incompleto
    // Mata la conexión abruptamente
    res.socket.destroy();
});

// 4. ESCENARIO: FORMATO INESPERADO (HTML en vez de JSON)
// Simula búsqueda
app.get('/api/search', (req, res) => {
    console.log('🎭 Escenario: El Impostor (HTML Return)');
    res.set('Content-Type', 'text/html'); // Engaña al cliente
    res.send('<html><body><h1>502 Bad Gateway</h1><hr>nginx</body></html>');
});

// 5. ESCENARIO: TIMEOUT DEL SERVIDOR
// Simula checkout/pago
app.post('/api/checkout', (req, res) => {
    console.log('🕳️ Escenario: Agujero Negro (Timeout)');
    // No hace nada, deja al cliente esperando
    setTimeout(() => {
       // Opcional: responder muy tarde solo para ver si el cliente ya canceló
       if (!res.headersSent) res.send("Demasiado tarde...");
    }, 65000); 
});

// Iniciar servidor
const PORT = 3000;
app.listen(PORT, () => {
    console.log(`🌪️ Laboratorio de Caos activo en http://localhost:${PORT}`);
});