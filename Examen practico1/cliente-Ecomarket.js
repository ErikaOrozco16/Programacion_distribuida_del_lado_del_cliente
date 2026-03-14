// ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────
const BASE_URL = "http://ecomarket.local/api/v1";
const TOKEN = "eyJ0eXAiO..."; // token proporcionado en el examen
const INTERVALO_BASE = 5;     // segundos entre consultas
const INTERVALO_MAX = 60;     // máximo de backoff
const TIMEOUT = 10;           // segundos de timeout por petición



// ─── INTERFAZ OBSERVADOR ──────────────────────────────────────────────────────
class Observador {
    async actualizar(inventario) {
        throw new Error("Debe implementar actualizar()");
    }
}



// ─── OBSERVABLE ───────────────────────────────────────────────────────────────
class MonitorInventario {

    constructor() {
        this._observadores = [];
        this._ultimo_etag = null;
        this._ultimo_estado = null;
        this._ejecutando = false;
        this._intervalo = INTERVALO_BASE;
    }

    suscribir(obs) {
        this._observadores.push(obs);
    }

    desuscribir(obs) {
        this._observadores = this._observadores.filter(o => o !== obs);
    }

    async _notificar(inventario) {
        for (const obs of this._observadores) {
            await obs.actualizar(inventario);
        }
    }



    async _consultar_inventario() {

        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), TIMEOUT * 1000);

        const headers = {
            "Authorization": `Bearer ${TOKEN}`
        };

        if (this._ultimo_etag) {
            headers["If-None-Match"] = this._ultimo_etag;
        }

        try {

            const response = await fetch(`${BASE_URL}/inventario`, {
                method: "GET",
                headers,
                signal: controller.signal
            });

            clearTimeout(timeout);

            // 200 → actualizar estado
            if (response.status === 200) {

                const etag = response.headers.get("etag");
                const data = await response.json();

                this._ultimo_etag = etag;
                this._ultimo_estado = data;

                return data;
            }

            // 304 → sin cambios
            if (response.status === 304) {
                return null;
            }

            // 4xx → error cliente
            if (response.status >= 400 && response.status < 500) {
                console.error("Error cliente:", response.status);
                return null;
            }

            // 5xx → error servidor (activar backoff)
            if (response.status >= 500) {
                console.warn("Error servidor:", response.status);
                this._intervalo = Math.min(this._intervalo * 2, INTERVALO_MAX);
                return null;
            }

        } catch (error) {

            if (error.name === "AbortError") {
                console.warn("Timeout al consultar inventario");
            } else {
                console.warn("Error de conexión:", error.message);
            }

            return null;
        }
    }



    async iniciar() {

        this._ejecutando = true;

        while (this._ejecutando) {

            const datos = await this._consultar_inventario();

            if (datos && JSON.stringify(datos) !== JSON.stringify(this._ultimo_estado)) {
                await this._notificar(datos);
                this._intervalo = INTERVALO_BASE;
            }

            await new Promise(res => setTimeout(res, this._intervalo * 1000));
        }
    }



    detener() {
        this._ejecutando = false;
    }

}



// ─── OBSERVADORES CONCRETOS ───────────────────────────────────────────────────

class ModuloCompras extends Observador {

    async actualizar(inventario) {

        const productos = inventario.productos || [];

        const bajos = productos.filter(p => p.status === "BAJO_MINIMO");

        if (bajos.length > 0) {

            console.log("Productos bajo mínimo:");

            bajos.forEach(p => {
                console.log(`- ${p.nombre} (stock: ${p.stock})`);
            });

        }

    }
}



class ModuloAlertas extends Observador {

    async actualizar(inventario) {

        const productos = inventario.productos || [];

        const bajos = productos.filter(p => p.status === "BAJO_MINIMO");

        for (const p of bajos) {

            try {

                const response = await fetch(`${BASE_URL}/alertas`, {
                    method: "POST",
                    headers: {
                        "Authorization": `Bearer ${TOKEN}`,
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        producto_id: p.id,
                        nombre: p.nombre,
                        stock: p.stock,
                        status: p.status
                    })
                });

                if (response.status === 201) {
                    console.log("Alerta enviada:", p.nombre);
                }

                if (response.status === 422) {
                    console.warn("Alerta inválida (no reintentar):", p.nombre);
                }

            } catch (error) {
                console.error("Error enviando alerta:", error.message);
            }

        }

    }

}



// ─── PUNTO DE ENTRADA ─────────────────────────────────────────────────────────

const monitor = new MonitorInventario();

monitor.suscribir(new ModuloCompras());
monitor.suscribir(new ModuloAlertas());

// iniciar dentro de un entorno async
(async () => {
    await monitor.iniciar();
})();