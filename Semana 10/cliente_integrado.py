import asyncio
import time
import base64
import json
import logging
from enum import Enum
import aiohttp

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

class EstadoCircuito(Enum):
    CERRADO = "CERRADO"
    ABIERTO = "ABIERTO"
    SEMIABIERTO = "SEMIABIERTO"

class CircuitOpenError(Exception):
    pass

class CircuitBreaker:
    def __init__(self, umbral=5, timeout=60):
        self.estado = EstadoCircuito.CERRADO
        self._umbral = umbral
        self._timeout = timeout
        self._fallos = 0
        self._tiempo_apertura = None

    async def ejecutar(self, fn):
        if self.estado == EstadoCircuito.ABIERTO:
            if time.time() - self._tiempo_apertura >= self._timeout:
                self.estado = EstadoCircuito.SEMIABIERTO
                logger.info(f"[BREAKER] Timeout {self._timeout}s -> SEMIABIERTO")
            else:
                raise CircuitOpenError("CircuitOpenError (sin tocar el servidor)")
        try:
            resultado = await fn()
            self._on_exito()
            return resultado
        except Exception as e:
            self._on_fallo(e)
            raise

    def _on_exito(self):
        self.estado = EstadoCircuito.CERRADO
        self._fallos = 0

    def _on_fallo(self, error):
        if not self._es_fallo_servidor(error):
            return
        self._fallos += 1
        if self._fallos >= self._umbral and self.estado != EstadoCircuito.ABIERTO:
            self.estado = EstadoCircuito.ABIERTO
            self._tiempo_apertura = time.time()

    def _es_fallo_servidor(self, error):
        msg = str(error).lower()
        return '503' in msg or 'timeout' in msg or 'connection' in msg or 'service unavailable' in msg

class TokenManager:
    def __init__(self):
        self._access_token = None
        
    def store_token(self, token):
        self._access_token = token
        
    def get_access_token(self):
        return self._access_token
        
    def get_auth_header(self):
        return {'Authorization': f'Bearer {self._access_token}'} if self._access_token else {}
        
    def is_expiring_soon(self):
        return False
        
    async def refresh_access_token(self):
        pass # mock

class ClienteRobusto:
    def __init__(self, tm, cb):
        self._tm = tm
        self._cb = cb
        self._session = None

    async def iniciar_sesion(self):
        self._session = aiohttp.ClientSession()
        async with self._session.post('http://localhost:8080/auth/login') as resp:
            data = await resp.json()
            token = data['access_token']
            self._tm.store_token(token)
            
            pad = 4 - len(token.split('.')[1]) % 4
            payload = json.loads(base64.urlsafe_b64decode(token.split('.')[1] + '=' * pad))
            logger.info(f"[LOGIN] Token almacenado -> rol={payload.get('rol')}")

    async def get_inventario(self, i):
        if self._tm.is_expiring_soon():
            await self._tm.refresh_access_token()
            
        headers = self._tm.get_auth_header()
        
        async def mock_http_get():
            async with self._session.get('http://localhost:8080/api/inventario', headers=headers) as resp:
                if resp.status == 503:
                    raise ConnectionError("503 Service Unavailable")
                return await resp.json()

        try:
            resultado = await self._cb.ejecutar(mock_http_get)
            logger.info(f"[HTTP #{i}] 200 -> productos={resultado.get('productos')} -> CB: {self._cb.estado.value} (fallos={self._cb._fallos})")
            if self._cb.estado == EstadoCircuito.CERRADO and self._cb._fallos == 0 and getattr(self, '_ui_disabled', False):
                logger.info("[UI] banner=oculto -> action=enable_checkout")
                self._ui_disabled = False
            return resultado
        except CircuitOpenError as e:
            logger.info(f"[BREAKER] Fail fast -> {e}")
            raise
        except Exception as e:
            if self._cb.estado == EstadoCircuito.ABIERTO and not getattr(self, '_ui_disabled', False):
                logger.info("[UI] banner=Servidor temporalmente no disponible -> action=disable_checkout")
                self._ui_disabled = True
            logger.info(f"[HTTP #{i}] 503 -> CB: {self._cb.estado.value} (fallos={self._cb._fallos})")
            raise

    async def cerrar(self):
        if self._session:
            await self._session.close()
            print("Conexion cerrada")

async def main():
    # El CB abre tras 5 fallos, pero para el test usaremos 2s de timeout en vez de 60s
    cb = CircuitBreaker(umbral=5, timeout=2) 
    tm = TokenManager()
    cliente = ClienteRobusto(tm, cb)
    
    await cliente.iniciar_sesion()
    
    # 3 exitos, 5 fallos, 1 open error
    for i in range(1, 10):
        try:
            await cliente.get_inventario(i)
        except Exception:
            pass
        await asyncio.sleep(0.5)
        
    # Esperar al timeout
    await asyncio.sleep(2.1)
    
    # Recovery
    try:
        await cliente.get_inventario(10)
    except Exception:
        pass
        
    logger.info(f"Estado final: circuito={cb.estado.value} -> token_valido={cliente._tm.get_access_token() is not None}")
    await cliente.cerrar()

if __name__ == '__main__':
    asyncio.run(main())
