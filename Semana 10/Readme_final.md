# Programacion\_distribuida\_del\_lado\_del\_cliente

# Semana 10 hito 2 :

# Reto 1: Mapa de Responsabilidades

**Equipo:** Erika Alejandra Orozco Vazquez y Ricardo Matos Vizcarra

### Fragmento A

**Componente asignado:** ReceptorAlertas
**Criterio técnico:** Este fragmento parsea el stream SSE línea a línea y extrae la información con el prefijo `data:`, además de llevar control del `\\\\\\\_last\\\\\\\_event\\\\\\\_id`, siendo el único componente que maneja el protocolo a nivel de bytes directamente de la respuesta.

### Fragmento B

**Componente asignado:** ClienteSSEMultiplex / EventRouter
**Criterio técnico:** Se utiliza el patrón Dispatcher llamando a `despachar()` con un diccionario de handlers para ejecutar acciones según el evento, sin conocer detalles del transporte de red ni del origen real de los datos.

### Fragmento C

**Componente asignado:** TokenManager
**Criterio técnico:** Se encarga de la decodificación en Base64URL (con rellenado de padding `=' \\\\\\\* padding`) del JWT para extraer el payload en JSON, que es la responsabilidad específica y exclusiva de este manejador de tokens.

### Fragmento D

**Componente asignado:** CircuitBreaker
**Criterio técnico:** Contiene la lógica transicional del patrón, evaluando si el tiempo transcurrido supera el umbral predeterminado para pasar de estado `ABIERTO` a `SEMIABIERTO`, siendo la única clase con máquina de estados de esta naturaleza.

### Fragmento E

**Componente asignado:** ClienteRobusto
**Criterio técnico:** Orquesta la ejecución de la petición evaluando caducidades desde el gestor de tokens, creando los headers de autenticación requeridos, y luego pasando la función lambda al cb (CircuitBreaker), sin duplicar las lógicas nativas de los componentes hijos.



# Reto 2: Diagrama de Flujo Integrado

**Equipo:** Erika Alejandra Orozco Vazquez y Ricardo Matos Vizcarra

### \[?1] Verificación de expiración del token

* **¿Qué componente verifica si el token expira pronto?**: ClienteRobusto hace la llamada para verificar.
* **¿Qué método se llama y quién lo implementa?**: Se llama al método `is\\\\\\\_expiring\\\\\\\_soon()`, el cual está implementado dentro del `TokenManager`. Si expira, se llama a `refresh\\\\\\\_access\\\\\\\_token()`, también implementado en `TokenManager`.

### \[?2] Salidas posibles del Circuit Breaker en estado SEMIABIERTO

* **Salida A (peticiones concurrentes adicionales)**: Lanza inmediatamente un `CircuitOpenError` (fail-fast) porque en estado SEMIABIERTO solo se permite pasar una petición de prueba para validar el servidor; las adicionales se detienen de forma rápida.
* **Salida B (la petición de prueba pasa)**: Transición del circuito a estado `CERRADO` reiniciando el conteo de fallos tras comprobar que el servidor volvió a estar operativo y retornó éxito.
* **Salida C (resultado de la petición de prueba)**: Se lanza nuevamente la excepción y el circuito vuelve al estado `ABIERTO`, debiéndose reiniciar el temporizador de apertura puesto que el servidor aún falla.

### \[?3] Petición de prueba con éxito (HTTP 200)

* **Transición y método**: Ocurre una transición de estado `SEMIABIERTO` a `CERRADO`. Esta transición la ejecuta el método interno de control de éxitos `\\\\\\\_on\\\\\\\_exito()` en el componente `CircuitBreaker`.
* **Atributo reseteado**: El atributo `self.\\\\\\\_fallos` (o contador de fallos) se resetea a su valor inicial `0`.

### \[?4] Independencia de la conexión SSE

* **¿Interrupción?**: **No**, la apertura del Circuit Breaker HTTP no interrumpe el stream SSE activo, ya que el CB y ClienteRobusto envuelven las peticiones estándar HTTP REST (como `GET /api/inventario`), pero la conexión TCP permanente manejada por ClienteSSEMultiplex ocurre por una vía separada e independiente a estos.

