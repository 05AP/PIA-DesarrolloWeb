import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.base import Base  # Registra todos los modelos en Base.metadata
from app.db.session import SessionLocal, engine
from app.models.infraestructura import (
    Dispensario,
    EstadoBomba,
    TanqueCombustible,
    TipoCombustible,
)
from app.models.operaciones import MetodoPagoEnum, RecepcionPipa, TransaccionVenta
from app.models.user import RolEnum, Usuario

logger = logging.getLogger(__name__)

SUPERVISOR_DEMO_EMAIL = "supervisor@gasolinera.com"
DESPACHADOR_DEMO_EMAIL = "despachador@gasolinera.com"


def _ensure_user(db: Session, *, email: str, nombre: str, password: str, rol: RolEnum, telefono: str) -> None:
    if db.query(Usuario).filter(Usuario.email == email).first():
        return
    db.add(
        Usuario(
            nombre=nombre,
            email=email,
            hashed_password=get_password_hash(password),
            rol=rol,
            telefono=telefono,
            esta_activo=True,
        )
    )
    logger.info("Usuario %s creado: %s", rol.value, email)  # Nunca se registra la contraseña


def init_db(db: Session) -> None:
    """Crea las tablas y siembra los datos iniciales (idempotente: no duplica registros)."""
    Base.metadata.create_all(bind=engine)

    _ensure_user(
        db,
        email=str(settings.FIRST_SUPERUSER_EMAIL).lower(),
        nombre=settings.FIRST_SUPERUSER_NAME,
        password=settings.FIRST_SUPERUSER_PASSWORD,
        rol=RolEnum.ADMIN,
        telefono="8110001122",
    )
    db.commit()

    if not settings.SEED_DEMO_DATA:
        logger.info("Inicialización completada (sin datos demo).")
        return

    _seed_demo_data(db)
    logger.info("Inicialización de la base de datos completada.")


def _seed_demo_data(db: Session) -> None:
    _ensure_user(
        db,
        email=SUPERVISOR_DEMO_EMAIL,
        nombre="Carlos Mendoza (Supervisor)",
        password="supervisor123",
        rol=RolEnum.SUPERVISOR,
        telefono="8115553344",
    )
    _ensure_user(
        db,
        email=DESPACHADOR_DEMO_EMAIL,
        nombre="Juan Pérez (Despachador Turno Matutino)",
        password="despachador123",
        rol=RolEnum.DESPACHADOR,
        telefono="8119998877",
    )
    db.commit()

    tanques_data = [
        {
            "numero_tanque": 1,
            "identificador": "TK-01-MAGNA",
            "tipo_combustible": TipoCombustible.MAGNA,
            "capacidad_total": 40000.0,
            "nivel_actual": 28500.0,
            "costo_compra_litro": 20.80,
            "precio_venta_litro": 23.99,
        },
        {
            "numero_tanque": 2,
            "identificador": "TK-02-PREMIUM",
            "tipo_combustible": TipoCombustible.PREMIUM,
            "capacidad_total": 30000.0,
            "nivel_actual": 19200.0,
            "costo_compra_litro": 22.40,
            "precio_venta_litro": 25.89,
        },
        {
            "numero_tanque": 3,
            "identificador": "TK-03-DIESEL",
            "tipo_combustible": TipoCombustible.DIESEL,
            "capacidad_total": 50000.0,
            "nivel_actual": 35000.0,
            "costo_compra_litro": 22.10,
            "precio_venta_litro": 25.49,
        },
    ]
    for t_data in tanques_data:
        if not db.query(TanqueCombustible).filter(TanqueCombustible.numero_tanque == t_data["numero_tanque"]).first():
            db.add(TanqueCombustible(**t_data))
            logger.info("Tanque sembrado: #%s (%s)", t_data["numero_tanque"], t_data["tipo_combustible"].value)
    db.commit()

    tanques = {t.numero_tanque: t for t in db.query(TanqueCombustible).filter(TanqueCombustible.numero_tanque.in_([1, 2, 3]))}
    if len(tanques) < 3:
        logger.warning("No se encontraron los tanques demo 1-3; se omite la siembra de bombas.")
        return

    bombas_data = [
        {"numero_bomba": 1, "isla": 1, "tanque_id": tanques[1].id, "odometro_litros": 125400.5},
        {"numero_bomba": 2, "isla": 1, "tanque_id": tanques[2].id, "odometro_litros": 89210.0},
        {"numero_bomba": 3, "isla": 2, "tanque_id": tanques[1].id, "odometro_litros": 104320.2},
        {"numero_bomba": 4, "isla": 2, "tanque_id": tanques[3].id, "odometro_litros": 240180.8},
    ]
    for b_data in bombas_data:
        if not db.query(Dispensario).filter(Dispensario.numero_bomba == b_data["numero_bomba"]).first():
            db.add(Dispensario(estado=EstadoBomba.ACTIVA, **b_data))
            logger.info("Bomba sembrada: #%s Isla %s", b_data["numero_bomba"], b_data["isla"])
    db.commit()

    if db.query(TransaccionVenta).count() > 0:
        return

    b1 = db.query(Dispensario).filter(Dispensario.numero_bomba == 1).first()
    b2 = db.query(Dispensario).filter(Dispensario.numero_bomba == 2).first()
    u_desp = db.query(Usuario).filter(Usuario.email == DESPACHADOR_DEMO_EMAIL).first()
    u_sup = db.query(Usuario).filter(Usuario.email == SUPERVISOR_DEMO_EMAIL).first()
    if not (b1 and b2 and u_desp and u_sup):
        return

    # Ventas demo coherentes con los odómetros actuales (para que el corte cuadre)
    db.add_all(
        [
            TransaccionVenta(
                folio="VTA-DEMO-0001",
                bomba_id=b1.id,
                tanque_id=b1.tanque_id,
                despachador_id=u_desp.id,
                tipo_combustible=TipoCombustible.MAGNA,
                litros=40.0,
                precio_unitario=23.99,
                total=959.60,
                metodo_pago=MetodoPagoEnum.EFECTIVO,
                placa_vehiculo="XYZ-1234",
                cliente="Cliente Mostrador",
                odometro_inicial=round(b1.odometro_litros - 40.0, 2),
                odometro_final=b1.odometro_litros,
            ),
            TransaccionVenta(
                folio="VTA-DEMO-0002",
                bomba_id=b2.id,
                tanque_id=b2.tanque_id,
                despachador_id=u_desp.id,
                tipo_combustible=TipoCombustible.PREMIUM,
                litros=25.0,
                precio_unitario=25.89,
                total=647.25,
                metodo_pago=MetodoPagoEnum.TARJETA,
                placa_vehiculo="ABC-5678",
                cliente="Flotilla Logística del Norte",
                odometro_inicial=round(b2.odometro_litros - 25.0, 2),
                odometro_final=b2.odometro_litros,
            ),
            RecepcionPipa(
                folio_remision="REM-PEMEX-88210",
                tanque_id=tanques[1].id,
                supervisor_id=u_sup.id,
                proveedor="PEMEX Logística y Distribución",
                placa_pipa="89-AB-2T",
                chofer="Esteban Morales",
                litros_recibidos=15000.0,
                costo_compra_litro=20.80,
                costo_total=312000.0,
                nivel_previo_tanque=13500.0,
                nivel_posterior_tanque=28500.0,
                notas="Descarga completada sin anomalías de presión o temperatura.",
            ),
        ]
    )
    db.commit()
    logger.info("Transacciones de demostración sembradas.")


if __name__ == "__main__":
    session = SessionLocal()
    try:
        init_db(session)
    finally:
        session.close()
