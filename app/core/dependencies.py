from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import RolEnum, Usuario

__all__ = [
    "get_db",
    "get_current_user",
    "require_role",
    "require_admin",
    "require_supervisor_or_admin",
]

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> Usuario:
    """Extrae el token JWT, valida su firma/expiración y recupera el usuario de la BD.

    El rol se toma de la BD (no del token), por lo que un cambio de rol o una
    desactivación surten efecto de inmediato aunque el token siga vigente.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales de autenticación inválidas o expiradas",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    user_email = payload.get("sub")
    if not user_email:
        raise credentials_exception

    user = db.query(Usuario).filter(Usuario.email == user_email).first()
    if user is None:
        raise credentials_exception

    if not user.esta_activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo en el sistema",
        )

    return user


def require_role(*allowed_roles: RolEnum):
    """Factory de dependencias para Autorización Basada en Roles (RBAC).

    Ejemplo de uso:
        current_user: Usuario = Depends(require_role(RolEnum.ADMIN, RolEnum.SUPERVISOR))
    """

    def role_checker(current_user: Usuario = Depends(get_current_user)) -> Usuario:
        if current_user.rol not in allowed_roles:
            role_names = ", ".join(r.value for r in allowed_roles)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permisos insuficientes. Se requiere rol: {role_names}. Rol actual: {current_user.rol.value}",
            )
        return current_user

    return role_checker


require_admin = require_role(RolEnum.ADMIN)
require_supervisor_or_admin = require_role(RolEnum.ADMIN, RolEnum.SUPERVISOR)