### \[?5] Aislamiento del TokenManager

* **¿Sabe que se cerró el CB?**: **No**. De acuerdo con el **INV-B1**, el TokenManager no tiene ni debe tener ningún atributo relacionado con el estado del Circuit Breaker. Estos componentes están completamente desacoplados y su única orquestación ocurre de forma superficial en el ClienteRobusto.



# Reto 3: Autopsia de ClienteRobusto

**Equipo:** Erika Alejandra Orozco Vazquez y Ricardo Matos Vizcarra

### Defecto A

**Síntoma A:** Los operadores con rol 'viewer' reciben un error de permisos al consultar inventario, aunque deberían poder hacer GET.
**Causa Raíz:** El `CircuitBreaker` está decodificando el JWT internamente y validando roles duros (`admin` o `supervisor`), en la misma función `ejecutar()`. No debería estar manejando lógica de tokens o autorización en absoluto.
**Línea Exacta:**

```python
        if token\\\\\\\_manager:
            token = token\\\\\\\_manager.get\\\\\\\_access\\\\\\\_token()
            pad = 4 - len(token.split('.')\\\\\\\[1]) % 4
            payload = json.loads(
                base64.urlsafe\\\\\\\_b64decode(token.split('.')\\\\\\\[1] + '=' \\\\\\\* pad)
            )
            if payload.get('rol') not in ('admin', 'supervisor'):
                raise PermissionError(f"Rol '{payload\\\\\\\['rol']}' no autorizado")
```

**Corrección:** Eliminar todo este bloque de código.

```python
    def ejecutar(self, fn):
        if self.estado == EstadoCircuito.ABIERTO:
# ... resto
```

**Principio Violado:** Principio de Responsabilidad Única (SRP) e Invariante A1 (INV-A1: El CircuitBreaker nunca accede a campos del payload JWT).

\---

### Defecto B

**Síntoma B:** En los logs de producción aparecen fragmentos del token de acceso.
**Causa Raíz:** Al registrar el fallo en `ClienteRobusto`, se está interpolando `headers\\\\\\\['Authorization']\\\\\\\[:40]`, lo cual filtra información sensible al sistema de registros de la aplicación.
**Línea Exacta:**

```python
            logger.error(
                f"Error: {e}. Auth: {headers\\\\\\\['Authorization']\\\\\\\[:40]}..."
            )
```

**Corrección:** Registrar únicamente el error sin enviar ninguna parte del Header de Auth.

```python
            logger.error(f"Error en endpoint al obtener inventario: {e}")
```

**Principio Violado:** Seguridad de datos sensibles e Invariante B2 (INV-B2: El token de acceso nunca aparece en logs, ni parcialmente, ni truncado).

\---

### Defecto C

**Síntoma C:** Después de que el servidor se recupera y el circuito cierra, sigue acumulando fallos como si fuera la primera vez — el contador no se reinicia.
**Causa Raíz:** Cuando el estado cambia exitosamente de vuelta a `CERRADO`, el contador acumulado de fallos no se resetea, por lo que a la próxima falla se sumará al acumulado previo y se abrirá prematuramente el circuito.
**Línea Exacta:**

```python
    def \\\\\\\_on\\\\\\\_exito(self):
        # ─────────────────────────────────────── BUG C (síntoma C)
        self.estado = EstadoCircuito.CERRADO
        # FALTA: self.\\\\\\\_fallos = 0
```

**Corrección:** Reiniciar el contador en `\\\\\\\_on\\\\\\\_exito()`.

```python
    def \\\\\\\_on\\\\\\\_exito(self):
        self.estado = EstadoCircuito.CERRADO
        self.\\\\\\\_fallos = 0
```

**Principio Violado:** Lógica de máquina de estados de Circuit Breaker e Invariante A3 (INV-A3: Al transicionar SEMIABIERTO → CERRADO, el contador se pone en 0).



# Reto 5: ADR Express

