from __future__ import annotations

import os
from urllib.parse import quote

from fastapi import FastAPI, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.auth import is_auth_enabled, session_is_authenticated, verify_credentials
from app.db import init_db
from app.routes import sections, trainees
from app.web import BASE_DIR, templates


class FlashStateMiddleware(BaseHTTPMiddleware):
    """Attach flash message from session to request.state."""

    async def dispatch(self, request: Request, call_next):
        session = request.scope.get("session")
        if isinstance(session, dict):
            request.state.flash = session.pop("flash", None)
        else:
            request.state.flash = None
        return await call_next(request)


class AuthRequiredMiddleware(BaseHTTPMiddleware):
    """Protect FastAPI routes when auth env vars are configured."""

    EXCLUDED_PREFIXES = ("/static",)
    EXCLUDED_PATHS = {"/login", "/health", "/openapi.json", "/docs", "/redoc"}

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not is_auth_enabled():
            return await call_next(request)

        if path in self.EXCLUDED_PATHS or any(path.startswith(prefix) for prefix in self.EXCLUDED_PREFIXES):
            return await call_next(request)

        session = request.scope.get("session") if isinstance(request.scope.get("session"), dict) else {}
        if session_is_authenticated(session):
            return await call_next(request)

        if request.method == "GET":
            return RedirectResponse(url=f"/login?next={quote(path)}", status_code=303)
        return JSONResponse({"detail": "Authentification requise."}, status_code=401)


app = FastAPI(title="Gestion des stagiaires")
# Important: SessionMiddleware must run before middlewares that read request scope session.
# Starlette executes the most recently added middleware first on request.
app.add_middleware(FlashStateMiddleware)
app.add_middleware(AuthRequiredMiddleware)
app.add_middleware(SessionMiddleware, secret_key=(os.getenv("APP_SECRET_KEY") or "dev-secret-change-me"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.on_event("startup")
def startup_init_db() -> None:
    init_db()


@app.get("/")
def home() -> RedirectResponse:
    return RedirectResponse(url="/stagiaires", status_code=303)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/login")
def login_form(request: Request, next: str = "/stagiaires"):
    if session_is_authenticated(request.scope.get("session") if isinstance(request.scope.get("session"), dict) else {}):
        return RedirectResponse(next, status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": "", "next": next})


@app.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/stagiaires"),
):
    if verify_credentials(username, password):
        session = request.scope.get("session")
        if isinstance(session, dict):
            session["auth_user"] = username.strip()
            session["flash"] = {"kind": "success", "message": "Connexion réussie."}
        return RedirectResponse(next or "/stagiaires", status_code=303)

    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Identifiants invalides.", "next": next},
        status_code=401,
    )


@app.post("/logout")
def logout(request: Request):
    session = request.scope.get("session")
    if isinstance(session, dict):
        session.pop("auth_user", None)
        session["flash"] = {"kind": "info", "message": "Déconnexion effectuée."}
    return RedirectResponse("/login", status_code=303)


app.include_router(trainees.router)
app.include_router(sections.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8001, reload=True)
