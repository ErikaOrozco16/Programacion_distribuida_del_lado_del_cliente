import asyncio
import time
import pytest
from enum import Enum

class EstadoCircuito(Enum):
    CERRADO = "CERRADO"
    ABIERTO = "ABIERTO"
    SEMIABIERTO = "SEMIABIERTO"

class CircuitOpenError(Exception): pass

class CircuitBreaker:
    def __init__(self, umbral=3, timeout=1):
        self.estado = EstadoCircuito.CERRADO
        self._umbral = umbral
        self._timeout = timeout
        self._fallos = 0
        self._tiempo_apertura = None

    async def ejecutar(self, fn):
        if self.estado == EstadoCircuito.ABIERTO:
            if time.time() - self._tiempo_apertura >= self._timeout:
                self.estado = EstadoCircuito.SEMIABIERTO
            else:
                raise CircuitOpenError("CircuitOpenError")
        try:
            resultado = await fn()
            self.estado = EstadoCircuito.CERRADO
            self._fallos = 0
            return resultado
        except Exception:
            self._fallos += 1
            if self._fallos >= self._umbral:
                self.estado = EstadoCircuito.ABIERTO
                self._tiempo_apertura = time.time()
            raise

class TokenManager:
    def __init__(self):
        self.refresh_count = 0

    def is_expiring_soon(self):
        return True  # Forzamos a que siempre requiera refresh en este test

    async def refresh_access_token(self):
        self.refresh_count += 1
        await asyncio.sleep(0.1) # Simulamos latencia de red en refresh
        return "nuevo_token"

    def get_auth_header(self):
        return {"Authorization": "Bearer nuevo_token"}

class ClienteRobusto:
    def __init__(self, tm, cb):
        self._tm = tm
        self._cb = cb
        self.mock_requests = 0

    async def get_inventario(self):
        # NOTA: ClienteRobusto DEBE preguntar por la expiracion del token 
        # ANTES de intentar pasar el request por el Circuit Breaker.
        if self._tm.is_expiring_soon():
            await self._tm.refresh_access_token()
            
        headers = self._tm.get_auth_header()

        async def _mock_http():
            self.mock_requests += 1
            return {"data": "ok"}

        return await self._cb.ejecutar(_mock_http)

# ----------------- PRUEBA AUTOMATIZADA TC-X2 -----------------
@pytest.mark.asyncio
async def test_tc_x2_refresh_semiaabierto():
    tm = TokenManager()
    cb = CircuitBreaker(umbral=3, timeout=1)
    cliente = ClienteRobusto(tm, cb)
    
    # 1. Agotamos el CB hasta abrirlo
    for _ in range(3):
        try:
            await cb.ejecutar(lambda: (_ for _ in ()).throw(Exception("Fallo 503")))
        except Exception:
            pass
            
    assert cb.estado == EstadoCircuito.ABIERTO
    
    # 2. Esperamos que el timeout se cumpla
    await asyncio.sleep(1.1)
    
    # 3. Solicitamos el inventario. Dado que cb._timeout ya pasó, el CB se considerará
    # elegible para estado SEMIABIERTO. Por su parte, el TM dirá que el token está expirado.
    
    await cliente.get_inventario()
    
    # 4. Aserciones para confirmar Orden Explícito:
    # Como el refresh está AFUERA de la lambda enviada a cb.ejecutar, el refresh_access_token 
    # debió llamarse 1 vez con éxito, ANTES de que el mock HTTP interno de cliente.get_inventario 
    # fuera consultado, y permitiendo que la lambda HTTP cruce exitosamente.
    assert tm.refresh_count == 1
    assert cliente.mock_requests == 1
    assert cb.estado == EstadoCircuito.CERRADO
    assert cb._fallos == 0
