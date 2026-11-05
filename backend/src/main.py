from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.api.routes import login, me, passwords, planning, rooms, sessions, users
from src.services.common import AuthError

app = FastAPI(title="SmartCampus API")
ROUTERS = (
    login.router,
    sessions.router,
    passwords.router,
    users.router,
    rooms.router,
    planning.router,
    me.router,
)
for router in ROUTERS:
    app.include_router(router)


@app.exception_handler(AuthError)
async def auth_error(request: Request, error: AuthError):
    return JSONResponse(status_code=error.status, content={"detail": error.message})


@app.get("/health")
def health():
    return {"status": "ok"}