**Equipo:** Erika Alejandra Orozco Vazquez y Ricardo Matos Vizcarra

### Título

Breaker separado para operaciones /auth vs /api generales

### 1 · Contexto

El servidor principal se divide conceptualmente en la provisión de JWT (`/auth/login`, `/auth/refresh`) y la provisión de datos del negocio (`/api/inventario`, `/api/precios`). La tasa de fallos de la base de datos de inventario suele ser mayor, pero el sistema de autenticación podría seguir funcionando correctamente de forma independiente en algunos esquemas de infraestructura, y perder el token implica desloguear al usuario en lugar de solo fallar un request.

### 2 · Decisión

Decidimos que el CircuitBreaker debe recubrir los llamados a la API de negocio y no los llamados al servicio de autenticación y refresco de tokens subyacentes, aislando el mecanismo `TokenManager` del estado del `CircuitBreaker`.

### 3 · Consecuencias positivas

* **Independencia Operativa:** El token puede seguir renovándose con éxito de fondo, de forma que al levantarse el servidor API, la sesión sigue válida y el usuario no fue deslogueado.
* **Reducción del Acoplamiento:** Cumplimos estrictamente los invariantes A1 y B1, donde el CircuitBreaker no conoce la lógica de JWT ni el TokenManager del CircuitBreaker.

### 4 · Consecuencias negativas

* **Carga Oculta:** Si el servicio de auth también sufre problemas masivos, no estamos protegiéndolo de los reintentos inútiles generados por el cliente (a menos que creemos un CB específico para auth).
* **Manejo Desigual de Errores:** Las excepciones que surgen de `TokenManager` tendrán que manejarse directamente por el `ClienteRobusto` o propagarse globalmente, sin el mecanismo `fail-fast` del CB para los errores HTTP 500 de Auth.

### 5 · Escenario adverso

Esta decisión sería incorrecta en una infraestructura de monolito donde `/auth` y `/api` corren exactamente en el mismo hilo/proceso del servidor de base de datos; bajo este escenario, los intentos persistentes de `refresh\\\\\\\_token` durante un fallo crítico del monolito seguirían contribuyendo al colapso por denegación de servicio (DoS) del mismo servicio caído, al no estar limitados por el breaker global.



# Reto 7: Certificación de Invariantes

**Equipo:** Erika Alejandra Orozco Vazquez y Ricardo Matos Vizcarra

|Invariante|Descripción|Estado|Evidencia|
|-|-|-|-|
|**INV-A1**|El CircuitBreaker nunca accede a campos del payload JWT (`sub`, `exp`, `rol`, etc.)|✅ Pasa|El `CircuitBreaker` de nuestro `cliente\\\\\\\_integrado.py` no requiere el parámetro de TokenManager en `ejecutar()` y no importa Base64 o Json para abrir un payload. La prueba manual con `token="no.es.jwt"` no produce error en el CB.|
|**INV-A2**|En estado SEMIABIERTO, exactamente una petición pasa al servidor; las demás reciben `CircuitOpenError` inmediato.|✅ Pasa|A través de la prueba automatizada implementada en `test\\\\\\\_circuit\\\\\\\_breaker.py` usando `asyncio.gather` vemos que solo una llamada es procesada y el resto levanta inmediatamente la excepción de circuito abierto.|
|**INV-A3**|Al transicionar SEMIABIERTO → CERRADO, el contador `\\\\\\\_fallos` se pone en 0.|✅ Pasa|Luego de observar las impresiones en `cliente\\\\\\\_integrado.py` (línea `\\\\\\\[HTTP #9] 200 -> CB: CERRADO (fallos=0)`), y tener la línea `self.\\\\\\\_fallos = 0` directamente en `\\\\\\\_on\\\\\\\_exito()`.|
|**INV-A4**|Un error HTTP 401 o 403 no incrementa `\\\\\\\_fallos`.|✅ Pasa|El filtro `\\\\\\\_es\\\\\\\_fallo\\\\\\\_servidor` dentro del breaker sólo devuelve `True` para errores que digan "503", "timeout" o "connection", ignorando los errores 401 o 403 relacionados a autorizaciones.|
|**INV-B1**|El TokenManager no tiene ningún atributo relacionado con el estado del Circuit Breaker.|✅ Pasa|Revisando la estructura de la clase, vemos que `TokenManager` sólo administra variables internas como `\\\\\\\_access\\\\\\\_token` y funciones de refresh o checkeo local. `hasattr(tm, '\\\\\\\_estado')` es Falso.|
|**INV-B2**|El token de acceso nunca aparece en logs, ni parcialmente, ni truncado con `\\\\\\\[:N]`.|✅ Pasa|Corregido en la autopsia de la Fase 2, ahora el log sólo registra `logger.info(f"\\\\\\\[HTTP #{i}] 503 -> CB: ...")` sin incluir ningún valor del header de autorización extraído.|
|**INV-B3**|Con múltiples peticiones concurrentes expiradas, solo un refresh se ejecuta (patrón singleton).|✅ Pasa|En la prueba en Python, un `asyncio.Lock()` dentro del método `refresh\\\\\\\_access\\\\\\\_token()` limitaría de manera thread-safe a que una llamada concurrente no re-solicite al mock del auth.|



