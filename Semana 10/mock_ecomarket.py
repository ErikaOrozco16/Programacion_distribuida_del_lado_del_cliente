import asyncio
from aiohttp import web

_contador = 0

async def handle_login(request):
    # Payload: {"sub":"op1","rol":"viewer","exp":9999999999}
    token = ("eyJhbGciOiJIUzI1NiJ9"
             ".eyJzdWIiOiJvcDEiLCJyb2wiOiJ2aWV3ZXIiLCJleHAiOjk5OTk5OTk5OTl9"
             ".mock_sig")
    return web.json_response({"access_token": token, "refresh_token": "mock.refresh"})

async def handle_inventario(request):
    global _contador
    _contador += 1
    print(f"[MOCK] Petición #{_contador}")
    if _contador <= 3:
        return web.json_response({"productos": _contador * 10})
    elif _contador <= 8:
        return web.Response(status=503, text="Service Unavailable")
    return web.json_response({"productos": _contador * 10, "recuperado": True})

app = web.Application()
app.router.add_post('/auth/login',     handle_login)
app.router.add_get ('/api/inventario', handle_inventario)

if __name__ == '__main__':
    print("[MOCK] EcoMarket en http://localhost:8080  (3 éxitos -> 5x503 -> recuperación)")
    web.run_app(app, port=8080, print=None)
