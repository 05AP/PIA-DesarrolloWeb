"""Importa Base y todos los modelos para que queden registrados en Base.metadata
antes de ejecutar create_all() o herramientas de migración."""
from app.db.session import Base
from app.models import (  # noqa: F401
    AjusteInventario,
    Dispensario,
    RecepcionPipa,
    TanqueCombustible,
    TransaccionVenta,
    Usuario,
)

__all__ = ["Base"]
