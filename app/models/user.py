import enum

from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy import Enum as SQLEnum

from app.db.session import Base
from app.models.common import UTCDateTime, utcnow


class RolEnum(str, enum.Enum):
    ADMIN = "ADMIN"
    SUPERVISOR = "SUPERVISOR"
    DESPACHADOR = "DESPACHADOR"


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nombre = Column(String(120), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    rol = Column(SQLEnum(RolEnum), nullable=False, default=RolEnum.DESPACHADOR)
    telefono = Column(String(20), nullable=True)
    esta_activo = Column(Boolean, default=True, nullable=False)
    created_at = Column(UTCDateTime, default=utcnow, nullable=False)
    updated_at = Column(UTCDateTime, default=utcnow, onupdate=utcnow, nullable=False)

    def __repr__(self):
        return f"<Usuario id={self.id} email={self.email} rol={self.rol}>"
