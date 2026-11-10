from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import (
    get_current_user,
    get_db,
    require_admin,
    require_supervisor_or_admin,
)
from app.models.infraestructura import EstadoBomba
from app.models.user import Usuario
from app.schemas.infraestructura import (
    BombaCreate,
    BombaEstadoUpdate,
    BombaResponse,
    BombaUpdate,
)
from app.services.infra_service import InfraService

router = APIRouter()


@router.get(
    "/",
    response_model=List[BombaResponse],
    summary="Listar bombas / dispensarios",
    description="Permite consultar el catálogo de bombas activas, filtrando por isla, tanque asignado o estado operativo.",
)
def get_bombas(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    isla: Optional[int] = Query(None, gt=0, description="Filtrar por número de isla"),
    tanque_id: Optional[int] = Query(None, gt=0, description="Filtrar por ID de tanque"),
    estado: Optional[EstadoBomba] = Query(None, description="Filtrar por estado operativo"),
    solo_activas: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    bombas = InfraService.list_bombas(
        db,
        skip=skip,
        limit=limit,
        isla=isla,
        tanque_id=tanque_id,
        estado=estado,
        solo_activas=solo_activas,
    )
    return [InfraService.map_bomba_response(b) for b in bombas]


@router.get(
    "/{bomba_id}",
    response_model=BombaResponse,
    summary="Obtener detalle de una bomba",
)
def get_bomba_by_id(
    bomba_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    bomba = InfraService.get_bomba_by_id(db, bomba_id=bomba_id)
    return InfraService.map_bomba_response(bomba)


@router.post(
    "/",
    response_model=BombaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar nueva bomba / dispensario (ADMIN y SUPERVISOR)",
)
def create_bomba(
    bomba_in: BombaCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_supervisor_or_admin),
):
    bomba = InfraService.create_bomba(db, bomba_in=bomba_in)
    return InfraService.map_bomba_response(bomba)


@router.put(
    "/{bomba_id}",
    response_model=BombaResponse,
    summary="Actualizar bomba / dispensario (ADMIN y SUPERVISOR)",
)
def update_bomba(
    bomba_id: int,
    bomba_in: BombaUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_supervisor_or_admin),
):
    bomba = InfraService.update_bomba(db, bomba_id=bomba_id, bomba_in=bomba_in)
    return InfraService.map_bomba_response(bomba)


@router.patch(
    "/{bomba_id}/estado",
    response_model=BombaResponse,
    summary="Cambiar estado operativo de la bomba (ADMIN y SUPERVISOR)",
    description="Permite poner una bomba en ACTIVA, EN_MANTENIMIENTO o FUERA_DE_SERVICIO rápidamente.",
)
def update_estado_bomba(
    bomba_id: int,
    estado_in: BombaEstadoUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_supervisor_or_admin),
):
    bomba = InfraService.cambiar_estado(db, bomba_id=bomba_id, nuevo_estado=estado_in.estado)
    return InfraService.map_bomba_response(bomba)


@router.delete(
    "/{bomba_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar bomba / dispensario (Solo ADMIN)",
)
def delete_bomba(
    bomba_id: int,
    db: Session = Depends(get_db),
    current_admin: Usuario = Depends(require_admin),
):
    InfraService.delete_bomba(db, bomba_id=bomba_id)
    return None
