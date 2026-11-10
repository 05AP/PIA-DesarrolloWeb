from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.infraestructura import EstadoBomba, TipoCombustible
from app.schemas.common import OptionalCleanStr, UTCDatetime

UMBRAL_NIVEL_BAJO_PCT = 15.0  # Alarma cuando el tanque está por debajo de este porcentaje


# ESQUEMAS PARA TANQUES DE COMBUSTIBLE

class TanqueFields(BaseModel):
    """Campos comunes del tanque (sin reglas de validación de entrada)."""
    numero_tanque: int = Field(..., gt=0, description="Número identificador del tanque (ej: 1, 2, 3)")
    identificador: OptionalCleanStr = Field(None, max_length=50, description="Código de estación, ej: TK-01")
    tipo_combustible: TipoCombustible = Field(..., description="Tipo de combustible (MAGNA, PREMIUM, DIESEL)")
    capacidad_total: float = Field(..., gt=0, description="Capacidad total máxima del tanque en litros")
    nivel_actual: float = Field(0.0, ge=0, description="Nivel actual de litros en el tanque")
    costo_compra_litro: float = Field(..., gt=0, description="Costo de compra por litro en pesos mexicanos (MXN)")
    precio_venta_litro: float = Field(..., gt=0, description="Precio de venta vigente al público por litro")
    esta_activo: bool = Field(True, description="Indica si el tanque está operativo")


class TanqueCreate(TanqueFields):
    @model_validator(mode="after")
    def validate_tank_rules(self):
        if self.nivel_actual > self.capacidad_total:
            raise ValueError(
                f"El nivel actual ({self.nivel_actual} L) no puede superar la capacidad máxima ({self.capacidad_total} L)"
            )
        if self.precio_venta_litro < self.costo_compra_litro:
            raise ValueError(
                f"El precio de venta (${self.precio_venta_litro:.2f}) no puede ser inferior al costo de compra "
                f"(${self.costo_compra_litro:.2f})"
            )
        return self


# Alias conservado por compatibilidad
TanqueBase = TanqueCreate


class TanqueUpdate(BaseModel):
    identificador: OptionalCleanStr = Field(None, max_length=50)
    capacidad_total: Optional[float] = Field(None, gt=0)
    costo_compra_litro: Optional[float] = Field(None, gt=0)
    precio_venta_litro: Optional[float] = Field(None, gt=0)
    esta_activo: Optional[bool] = None


class TanqueInventarioUpdate(BaseModel):
    """Ajuste manual de inventario (merma, calibración o corrección). Queda registrado en bitácora."""
    litros_a_agregar: float = Field(
        ..., description="Litros a ajustar: positivo = entrada, negativo = merma / salida (distinto de 0)"
    )
    motivo: str = Field(..., min_length=3, max_length=255, description="Justificación del movimiento (ej: 'Calibración')")

    @model_validator(mode="after")
    def validate_non_zero(self):
        if self.litros_a_agregar == 0:
            raise ValueError("El ajuste debe ser distinto de 0 litros")
        self.motivo = self.motivo.strip()
        return self


class TanqueResponse(TanqueFields):
    """Respuesta: no re-aplica reglas de entrada, solo refleja el estado persistido."""
    id: int
    porcentaje_ocupacion: Optional[float] = None
    alerta_nivel_bajo: Optional[bool] = None
    created_at: UTCDatetime
    updated_at: UTCDatetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def compute_indicators(self):
        if self.capacidad_total and self.capacidad_total > 0:
            porcentaje = (self.nivel_actual / self.capacidad_total) * 100
            self.porcentaje_ocupacion = round(porcentaje, 2)
            self.alerta_nivel_bajo = porcentaje < UMBRAL_NIVEL_BAJO_PCT
        else:
            self.porcentaje_ocupacion = 0.0
            self.alerta_nivel_bajo = False
        return self


class AjusteInventarioResponse(BaseModel):
    id: int
    tanque_id: int
    usuario_id: int
    usuario_nombre: Optional[str] = None
    litros: float
    nivel_previo_tanque: float
    nivel_posterior_tanque: float
    motivo: str
    created_at: UTCDatetime

    model_config = ConfigDict(from_attributes=True)


# ESQUEMAS PARA DISPENSARIOS / BOMBAS

class BombaBase(BaseModel):
    numero_bomba: int = Field(..., gt=0, description="Número de bomba visible para los clientes (ej: 1, 2, 3)")
    isla: int = Field(..., gt=0, description="Número de isla física donde se ubica el dispensario")
    tanque_id: int = Field(..., gt=0, description="ID del tanque subterráneo asignado a este dispensario")
    estado: EstadoBomba = Field(default=EstadoBomba.ACTIVA, description="Estado operativo de la bomba")
    odometro_litros: float = Field(default=0.0, ge=0, description="Lectura acumulada de litros despachados")
    esta_activo: bool = Field(True, description="Indica si el dispensario está registrado como activo")


class BombaCreate(BombaBase):
    pass


class BombaUpdate(BaseModel):
    isla: Optional[int] = Field(None, gt=0)
    tanque_id: Optional[int] = Field(None, gt=0)
    estado: Optional[EstadoBomba] = None
    odometro_litros: Optional[float] = Field(None, ge=0)
    esta_activo: Optional[bool] = None


class BombaEstadoUpdate(BaseModel):
    estado: EstadoBomba = Field(..., description="Nuevo estado operativo de la bomba")


class BombaResponse(BombaBase):
    id: int
    created_at: UTCDatetime
    updated_at: UTCDatetime
    tanque_tipo_combustible: Optional[str] = None
    tanque_precio_litro: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)
