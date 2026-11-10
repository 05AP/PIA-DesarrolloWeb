"""Tipos reutilizables para los esquemas Pydantic."""
from datetime import datetime, timezone
from typing import Annotated, Optional

from pydantic import AfterValidator, BeforeValidator


def _ensure_utc(value: datetime) -> datetime:
    """Marca como UTC las fechas sin zona horaria (SQLite no la conserva).

    Así el JSON siempre incluye el offset (+00:00) y el navegador puede convertir a hora local.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _strip_or_none(value: Optional[str]) -> Optional[str]:
    """Elimina espacios en los extremos; una cadena vacía se considera ausente."""
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


UTCDatetime = Annotated[datetime, AfterValidator(_ensure_utc)]
OptionalCleanStr = Annotated[Optional[str], BeforeValidator(_strip_or_none)]
