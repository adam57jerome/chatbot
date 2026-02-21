from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.db import init_db
from app.routes import sections, trainees
from app.web import BASE_DIR


class FlashStateMiddleware(BaseHTTPMiddleware):
    """Attach flash message from session to request.state."""

    async def dispatch(self, request: Request, call_next):
        session = request.scope.get("session")
        if isinstance(session, dict):
            request.state.flash = session.pop("flash", None)
        else:
            request.state.flash = None
        response = await call_next(request)
        return response


app = FastAPI(title="Gestion des stagiaires")
# Important: SessionMiddleware must run before any middleware that reads session.
# Starlette executes the most recently added middleware first on request.
app.add_middleware(FlashStateMiddleware)
app.add_middleware(SessionMiddleware, secret_key="dev-secret-change-me")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.on_event("startup")
def startup_init_db() -> None:
    init_db()


@app.get("/")
def home() -> RedirectResponse:
    return RedirectResponse(url="/stagiaires", status_code=303)


app.include_router(trainees.router)
app.include_router(sections.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8001, reload=True)
