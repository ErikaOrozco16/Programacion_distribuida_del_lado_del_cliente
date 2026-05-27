# Reto IA 2 - Diagrama de estados del cliente

```text
Estados:
  [SIN_SESION]
      El cliente no tiene tokens y solo puede mostrar login.

  [LOGIN_EN_PROCESO]
      El cliente envio credenciales y espera respuesta del servidor.

  [AUTENTICADO]
      El cliente tiene access_token y puede hacer peticiones autenticadas.

  [REFRESH_EN_PROCESO]
      El access_token esta por expirar o recibio 401; se solicita token nuevo.

  [LOGOUT_EN_PROCESO]
      El cliente limpia estado local y cancela trabajo pendiente.

  [ERROR_RECUPERABLE]
      Hubo fallo de red temporal; se puede reintentar sin perder sesion.

Transiciones:
  SIN_SESION -- usuario_envia_credenciales -->
      LOGIN_EN_PROCESO
      Accion: enviar POST /api/auth/login.

  LOGIN_EN_PROCESO -- login_200 -->
      AUTENTICADO
      Accion: guardar access_token y refresh_token, iniciar timer proactivo.

  LOGIN_EN_PROCESO -- login_401 -->
      SIN_SESION
      Accion: mostrar error y no guardar tokens.

  AUTENTICADO -- exp_menor_o_igual_a_5_min -->
      REFRESH_EN_PROCESO
      Accion: pausar refresh duplicados y llamar POST /api/auth/refresh.

  AUTENTICADO -- respuesta_401_en_recurso -->
      REFRESH_EN_PROCESO
      Accion: ejecutar refresh reactivo y marcar la peticion para reintento unico.

  REFRESH_EN_PROCESO -- refresh_200 -->
      AUTENTICADO
      Accion: guardar nuevo access_token, liberar llamadas en espera y reintentar.

  REFRESH_EN_PROCESO -- refresh_401 -->
      LOGOUT_EN_PROCESO
      Accion: asumir sesion vencida, limpiar tokens y pedir nuevo login.

  REFRESH_EN_PROCESO -- error_red_temporal -->
      ERROR_RECUPERABLE
      Accion: informar fallo temporal y permitir reintento controlado.

  ERROR_RECUPERABLE -- reintento_refresh_exitoso -->
      AUTENTICADO
      Accion: guardar token renovado y continuar.

  AUTENTICADO -- usuario_cierra_sesion -->
      LOGOUT_EN_PROCESO
      Accion: cancelar timers, limpiar tokens y cola de refresh.

  LOGOUT_EN_PROCESO -- limpieza_completa -->
      SIN_SESION
      Accion: redirigir al login.
```

La transicion mas delicada es `AUTENTICADO -> REFRESH_EN_PROCESO`, porque puede entrar por dos rutas al mismo tiempo: refresh proactivo por reloj y refresh reactivo por 401. Por eso se usa un singleton de refresh.
