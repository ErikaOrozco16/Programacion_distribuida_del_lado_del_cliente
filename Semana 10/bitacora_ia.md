# Bitácora de Uso de IA - Semana 10 (Grand Deploy)

**Equipo:** Erika Alejandra Orozco Vazquez y Ricardo Matos Vizcarra

Este documento consolida el registro auditable del uso de la Inteligencia Artificial a lo largo de los retos de la Semana 10, donde la IA actuó en los roles socráticos solicitados, sin que se haya utilizado para la generación de respuestas directas de código sin comprensión previa.

---

### Reto 2: Diagrama de Flujo Integrado
- **Rol de IA:** Revisor de diagramas.
- **Prompt Usado:** "Actúa como revisor de arquitectura de sistemas. Nuestro diagrama establece que en estado SEMIABIERTO si la petición de prueba falla, se ejecuta la salida C (lanza excepción y el circuito vuelve a ABIERTO reiniciando timeout). ¿Nuestro flujo tiene nodos incorrectos o faltantes?"
- **Interacción / Resultado:** La IA validó nuestra hipótesis como correcta y señaló que nos faltaba detallar el comportamiento del *TokenManager*. Preguntó: "¿El TokenManager necesita estar enterado de este cierre?". 
- **Decisión / Aprendizaje:** Respondimos que no, respetando el invariante INV-B1. La IA validó nuestra respuesta, lo que reforzó nuestro entendimiento del aislamiento de responsabilidades.

---

### Reto 3: Autopsia de ClienteRobusto
- **Rol de IA:** Inspector de calidad de código socrático.
- **Prompt Usado:** "Actúa como inspector de calidad de código. SÍNTOMA A: Los operadores con rol 'viewer' reciben un error de permisos al consultar inventario. Nuestra hipótesis: El TokenManager está restringiendo la llamada. Nuestra corrección: Modificar el TokenManager. ¿Nuestra hipótesis identifica la causa correcta?"
- **Interacción / Resultado:** La IA se negó a darnos la línea exacta. En su lugar, respondió socráticamente: *"Tu síntoma es de permisos, pero fíjate en el archivo del ClienteRobusto: ¿es realmente el TokenManager el que está decodificando y tomando decisiones de permiso antes de la petición, o hay otro componente involucrado indebidamente?"*.
- **Decisión / Aprendizaje:** Al revisar el código notamos la violación de SRP. El `CircuitBreaker.ejecutar()` estaba abriendo el JWT internamente para validar los roles `admin` o `supervisor`. Cambiamos la corrección a "eliminar la decodificación JWT del CB".

---

### Reto 4: Integración en Vivo
- **Rol de IA:** Debugger socrático.
- **Prompt Usado:** "Nuestro script falla en la petición #6. Estado del CircuitBreaker: CERRADO. Fallos acumulados: 0. Error: Ninguno aparente, pero el CircuitBreaker no se está abriendo. Comportamiento esperado: Debería abrirse al quinto 503. ¿El problema está en la clasificación del error o en el estado?"
- **Interacción / Resultado:** La IA preguntó: *"¿Qué retorna tu función de `_es_fallo_servidor(error)` cuando recibe un string de error '503 Service Unavailable'? Comprueba si está siendo sensible a mayúsculas."*
- **Decisión / Aprendizaje:** Descubrimos que nuestra validación estaba buscando "503" pero fallaba en otras cadenas al no utilizar `.lower()`. Lo corregimos.

---

### Reto 5: ADR Express
- **Rol de IA:** Comité de revisión arquitectónica.
- **Prompt Usado:** "(Ver archivo `Semana 10/Reto 5/bitacora_ia.md`). Presenta un escenario concreto de EcoMarket donde separar el CircuitBreaker de auth del CircuitBreaker de la API produzca un resultado peor."
- **Interacción / Resultado:** Planteó un escenario donde ambos servicios se encuentran en un Gateway común que colapsa.
- **Decisión / Aprendizaje:** Aceptamos el riesgo, pero mantuvimos la decisión de separar las responsabilidades por priorizar el Desacoplamiento frente a una falla sistémica monolítica poco habitual en nuestra arquitectura nativa distribuida.

---

### Reto 6: Árbitro de Reconexión SSE
- **Rol de IA:** Arquitecto de AWS especialista en e-commerce.
- **Prompt Usado:** "EcoMarket tiene 1 200 operadores simultáneos en Black Friday. Nuestro argumento para la Estrategia B (SSE independiente) es que son canales separados y el CB no debe ahogar las notificaciones Push persistentes. Presenta el contra-argumento más fuerte."
- **Interacción / Resultado:** Planteó el "Efecto Manada" (Thundering Herd Problem): *"Si el servicio HTTP cayó, probablemente el host de notificaciones también sufre si comparten hardware. Reconectar 1200 sockets a la vez ahogará la RAM del servidor y provocará Timeouts severos. ¿Qué pasa si ambos servidores están en el mismo host?"*
- **Decisión / Aprendizaje:** Modificamos nuestra justificación. Determinamos que la Estrategia B solo es la mejor bajo una arquitectura estricta de Microservicios aislados. Añadimos un apunte de "Backoff Exponencial" para que el cliente Socket no asalte el servidor.

---

### Reto 8: Test de Regresión Cruzada
- **Rol de IA:** Co-desarrollador de pruebas de integración.
- **Prompt Usado:** "TC-X2: Setup: TM devuelve is_expiring_soon=True. CB está en SEMIABIERTO. Acción: Llamar a get_inventario(). Verificación: Comprobar que mock HTTP recibe la petición exitosamente. ¿Hay un caso borde que nuestra verificación no cubre?"
- **Interacción / Resultado:** Respondió: *"¿Qué sucede si tu función intenta hacer la llamada HTTP ANTES de recibir la confirmación de la promesa del `refresh_access_token`? Tu verificación actual no cuenta el ORDEN cronológico. Solo sabes que ocurrieron. Mide el número de veces que se invocó cada mock y asegura que el orden en código sea asíncronamente bloqueante (await)."*
- **Decisión / Aprendizaje:** Agregamos contadores específicos `refresh_count` y `mock_requests` en el script Python `test_tc_x2_refresh_semiaabierto.py` para asertar matemáticamente que el flujo de expiración bloquea la petición hasta actualizar el JWT.
