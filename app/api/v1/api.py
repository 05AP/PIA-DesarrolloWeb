from fastapi import APIRouter

from app.api.v1.endpoints import auth, bombas, operaciones, tanques, users

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Autenticación"])
api_router.include_router(users.router, prefix="/users", tags=["Usuarios (RBAC)"])
api_router.include_router(tanques.router, prefix="/tanques", tags=["Infraestructura - Tanques"])
api_router.include_router(bombas.router, prefix="/bombas", tags=["Infraestructura - Bombas"])
api_router.include_router(operaciones.router, prefix="/operaciones", tags=["Operaciones y Transacciones"])
