"""Stock Mann — Main entry point."""

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager

from app.data.database import init_db
from app.api.routes import router
from app.scheduler import start_scheduler, stop_scheduler
from config.settings import API_HOST, API_PORT


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    print("Stock Mann is running!")
    yield
    stop_scheduler()


app = FastAPI(
    title="Stock Mann",
    description="Real-time Indian Stock Market Analysis System",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="app/dashboard/static"), name="static")
templates = Jinja2Templates(directory="app/dashboard/templates")

app.include_router(router)


@app.get("/")
async def landing_page(request: Request):
    return templates.TemplateResponse(request=request, name="landing.html")


@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")


@app.get("/terminal")
async def terminal(request: Request):
    return templates.TemplateResponse(request=request, name="dashboard.html")


@app.get("/profile")
async def profile_page():
    return RedirectResponse(url="/terminal", status_code=302)


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", API_PORT))
    is_dev = os.environ.get("ENV", "dev") == "dev"
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=is_dev)
