from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, require_admin, require_supervisor_or_admin
from app.models.user import RolEnum, Usuario
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services.auth_service import AuthService

router = APIRouter()


@router.get(
    "/",
    response_model=List[UserResponse],
    summary="Listar usuarios del sistema (ADMIN y SUPERVISOR)",
)
def get_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    rol: Optional[RolEnum] = None,
    solo_activos: Optional[bool] = None,
    db: Session = Depends(get_db),
    _user: Usuario = Depends(require_supervisor_or_admin),
):
    return AuthService.list_users(db, skip=skip, limit=limit, rol=rol, solo_activos=solo_activos)


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear usuario (Solo ADMIN)",
)
def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(require_admin),
):
    return AuthService.create_user(db, user_in=user_in)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Obtener usuario por ID (ADMIN y SUPERVISOR)",
)
def get_user_by_id(
    user_id: int,
    db: Session = Depends(get_db),
    _user: Usuario = Depends(require_supervisor_or_admin),
):
    return AuthService.get_by_id_or_404(db, user_id=user_id)


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Actualizar usuario (Solo ADMIN)",
)
def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_admin: Usuario = Depends(require_admin),
):
    return AuthService.update_user(db, user_id=user_id, user_in=user_in, current_user=current_admin)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desactivar usuario (Solo ADMIN)",
    description="Baja lógica: el usuario queda inactivo y se conserva su historial de operaciones.",
)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: Usuario = Depends(require_admin),
):
    AuthService.delete_user(db, user_id=user_id, current_user=current_admin)
