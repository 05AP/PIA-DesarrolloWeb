import enum

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.db.session import Base
from app.models.common import Liters, Money, UTCDateTime, utcnow


class TipoCombustible(str, enum.Enum):
    MAGNA = "MAGNA"
    PREMIUM = "PREMIUM"
    DIESEL = "DIESEL"


class EstadoBomba(str, enum.Enum):
    ACTIVA = "ACTIVA"
    EN_MANTENIMIENTO = "EN_MANTENIMIENTO"
    FUERA_DE_SERVICIO = "FUERA_DE_SERVICIO"


class TanqueCombustible(Base):
    __tablename__ = "tanques_combustible"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    numero_tanque = Column(Integer, unique=True, index=True, nullable=False)
    identificador = Column(String(50), nullable=True)  # Ej: TK-01
    tipo_combustible = Column(SQLEnum(TipoCombustible), nullable=False)
    capacidad_total = Column(Liters, nullable=False)  # Litros (ej: 40000.00)
    nivel_actual = Column(Liters, nullable=False, default=0.0)  # Litros disponibles
    costo_compra_litro = Column(Money, nullable=False)  # MXN/L
    precio_venta_litro = Column(Money, nullable=False)  # MXN/L
    esta_activo = Column(Boolean, default=True, nullable=False)
    created_at = Column(UTCDateTime, default=utcnow, nullable=False)
    updated_at = Column(UTCDateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Sin cascada de borrado: un tanque con bombas conectadas no puede eliminarse (FK RESTRICT)
    bombas = relationship("Dispensario", back_populates="tanque")

    def __repr__(self):
        return f"<Tanque #{self.numero_tanque} ({self.tipo_combustible}): {self.nivel_actual}/{self.capacidad_total} L>"


class Dispensario(Base):
    __tablename__ = "dispensarios"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    numero_bomba = Column(Integer, unique=True, index=True, nullable=False)  # Número de bomba visible
    isla = Column(Integer, nullable=False, index=True)  # Número de isla en la estación
    tanque_id = Column(Integer, ForeignKey("tanques_combustible.id", ondelete="RESTRICT"), nullable=False)
    estado = Column(SQLEnum(EstadoBomba), default=EstadoBomba.ACTIVA, nullable=False)
    odometro_litros = Column(Liters, default=0.0, nullable=False)  # Litros acumulados despachados
    esta_activo = Column(Boolean, default=True, nullable=False)
    created_at = Column(UTCDateTime, default=utcnow, nullable=False)
    updated_at = Column(UTCDateTime, default=utcnow, onupdate=utcnow, nullable=False)

    tanque = relationship("TanqueCombustible", back_populates="bombas")

    def __repr__(self):
        return f"<Bomba #{self.numero_bomba} Isla {self.isla} Estado={self.estado}>"
