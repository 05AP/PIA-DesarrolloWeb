"""Script de Población de Datos Iniciales (Seed Data)
Gasolinera API - Aseguramiento de Calidad y Pruebas
Permite restablecer o sembrar usuarios por rol, tanques prellenados y bombas con transacciones demo.
"""
import logging
import sys

from app.db.init_db import init_db
from app.db.session import Base, SessionLocal, engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("seed_data")


def run_seed(clean: bool = False):
    """Puebla los datos iniciales. Si clean=True, recrea las tablas desde cero."""
    if clean:
        logger.warning("Eliminando tablas existentes para repoblación limpia...")
        Base.metadata.drop_all(bind=engine)

    logger.info("Verificando estructura de tablas...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        logger.info("Iniciando siembra de datos...")
        init_db(db)
        logger.info("=" * 60)
        logger.info("¡Siembra de datos iniciales completada con éxito!")
        logger.info("USUARIOS DISPONIBLES PARA PRUEBAS:")
        logger.info("  1. ADMIN:       admin@gasolinera.com       | Contraseña: admin123")
        logger.info("  2. SUPERVISOR:  supervisor@gasolinera.com  | Contraseña: supervisor123")
        logger.info("  3. DESPACHADOR: despachador@gasolinera.com | Contraseña: despachador123")
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"Error durante la siembra de datos: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    limpiar = "--clean" in sys.argv or "-c" in sys.argv
    run_seed(clean=limpiar)