# Reto 8: Test de Regresión Cruzada

**Equipo:** Erika Alejandra Orozco Vazquez y Ricardo Matos Vizcarra

### TC-X1 — SSE activo + Circuit Breaker transiciona a ABIERTO

**Protocolo y Verificación:**

* **Setup:** Configurar un servidor simulado que despache eventos SSE exitosamente en segundo plano. Configurar un servidor para la API REST que empiece a devolver errores `503 Service Unavailable`.
* **Acción:** Lanzar la conexión SSE en un canal en segundo plano (`asyncio.create\\\\\\\_task(cliente\\\\\\\_sse.conectar())`). Acto seguido, en el proceso primario, efectuar llamadas repetitivas con `ClienteRobusto.get\\\\\\\_inventario()` hasta que el `CircuitBreaker` acumule 5 fallos y alcance el estado `ABIERTO`.
* **Verificación:** Observar en los logs si los eventos SSE continuaron despachándose a través del `EventRouter` después de que el Circuit Breaker cambiara de estado a `ABIERTO`.
* **Resultado documentado:** La conexión SSE no se interrumpe y los eventos continúan llegando. Esto ratifica que el CB sólo vigila y corta peticiones al esquema Request/Response HTTP y no a conexiones Socket/Streams TCP.

\---

### TC-X3 — Reconexión SSE con Last-Event-ID tras cierre del circuito

**Protocolo y Verificación:**

* **Setup:** Inicializar un cliente `TokenManager` con token válido y un mock SSE que emite tres eventos con los IDs `ev1`, `ev2`, `ev3`. Configurar el mock para que corte abruptamente la conexión tras el evento `ev3`.
* **Acción:** Al detectar la desconexión TCP, el `ReceptorAlertas` entra en ciclo de back-off para reconexión. Intervenimos abriendo y cerrando el Circuit Breaker de la app mediante peticiones falsas REST en paralelo. Luego de los 60s, el circuito cierra. El `ReceptorAlertas` realiza el re-intento de conexión.
* **Verificación:** Al recibir la conexión del mock SSE nuevamente, leer los headers que envió el cliente `ReceptorAlertas` para identificar si se incluyó el header `Last-Event-ID: ev3`. Asimismo, verificar si el Token enviado en el header `Authorization` fue renovado satisfactoriamente desde el `TokenManager`.
* **Resultado documentado:** Tras la desconexión asíncrona, el `\\\\\\\_last\\\\\\\_event\\\\\\\_id` se mantiene preservado en memoria del `ReceptorAlertas` y la reconexión lo inyecta exitosamente, garantizando la consistencia y persistencia de eventos (evitando procesar `ev1` al `ev3` nuevamente). El token inyectado correspondía a la versión más reciente del singleton TM.



# Bitácora de Uso de IA - Semana 10 (Grand Deploy)

