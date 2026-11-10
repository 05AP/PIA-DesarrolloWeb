import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.v1.api import api_router
from app.core.config import settings
from app.db.init_db import init_db
from app.db.session import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("gasolinera")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Ciclo de vida de la aplicación: crea tablas y siembra datos iniciales al arrancar."""
    db = SessionLocal()
    try:
        init_db(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="""
# API RESTful - Sistema de Estación de Servicio (Gasolinera)

API desarrollada en **Python** y **FastAPI** para la administración de operaciones, transacciones,
inventario de combustible y seguridad de una gasolinera.

### Características
* **Arquitectura Monolítica Modular** en capas: Core, DB, Models, Schemas, Services y API.
* **Seguridad**: autenticación **JWT** (HS256), contraseñas con **bcrypt** y control de acceso por roles
  (**ADMIN**, **SUPERVISOR**, **DESPACHADOR**).
* **Infraestructura**: tanques subterráneos (Magna, Premium, Diésel) y dispensarios/bombas por isla.
* **Proceso central (ACID)**: despacho de combustible que valida bomba e inventario, calcula el importe,
  descuenta el tanque, avanza el odómetro y registra la venta con folio único en una sola transacción.
* **Suministro**: recepción de pipas con validación anti-derrame y de costo vs. precio.
* **Corte de turno**: arqueo por método de pago y combustible, con auditoría de odómetros.
* **Validación** estricta con **Pydantic v2**.
    """,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# La API usa tokens Bearer (no cookies), por lo que no se requieren credenciales CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Registra el error completo en logs y devuelve un mensaje genérico (no expone detalles internos)."""
    logger.exception("Error no controlado en %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Error interno del servidor. La operación no se completó."},
    )


app.include_router(api_router, prefix=settings.API_V1_STR)

if FRONTEND_DIR.exists():
    app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


@app.get("/app", include_in_schema=False)
def frontend_app_redirect():
    """Redirige al Frontend de Pruebas (POS y Dashboard)."""
    return RedirectResponse(url="/frontend/")


@app.get("/", include_in_schema=False)
def root_redirect():
    """Redirige la raíz a la interfaz web."""
    return RedirectResponse(url="/frontend/")


@app.get("/health", tags=["Estado del Sistema"])
def health_check():
    """Health check para el balanceador / plataforma en la nube. Verifica también la conexión a la BD."""
    db_ok = True
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check: la base de datos no responde")
        db_ok = False
    finally:
        db.close()

    body = {
        "status": "online" if db_ok else "degraded",
        "database": "ok" if db_ok else "error",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }
    return JSONResponse(status_code=200 if db_ok else 503, content=body)
