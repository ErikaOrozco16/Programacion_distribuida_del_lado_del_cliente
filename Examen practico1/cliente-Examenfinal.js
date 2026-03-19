
//--Simulador de API
global.fetch = async (url, opciones = {}) => {

    console.log("Simulación de petición a:", url);

    if (url.includes("/inventario")) {

        return {
            status: 200,
            headers: {
                get: () => "12345-etag"
            },
            async json() {
                return {
                    productos: [
                        {
                            id: 1,
                            nombre: "Manzanas",
                            stock: 3,
                            status: "BAJO_MINIMO"
                        },
                        {
                            id: 2,
                            nombre: "Leche",
                            stock: 20,
                            status: "OK"
                        }
                    ]
                };
            }
        };

    }

    if (url.includes("/alertas")) {

        return {
            status: 201,
            async json() {
                return { mensaje: "Alerta creada" };
            }
        };

    }

};





// ─── CONFIGURACIÓN ───────────────────────────────────────────────
const BASE_URL = "http://ecomarket.local/api/v1";
const TOKEN = "eyJ0eXAiO...";
const INTERVALO_BASE = 5000;
const INTERVALO_MAX = 60000;
const TIMEOUT = 10000;


// ─── INTERFAZ OBSERVADOR ─────────────────────────────────────────
class Observador {

    async actualizar(inventario) {
        throw new Error("Método actualizar() debe implementarse");
    }

}


// ─── MONITOR DE INVENTARIO (OBSERVABLE) ──────────────────────────
class MonitorInventario {

    constructor() {
        this._observadores = [];
        this._ultimoEtag = null;
        this._ultimoEstado = null;
        this._intervalo = INTERVALO_BASE;
        this._ejecutando = false;
    }

    suscribir(obs) {
        this._observadores.push(obs);
    }

    desuscribir(obs) {
        this._observadores =
            this._observadores.filter(o => o !== obs);
    }

    async _notificar(inventario) {

        for (const obs of this._observadores) {

            try {
                await obs.actualizar(inventario);
            } catch (error) {
                console.error("Error en observador:", error.message);
            }

        }

    }



    async _consultarInventario() {

        const controller = new AbortController();
        const timeout = setTimeout(
            () => controller.abort(),
            TIMEOUT
        );

        const headers = {
            Authorization: `Bearer ${TOKEN}`
        };

        if (this._ultimoEtag) {
            headers["If-None-Match"] = this._ultimoEtag;
        }

        try {

            const response = await fetch(
                `${BASE_URL}/inventario`,
                {
                    method: "GET",
                    headers,
                    signal: controller.signal
                }
            );

            clearTimeout(timeout);


            // ─── 200 OK ───────────────────────────────
            if (response.status === 200) {

                const etag = response.headers.get("etag");
                const data = await response.json();

                if (!data || !data.productos) {
                    console.warn("Respuesta inválida del servidor");
                    return null;
                }

                this._ultimoEtag = etag;

                return data;
            }


            // ─── 304 SIN CAMBIOS ──────────────────────
            if (response.status === 304) {

                  this._intervalo = Math.min(
                    this._intervalo * 2,
                    INTERVALO_MAX
                 );
                return null;
            }


            // ─── ERRORES CLIENTE ──────────────────────
            if (response.status >= 400 && response.status < 500) {

                console.error("Error cliente:", response.status);
                return null;
            }


            // ─── ERRORES SERVIDOR (BACKOFF) ───────────
            if (response.status >= 500) {

                console.warn("Error servidor:", response.status);

                this._intervalo = Math.min(
                    this._intervalo * 2,
                    INTERVALO_MAX
                );

                return null;
            }

            if (response.status === 503) {

               console.warn("Servicio no disponible (503)");

               this._intervalo = Math.min(
                 this._intervalo * 2,
                 INTERVALO_MAX
                );

             return null;
            }

        } catch (error) {

            if (error.name === "AbortError") {
                console.warn("Timeout en consulta inventario");
            } else {
                console.warn("Error conexión:", error.message);
            }

            return null;
        }

    }



    async iniciar() {

        this._ejecutando = true;

        while (this._ejecutando) {

            const datos = await this._consultarInventario();

            if (
                datos &&
                JSON.stringify(datos) !==
                JSON.stringify(this._ultimoEstado)
            ) {

                this._ultimoEstado = datos;

                await this._notificar(datos);

                this._intervalo = INTERVALO_BASE;

            }

            await new Promise(resolve =>
                setTimeout(resolve, this._intervalo)
            );

        }

    }



    detener() {
        this._ejecutando = false;
    }

}



// ─── OBSERVADOR: MÓDULO COMPRAS ──────────────────────────────────
class ModuloCompras extends Observador {

    async actualizar(inventario) {

        const bajos = inventario.productos
            .filter(p => p.status === "BAJO_MINIMO");

        if (bajos.length > 0) {

            console.log("Productos que requieren reposición:");

            bajos.forEach(p => {
                console.log(
                    `${p.nombre} - stock actual: ${p.stock}`
                );
            });

        }

    }

}



// ─── OBSERVADOR: MÓDULO ALERTAS ──────────────────────────────────
class ModuloAlertas extends Observador {

    async actualizar(inventario) {

        const bajos = inventario.productos
            .filter(p => p.status === "BAJO_MINIMO");

        for (const producto of bajos) {

            try {

                const response = await fetch(
                    `${BASE_URL}/alertas`,
                    {
                        method: "POST",
                        headers: {
                            Authorization: `Bearer ${TOKEN}`,
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify({
                            producto_id: producto.id,
                            nombre: producto.nombre,
                            stock: producto.stock,
                            status: producto.status
                        })
                    }
                );

                if (response.status === 201) {
                    console.log(
                        "Alerta creada para:",
                        producto.nombre
                    );
                }

                if (response.status === 422) {
                    console.warn(
                        "Alerta inválida:",
                        producto.nombre
                    );
                }

            } catch (error) {

                console.error(
                    "Error enviando alerta:",
                    error.message
                );

            }

        }

    }

}



// ─── PUNTO DE ENTRADA ────────────────────────────────────────────
const monitor = new MonitorInventario();

monitor.suscribir(new ModuloCompras());
monitor.suscribir(new ModuloAlertas());

(async () => {
    await monitor.iniciar();
})();
