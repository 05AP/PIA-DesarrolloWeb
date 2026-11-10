from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import (
    get_current_user,
    get_db,
    require_supervisor_or_admin,
)
from app.models.infraestructura import TipoCombustible
from app.models.operaciones import MetodoPagoEnum
from app.models.user import Usuario
from app.schemas.operaciones import (
    CorteTurnoResponse,
    RecepcionPipaCreate,
    RecepcionPipaResponse,
    VentaCreate,
    VentaResponse,
)
from app.services.operaciones_service import OperacionesService

router = APIRouter()


# ENDPOINTS DE DESPACHO / VENTA (PROCESO CENTRAL)

@router.post(
    "/ventas/despacho",
    response_model=VentaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar despacho / venta de combustible (Proceso Central ACID)",
    description=r"""
**Proceso Transaccional Central del Negocio**:
1. Valida que la bomba seleccionada esté en estado **ACTIVA**.
2. Valida que el tanque subterráneo tenga volumen suficiente de combustible (**409 Conflict** en caso de inventario insuficiente).
3. Calcula el importe total ($litros \times precio\_por\_litro$).
4. Descuenta atómicamente el inventario del tanque de almacenamiento.
5. Actualiza e incrementa el odómetro acumulado de la bomba.
6. Registra la transacción con folio único y datos de auditoría.
    """,
)
def registrar_despacho(
    venta_in: VentaCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    nueva_venta = OperacionesService.registrar_despacho(
        db=db,
        venta_in=venta_in,
        despachador=current_user,
    )
    return OperacionesService.map_venta_response(nueva_venta)


@router.get(
    "/ventas",
    response_model=List[VentaResponse],
    summary="Listar transacciones de venta",
    description="Permite consultar el historial de despachos con filtros por bomba, combustible, método de pago y despachador.",
)
def listar_ventas(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    bomba_id: Optional[int] = Query(None, gt=0, description="Filtrar por ID de bomba"),
    tipo_combustible: Optional[TipoCombustible] = Query(None, description="Filtrar por tipo de combustible"),
    metodo_pago: Optional[MetodoPagoEnum] = Query(None, description="Filtrar por método de pago"),
    despachador_id: Optional[int] = Query(None, gt=0, description="Filtrar por ID de despachador"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    ventas = OperacionesService.listar_ventas(
        db=db,
        skip=skip,
        limit=limit,
        bomba_id=bomba_id,
        tipo_combustible=tipo_combustible,
        metodo_pago=metodo_pago,
        despachador_id=despachador_id,
    )
    return [OperacionesService.map_venta_response(v) for v in ventas]


@router.get(
    "/ventas/{venta_id}",
    response_model=VentaResponse,
    summary="Consultar detalle de una venta por ID",
)
def obtener_venta_por_id(
    venta_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    venta = OperacionesService.obtener_venta_por_id(db=db, venta_id=venta_id)
    return OperacionesService.map_venta_response(venta)


# ENDPOINTS DE SUMINISTRO (RECEPCIÓN DE PIPAS)

@router.post(
    "/suministro/recepcion-pipa",
    response_model=RecepcionPipaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar recepción y descarga de pipa (SUPERVISOR y ADMIN)",
    description="""
**Módulo de Suministro de Combustible**:
- Valida que el folio de remisión sea único.
- **Validación crítica anti-derrame**: El volumen actual del tanque más los litros de la pipa no pueden superar la capacidad máxima del tanque (**400 Bad Request por sobrecupo**).
- Actualiza atómicamente el inventario disponible y el costo de adquisición por litro en el catálogo.
    """,
)
def registrar_recepcion_pipa(
    recepcion_in: RecepcionPipaCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_supervisor_or_admin),
):
    nueva_recepcion = OperacionesService.registrar_recepcion_pipa(
        db=db,
        recepcion_in=recepcion_in,
        supervisor=current_user,
    )
    return OperacionesService.map_recepcion_response(nueva_recepcion)


@router.get(
    "/suministro/recepciones",
    response_model=List[RecepcionPipaResponse],
    summary="Listar historial de recepciones de pipas (SUPERVISOR y ADMIN)",
)
def listar_recepciones_pipas(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    tanque_id: Optional[int] = Query(None, gt=0, description="Filtrar por ID de tanque"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_supervisor_or_admin),
):
    recepciones = OperacionesService.listar_recepciones_pipas(
        db=db,
        skip=skip,
        limit=limit,
        tanque_id=tanque_id,
    )
    return [OperacionesService.map_recepcion_response(r) for r in recepciones]


# ENDPOINTS DE ARQUEO Y CORTE DE TURNO

@router.get(
    "/corte",
    response_model=CorteTurnoResponse,
    summary="Generar arqueo y corte de caja / turno (SUPERVISOR y ADMIN)",
    description="""
**Reporte de Cuadre y Arqueo Operativo**:
- Total de transacciones, litros vendidos e ingresos recaudados.
- Desglose por método de pago (**Efectivo, Tarjeta, Vales**).
- Desglose volumétrico e importes por tipo de combustible (**Magna, Premium, Diésel**).
- Auditoría por bomba comparando avance de odómetros vs transacciones registradas.
- Diagnóstico automático del estado del cuadre (**CUADRADO_EXACTO** o **DISCREPANCIA_DETECTADA**).
    """,
)
def generar_corte_turno(
    fecha_inicio: Optional[datetime] = Query(None, description="Inicio del período de corte (ISO 8601)"),
    fecha_fin: Optional[datetime] = Query(None, description="Fin del período de corte (ISO 8601)"),
    despachador_id: Optional[int] = Query(None, gt=0, description="Filtrar arqueo para un despachador específico"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_supervisor_or_admin),
):
    return OperacionesService.generar_corte_turno(
        db=db,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        despachador_id=despachador_id,
    )
