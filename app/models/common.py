"""Tipos y utilidades compartidas por los modelos ORM."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Numeric


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Montos en MXN y volúmenes en litros con precisión decimal exacta en la BD (NUMERIC en PostgreSQL),
# evitando errores de redondeo de punto flotante en importes. asdecimal=False entrega float a Python
# para mantener la compatibilidad con los esquemas Pydantic y el JSON de la API.
Money = Numeric(12, 2, asdecimal=False)
Liters = Numeric(14, 2, asdecimal=False)

# Fechas siempre en UTC con zona horaria (TIMESTAMPTZ en PostgreSQL)
UTCDateTime = DateTime(timezone=True)
