import enum

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.db.session import Base
from app.models.common import Liters, Money, UTCDateTime, utcnow
from app.models.infraestructura import TipoCombustible


class MetodoPagoEnum(str, enum.Enum):
    EFECTIVO = "EFECTIVO"
    TARJETA = "TARJETA"
    VALES = "VALES"


class TransaccionVenta(Base):
    """Modelo ORM para registrar una venta / despacho de combustible en bomba."""
    __tablename__ = "transacciones_ventas"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    folio = Column(String(60), unique=True, index=True, nullable=False)
    bomba_id = Column(Integer, ForeignKey("dispensarios.id", ondelete="RESTRICT"), nullable=False, index=True)
    tanque_id = Column(Integer, ForeignKey("tanques_combustible.id", ondelete="RESTRICT"), nullable=False)
    despachador_id = Column(Integer, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False, index=True)

    tipo_combustible = Column(SQLEnum(TipoCombustible), nullable=False)
    litros = Column(Liters, nullable=False)
    precio_unitario = Column(Money, nullable=False)  # Precio por litro aplicado al momento de la venta
    total = Column(Money, nullable=False)  # litros * precio_unitario
    metodo_pago = Column(SQLEnum(MetodoPagoEnum), nullable=False, default=MetodoPagoEnum.EFECTIVO)

    placa_vehiculo = Column(String(20), nullable=True)
    cliente = Column(String(120), nullable=True)

    odometro_inicial = Column(Liters, nullable=False)
    odometro_final = Column(Liters, nullable=False)

    created_at = Column(UTCDateTime, default=utcnow, nullable=False, index=True)

    bomba = relationship("Dispensario")
    tanque = relationship("TanqueCombustible")
    despachador = relationship("Usuario")

    def __repr__(self):
        return f"<Venta folio={self.folio} bomba={self.bomba_id} litros={self.litros} total=${self.total}>"


class RecepcionPipa(Base):
    """Modelo ORM para registrar la recepción y descarga de hidrocarburos desde pipas transportistas."""
    __tablename__ = "recepciones_pipas"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    folio_remision = Column(String(60), unique=True, index=True, nullable=False)
    tanque_id = Column(Integer, ForeignKey("tanques_combustible.id", ondelete="RESTRICT"), nullable=False, index=True)
    supervisor_id = Column(Integer, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False)

    proveedor = Column(String(120), nullable=False)  # Ej: PEMEX Transformación Industrial
    placa_pipa = Column(String(30), nullable=True)
    chofer = Column(String(120), nullable=True)

    litros_recibidos = Column(Liters, nullable=False)
    costo_compra_litro = Column(Money, nullable=False)
    costo_total = Column(Money, nullable=False)

    nivel_previo_tanque = Column(Liters, nullable=False)
    nivel_posterior_tanque = Column(Liters, nullable=False)
    notas = Column(String(255), nullable=True)

    created_at = Column(UTCDateTime, default=utcnow, nullable=False, index=True)

    tanque = relationship("TanqueCombustible")
    supervisor = relationship("Usuario")

    def __repr__(self):
        return f"<RecepcionPipa remision={self.folio_remision} tanque={self.tanque_id} litros={self.litros_recibidos}>"


class AjusteInventario(Base):
    """Bitácora de auditoría de ajustes manuales de inventario (mermas, calibraciones, correcciones)."""
    __tablename__ = "ajustes_inventario"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tanque_id = Column(Integer, ForeignKey("tanques_combustible.id", ondelete="RESTRICT"), nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False)

    litros = Column(Liters, nullable=False)  # Positivo = entrada, negativo = merma / salida
    nivel_previo_tanque = Column(Liters, nullable=False)
    nivel_posterior_tanque = Column(Liters, nullable=False)
    motivo = Column(String(255), nullable=False)

    created_at = Column(UTCDateTime, default=utcnow, nullable=False, index=True)

    tanque = relationship("TanqueCombustible")
    usuario = relationship("Usuario")

    def __repr__(self):
        return f"<AjusteInventario tanque={self.tanque_id} litros={self.litros} motivo={self.motivo!r}>"