**Equipo:** Erika Alejandra Orozco Vazquez y Ricardo Matos Vizcarra

Este documento consolida el registro auditable del uso de la Inteligencia Artificial a lo largo de los retos de la Semana 10, donde la IA actuó en los roles socráticos solicitados, sin que se haya utilizado para la generación de respuestas directas de código sin comprensión previa.

\---

### Reto 2: Diagrama de Flujo Integrado

* **Rol de IA:** Revisor de diagramas.
* **Prompt Usado:** "Actúa como revisor de arquitectura de sistemas. Nuestro diagrama establece que en estado SEMIABIERTO si la petición de prueba falla, se ejecuta la salida C (lanza excepción y el circuito vuelve a ABIERTO reiniciando timeout). ¿Nuestro flujo tiene nodos incorrectos o faltantes?"
* **Interacción / Resultado:** La IA validó nuestra hipótesis como correcta y señaló que nos faltaba detallar el comportamiento del *TokenManager*. Preguntó: "¿El TokenManager necesita estar enterado de este cierre?".
* **Decisión / Aprendizaje:** Respondimos que no, respetando el invariante INV-B1. La IA validó nuestra respuesta, lo que reforzó nuestro entendimiento del aislamiento de responsabilidades.

\---

### Reto 3: Autopsia de ClienteRobusto

* **Rol de IA:** Inspector de calidad de código socrático.
* **Prompt Usado:** "Actúa como inspector de calidad de código. SÍNTOMA A: Los operadores con rol 'viewer' reciben un error de permisos al consultar inventario. Nuestra hipótesis: El TokenManager está restringiendo la llamada. Nuestra corrección: Modificar el TokenManager. ¿Nuestra hipótesis identifica la causa correcta?"
* **Interacción / Resultado:** La IA se negó a darnos la línea exacta. En su lugar, respondió socráticamente: *"Tu síntoma es de permisos, pero fíjate en el archivo del ClienteRobusto: ¿es realmente el TokenManager el que está decodificando y tomando decisiones de permiso antes de la petición, o hay otro componente involucrado indebidamente?"*.
* **Decisión / Aprendizaje:** Al revisar el código notamos la violación de SRP. El `CircuitBreaker.ejecutar()` estaba abriendo el JWT internamente para validar los roles `admin` o `supervisor`. Cambiamos la corrección a "eliminar la decodificación JWT del CB".

\---

### Reto 4: Integración en Vivo

* **Rol de IA:** Debugger socrático.
* **Prompt Usado:** "Nuestro script falla en la petición #6. Estado del CircuitBreaker: CERRADO. Fallos acumulados: 0. Error: Ninguno aparente, pero el CircuitBreaker no se está abriendo. Comportamiento esperado: Debería abrirse al quinto 503. ¿El problema está en la clasificación del error o en el estado?"
* **Interacción / Resultado:** La IA preguntó: *"¿Qué retorna tu función de `\\\\\\\_es\\\\\\\_fallo\\\\\\\_servidor(error)` cuando recibe un string de error '503 Service Unavailable'? Comprueba si está siendo sensible a mayúsculas."*
* **Decisión / Aprendizaje:** Descubrimos que nuestra validación estaba buscando "503" pero fallaba en otras cadenas al no utilizar `.lower()`. Lo corregimos.

\---

### Reto 5: ADR Express

* **Rol de IA:** Comité de revisión arquitectónica.
* **Prompt Usado:** "(Ver archivo `Semana 10/Reto 5/bitacora\\\\\\\_ia.md`). Presenta un escenario concreto de EcoMarket donde separar el CircuitBreaker de auth del CircuitBreaker de la API produzca un resultado peor."
* **Interacción / Resultado:** Planteó un escenario donde ambos servicios se encuentran en un Gateway común que colapsa.
* **Decisión / Aprendizaje:** Aceptamos el riesgo, pero mantuvimos la decisión de separar las responsabilidades por priorizar el Desacoplamiento frente a una falla sistémica monolítica poco habitual en nuestra arquitectura nativa distribuida.

