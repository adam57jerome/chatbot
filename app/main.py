from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.routes import sections, trainees
from app.web import BASE_DIR

app = FastAPI(title="Gestion des stagiaires")
app.add_middleware(SessionMiddleware, secret_key="dev-secret-change-me")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/")
def home() -> RedirectResponse:
    return RedirectResponse(url="/stagiaires", status_code=303)


@app.middleware("http")
async def attach_flash_state(request: Request, call_next):
    request.state.flash = request.session.pop("flash", None)
    response = await call_next(request)
    return response


app.include_router(trainees.router)
app.include_router(sections.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8001, reload=True)
