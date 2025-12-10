"""Main FastAPI application for TwinSync Spot."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pathlib import Path

from app.db import Database
from app.camera.ha_adapter import HACamera
from app.core.analyzer import SpotAnalyzer
from app.api.routes import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    # Startup
    db = Database()
    await db.init()
    
    app.state.db = db
    app.state.camera = HACamera()
    app.state.analyzer = SpotAnalyzer()
    
    yield
    
    # Shutdown (cleanup if needed)


# Create FastAPI app
app = FastAPI(
    title="TwinSync Spot",
    description="Does this match YOUR definition?",
    version="1.0.3",
    lifespan=lifespan
)

# Mount static files
static_path = Path(__file__).parent / "web" / "static"
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Setup templates
templates_path = Path(__file__).parent / "web" / "templates"
templates = Jinja2Templates(directory=str(templates_path))

# Include API routes
app.include_router(api_router)


# Web routes
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Home page - spots grid."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/add", response_class=HTMLResponse)
async def add_spot(request: Request):
    """Add new spot page."""
    return templates.TemplateResponse("add_spot.html", {"request": request})


@app.get("/spot/{spot_id}", response_class=HTMLResponse)
async def spot_detail(request: Request, spot_id: int):
    """Spot detail page."""
    return templates.TemplateResponse("spot_detail.html", {
        "request": request,
        "spot_id": spot_id
    })


@app.get("/settings", response_class=HTMLResponse)
async def settings(request: Request):
    """Settings page."""
    return templates.TemplateResponse("settings.html", {"request": request})
