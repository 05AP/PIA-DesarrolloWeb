from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.infraestructura import TipoCombustible
from app.models.operaciones import MetodoPagoEnum
from app.schemas.common import OptionalCleanStr, UTCDatetime


# ESQUEMAS PARA DESPACHO / VENTA
class VentaCreate(BaseModel):
    bomba_id: int = Field(..., gt=0, description="ID del dispensario/bomba donde se realiza el despacho")
    litros: float = Field(..., gt=0, description="Cantidad de litros a despachar (debe ser mayor a 0)")
    metodo_pago: MetodoPagoEnum = Field(default=MetodoPagoEnum.EFECTIVO, description="Método de pago (EFECTIVO, TARJETA, VALES)")
    placa_vehiculo: OptionalCleanStr = Field(None, max_length=20, description="Placa del vehículo atendido")
    cliente: OptionalCleanStr = Field(None, max_length=120, description="Nombre o razón social del cliente (opcional)")


class VentaResponse(BaseModel):
    id: int
    folio: str
    bomba_id: int
    tanque_id: int
    despachador_id: int
    despachador_nombre: Optional[str] = None
    tipo_combustible: TipoCombustible
    litros: float
    precio_unitario: float
    total: float
    metodo_pago: MetodoPagoEnum
    placa_vehiculo: Optional[str] = None
    cliente: Optional[str] = None
    odometro_inicial: float
    odometro_final: float
    created_at: UTCDatetime

    model_config = ConfigDict(from_attributes=True)


# ESQUEMAS PARA RECEPCIÓN DE PIPAS
class RecepcionPipaCreate(BaseModel):
    tanque_id: int = Field(..., gt=0, description="ID del tanque subterráneo de destino")
    folio_remision: str = Field(..., min_length=3, max_length=60, description="Número de remisión o factura del transportista")
    proveedor: str = Field(..., min_length=2, max_length=120, description="Nombre de la empresa distribuidora (ej: PEMEX, Mobil)")
    placa_pipa: OptionalCleanStr = Field(None, max_length=30, description="Placa del tractocamión o remolque")
    chofer: OptionalCleanStr = Field(None, max_length=120, description="Nombre del operador que entrega")
    litros_recibidos: float = Field(..., gt=0, description="Volumen neto de combustible descargado en litros")
    costo_compra_litro: float = Field(..., gt=0, description="Costo de adquisición por litro en MXN")
    notas: OptionalCleanStr = Field(None, max_length=255, description="Observaciones o bitácora de descarga")


class RecepcionPipaResponse(BaseModel):
    id: int
    folio_remision: str
    tanque_id: int
    tanque_numero: Optional[int] = None
    tanque_combustible: Optional[str] = None
    supervisor_id: int
    supervisor_nombre: Optional[str] = None
    proveedor: str
    placa_pipa: Optional[str] = None
    chofer: Optional[str] = None
    litros_recibidos: float
    costo_compra_litro: float
    costo_total: float
    nivel_previo_tanque: float
    nivel_posterior_tanque: float
    notas: Optional[str] = None
    created_at: UTCDatetime

    model_config = ConfigDict(from_attributes=True)


# ESQUEMAS PARA CORTE DE CAJA / ARQUEO
class DetalleMetodoPago(BaseModel):
    metodo: MetodoPagoEnum
    cantidad_transacciones: int
    monto_total: float


class DetalleCombustible(BaseModel):
    tipo_combustible: TipoCombustible
    litros_vendidos: float
    monto_total: float


class DetalleBombaCorte(BaseModel):
    bomba_id: int
    numero_bomba: int
    isla: int
    tipo_combustible: str
    odometro_actual: float
    litros_vendidos_periodo: float
    monto_vendido_periodo: float
    litros_por_odometro: float = Field(
        0.0, description="Avance real del odómetro de la bomba durante el periodo auditado"
    )
    litros_sin_registro: float = Field(
        0.0, description="Litros que avanzó el odómetro sin una venta registrada (faltante)"
    )


class CorteTurnoResponse(BaseModel):
    fecha_corte: UTCDatetime
    periodo_inicio: Optional[UTCDatetime] = None
    periodo_fin: Optional[UTCDatetime] = None
    total_transacciones: int
    litros_totales_vendidos: float
    ingresos_totales: float
    desglose_metodos_pago: List[DetalleMetodoPago]
    desglose_combustibles: List[DetalleCombustible]
    detalle_bombas: List[DetalleBombaCorte]
    cuadre_status: Literal["CUADRADO_EXACTO", "DISCREPANCIA_DETECTADA"]
    observaciones: str
