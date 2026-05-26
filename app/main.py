from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from contextlib import asynccontextmanager
import time, logging, os

from app.core.config import settings
from app.core.database import init_db
from app.routers.auth import router as auth_router
from app.routers import (
    modules_router, exercises_router, progress_router, admin_router
)
from app.seed import seed_database

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    await init_db()
    await seed_database()
    yield
    logger.info("Shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
## PythonBackend.dev — Plataforma de Prática

3 níveis progressivos: **Básico → Intermediário → Avançado**

- 🐣 **Básico**: primeiros passos, tipos, loops, funções, OOP
- 🌐 **Intermediário**: APIs REST, banco de dados, autenticação, Docker  
- 🚀 **Avançado**: performance, arquitetura, testes avançados, Cloud
""",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    ms = round((time.perf_counter() - start) * 1000, 2)
    if request.url.path not in ("/health", "/favicon.ico"):
        logger.info(f"{request.method} {request.url.path} → {response.status_code} ({ms}ms)")
    response.headers["X-Response-Time"] = f"{ms}ms"
    return response


API = "/api/v1"
app.include_router(auth_router,       prefix=API)
app.include_router(modules_router,    prefix=API)
app.include_router(exercises_router,  prefix=API)
app.include_router(progress_router,   prefix=API)
app.include_router(admin_router,      prefix=API)


@app.get("/health", tags=["Sistema"])
async def health():
    return {"status": "ok", "version": settings.APP_VERSION, "app": settings.APP_NAME}


# Serve SPA
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        index = os.path.join(FRONTEND_DIR, "index.html")
        if os.path.isfile(index):
            return FileResponse(index)
        return JSONResponse({"detail": "Frontend not found"}, status_code=404)
