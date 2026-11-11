from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import settings

db_url = settings.DATABASE_URL

is_sqlite = db_url.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}

engine = create_engine(
    db_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=settings.DEBUG,
)

if is_sqlite:
    @event.listens_for(engine, "connect")
    def _configure_sqlite_connection(dbapi_connection, _connection_record):
        """Ajustes para que SQLite se comporte como PostgreSQL en desarrollo y pruebas.

        - Activa las llaves foráneas (SQLite no las aplica por defecto).
        - Desactiva el manejo implícito de transacciones de pysqlite para que SQLAlchemy emita
          BEGIN explícito; así los SAVEPOINT y el rollback funcionan correctamente.
        """
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
        dbapi_connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def _sqlite_explicit_begin(conn):
        conn.exec_driver_sql("BEGIN")


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Generador de sesiones de base de datos con manejo automático de cierre."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
