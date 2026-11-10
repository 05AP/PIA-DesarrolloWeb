from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import (
    get_current_user,
    get_db,
    require_admin,
    require_supervisor_or_admin,
)
from app.models.infraestructura import TipoCombustible
from app.models.user import Usuario
from app.schemas.infraestructura import (
    AjusteInventarioResponse,
    TanqueCreate,
    TanqueInventarioUpdate,
    TanqueResponse,
    TanqueUpdate,
)
from app.services.infra_service import InfraService

router = APIRouter()


@router.get(
    "/",
    response_model=List[TanqueResponse],
    summary="Listar tanques subterráneos",
    description="Permite a cualquier usuario autenticado (Despachador, Supervisor, Admin) consultar el catálogo y niveles de combustible.",
)
def get_tanques(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    tipo_combustible: Optional[TipoCombustible] = None,
    solo_activos: Optional[bool] = None,
    db: Session = Depends(get_db),
    _user: Usuario = Depends(get_current_user),
):
    tanques = InfraService.list_tanques(
        db, skip=skip, limit=limit, tipo_combustible=tipo_combustible, solo_activos=solo_activos
    )
    return [TanqueResponse.model_validate(t) for t in tanques]


@router.get(
    "/{tanque_id}",
    response_model=TanqueResponse,
    summary="Obtener detalle de un tanque subterráneo",
)
def get_tanque_by_id(
    tanque_id: int,
    db: Session = Depends(get_db),
    _user: Usuario = Depends(get_current_user),
):
    return TanqueResponse.model_validate(InfraService.get_tanque_by_id(db, tanque_id=tanque_id))


@router.post(
    "/",
    response_model=TanqueResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar nuevo tanque subterráneo (ADMIN y SUPERVISOR)",
)
def create_tanque(
    tanque_in: TanqueCreate,
    db: Session = Depends(get_db),
    _user: Usuario = Depends(require_supervisor_or_admin),
):
    return TanqueResponse.model_validate(InfraService.create_tanque(db, tanque_in=tanque_in))


@router.put(
    "/{tanque_id}",
    response_model=TanqueResponse,
    summary="Actualizar parámetros del tanque (ADMIN y SUPERVISOR)",
)
def update_tanque(
    tanque_id: int,
    tanque_in: TanqueUpdate,
    db: Session = Depends(get_db),
    _user: Usuario = Depends(require_supervisor_or_admin),
):
    return TanqueResponse.model_validate(InfraService.update_tanque(db, tanque_id=tanque_id, tanque_in=tanque_in))


@router.post(
    "/{tanque_id}/reabastecer",
    response_model=TanqueResponse,
    summary="Ajuste manual de inventario (ADMIN y SUPERVISOR)",
    description=(
        "Registra un ajuste físico de inventario (merma, calibración o corrección). Litros positivos suman y "
        "negativos restan. Cada ajuste queda en bitácora de auditoría con usuario y motivo. "
        "Para entradas de combustible por proveedor use `/operaciones/suministro/recepcion-pipa`."
    ),
)
def reabastecer_tanque(
    tanque_id: int,
    reabastecimiento: TanqueInventarioUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_supervisor_or_admin),
):
    tanque = InfraService.ajustar_inventario(
        db,
        tanque_id=tanque_id,
        litros=reabastecimiento.litros_a_agregar,
        motivo=reabastecimiento.motivo,
        usuario=current_user,
    )
    return TanqueResponse.model_validate(tanque)


@router.get(
    "/{tanque_id}/ajustes",
    response_model=List[AjusteInventarioResponse],
    summary="Bitácora de ajustes de inventario del tanque (ADMIN y SUPERVISOR)",
)
def listar_ajustes_tanque(
    tanque_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: Usuario = Depends(require_supervisor_or_admin),
):
    InfraService.get_tanque_by_id(db, tanque_id=tanque_id)  # 404 si no existe
    ajustes = InfraService.listar_ajustes(db, tanque_id=tanque_id, skip=skip, limit=limit)
    return [InfraService.map_ajuste_response(a) for a in ajustes]


@router.delete(
    "/{tanque_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar tanque subterráneo (Solo ADMIN)",
    description="Solo se permite si no tiene bombas conectadas ni historial; de lo contrario responde 409 (desactívelo).",
)
def delete_tanque(
    tanque_id: int,
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(require_admin),
):
    InfraService.delete_tanque(db, tanque_id=tanque_id)