\---

### Reto 6: Árbitro de Reconexión SSE

* **Rol de IA:** Arquitecto de AWS especialista en e-commerce.
* **Prompt Usado:** "EcoMarket tiene 1 200 operadores simultáneos en Black Friday. Nuestro argumento para la Estrategia B (SSE independiente) es que son canales separados y el CB no debe ahogar las notificaciones Push persistentes. Presenta el contra-argumento más fuerte."
* **Interacción / Resultado:** Planteó el "Efecto Manada" (Thundering Herd Problem): *"Si el servicio HTTP cayó, probablemente el host de notificaciones también sufre si comparten hardware. Reconectar 1200 sockets a la vez ahogará la RAM del servidor y provocará Timeouts severos. ¿Qué pasa si ambos servidores están en el mismo host?"*
* **Decisión / Aprendizaje:** Modificamos nuestra justificación. Determinamos que la Estrategia B solo es la mejor bajo una arquitectura estricta de Microservicios aislados. Añadimos un apunte de "Backoff Exponencial" para que el cliente Socket no asalte el servidor.

\---

### Reto 8: Test de Regresión Cruzada

* **Rol de IA:** Co-desarrollador de pruebas de integración.
* **Prompt Usado:** "TC-X2: Setup: TM devuelve is\_expiring\_soon=True. CB está en SEMIABIERTO. Acción: Llamar a get\_inventario(). Verificación: Comprobar que mock HTTP recibe la petición exitosamente. ¿Hay un caso borde que nuestra verificación no cubre?"
* **Interacción / Resultado:** Respondió: *"¿Qué sucede si tu función intenta hacer la llamada HTTP ANTES de recibir la confirmación de la promesa del `refresh\\\\\\\_access\\\\\\\_token`? Tu verificación actual no cuenta el ORDEN cronológico. Solo sabes que ocurrieron. Mide el número de veces que se invocó cada mock y asegura que el orden en código sea asíncronamente bloqueante (await)."*
* **Decisión / Aprendizaje:** Agregamos contadores específicos `refresh\\\\\\\_count` y `mock\\\\\\\_requests` en el script Python `test\\\\\\\_tc\\\\\\\_x2\\\\\\\_refresh\\\\\\\_semiaabierto.py` para asertar matemáticamente que el flujo de expiración bloquea la petición hasta actualizar el JWT.



# Contribución del Equipo - Examen Práctico 2

**Equipo:** Erika Alejandra Orozco Vazquez y Ricardo Matos Vizcarra

### División de Trabajo y Defensa de Aportaciones

1. **Erika Alejandra Orozco Vazquez**

   * **Responsabilidades:** Implementación asíncrona del Circuit Breaker (`test\\\\\\\_circuit\\\\\\\_breaker.py`), resolución de las condiciones de carrera concurrentes (mutua exclusión para SEMIABIERTO en INV-A2) y la redacción reflexiva sobre los trade-offs de reconexión SSE (Reto 6 y Reto 10).
   * **Defensa Breve:** El Circuit Breaker representa la principal trinchera para proteger el API de sobrecargas. Resolver el bug de concurrencia fue vital, ya que un estado SEMIABIERTO que no utiliza flags tipo mutex terminaría inundando el servidor fallido en vez de enviar solo la petición de prueba unitaria requerida.
2. **Ricardo Matos Vizcarra**

   * **Responsabilidades:** Integración y orquestación del cliente con Token Manager (`cliente\\\\\\\_integrado.py`), resolución de los bugs de Autopsia (SRP) y estructuración de la prueba cruzada TC-X2 para verificar que el refresh de tokens ocurre en el orden correcto antes del llamado al Circuit Breaker.
   * **Defensa Breve:** Desacoplar el servicio de Autenticación de las peticiones de Dominio aseguró la satisfacción de los invariantes INV-A1 e INV-B1. La creación del test de regresión cruzada permitió validar la resistencia de esta separación, garantizando que un fallo en inventario no desloguea accidentalmente a los usuarios de EcoMarket.

