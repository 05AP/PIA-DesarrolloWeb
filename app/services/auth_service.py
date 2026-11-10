from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    fake_password_check,
    get_password_hash,
    verify_password,
)
from app.models.user import RolEnum, Usuario
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserUpdate


class AuthService:
    """Lógica de negocio de autenticación y administración de usuarios."""

    @staticmethod
    def get_by_email(db: Session, email: str) -> Optional[Usuario]:
        return db.query(Usuario).filter(Usuario.email == email.strip().lower()).first()

    @staticmethod
    def get_by_id(db: Session, user_id: int) -> Optional[Usuario]:
        return db.query(Usuario).filter(Usuario.id == user_id).first()

    @classmethod
    def get_by_id_or_404(cls, db: Session, user_id: int) -> Usuario:
        user = cls.get_by_id(db, user_id=user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuario con ID {user_id} no encontrado",
            )
        return user

    @classmethod
    def authenticate(cls, db: Session, email: str, password: str) -> Optional[Usuario]:
        user = cls.get_by_email(db, email=email)
        if not user:
            fake_password_check()  # Igualar tiempos de respuesta (anti-enumeración)
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    @classmethod
    def login(cls, db: Session, email: str, password: str) -> Token:
        """Valida credenciales y estado del usuario y emite el JWT."""
        user = cls.authenticate(db, email=email, password=password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales incorrectas (correo o contraseña errónea)",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.esta_activo:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cuenta de usuario inactiva. Contacte al administrador.",
            )

        token = create_access_token(subject=user.email, role=user.rol.value)
        return Token(
            access_token=token,
            token_type="bearer",
            rol=user.rol.value,
            nombre=user.nombre,
            email=user.email,
        )

    @classmethod
    def create_user(cls, db: Session, user_in: UserCreate) -> Usuario:
        if cls.get_by_email(db, email=user_in.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe un usuario registrado con el correo: {user_in.email}",
            )

        db_user = Usuario(
            nombre=user_in.nombre.strip(),
            email=user_in.email,
            hashed_password=get_password_hash(user_in.password),
            rol=user_in.rol,
            telefono=user_in.telefono,
            esta_activo=user_in.esta_activo,
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user

    @classmethod
    def update_user(cls, db: Session, user_id: int, user_in: UserUpdate, current_user: Usuario) -> Usuario:
        user = cls.get_by_id_or_404(db, user_id=user_id)

        # Un administrador no puede quitarse a sí mismo el acceso (evita bloquear el sistema)
        if user.id == current_user.id:
            if user_in.esta_activo is False:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No puede desactivar su propia cuenta.",
                )
            if user_in.rol is not None and user_in.rol != RolEnum.ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No puede retirarse a sí mismo el rol de administrador.",
                )

        if user_in.email and user_in.email != user.email:
            if cls.get_by_email(db, email=user_in.email):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"El correo {user_in.email} ya está en uso",
                )
            user.email = user_in.email

        if user_in.nombre is not None:
            user.nombre = user_in.nombre.strip()
        if user_in.rol is not None:
            user.rol = user_in.rol
        if user_in.telefono is not None:
            user.telefono = user_in.telefono
        if user_in.esta_activo is not None:
            user.esta_activo = user_in.esta_activo
        if user_in.password is not None:
            user.hashed_password = get_password_hash(user_in.password)

        db.commit()
        db.refresh(user)
        return user

    @classmethod
    def list_users(
        cls,
        db: Session,
        skip: int = 0,
        limit: int = 100,
        rol: Optional[RolEnum] = None,
        solo_activos: Optional[bool] = None,
    ) -> List[Usuario]:
        query = db.query(Usuario)
        if rol is not None:
            query = query.filter(Usuario.rol == rol)
        if solo_activos is not None:
            query = query.filter(Usuario.esta_activo == solo_activos)
        return query.order_by(Usuario.id.asc()).offset(skip).limit(limit).all()

    @classmethod
    def delete_user(cls, db: Session, user_id: int, current_user: Usuario) -> None:
        """Baja lógica (soft delete): conserva el historial de ventas y recepciones del usuario."""
        user = cls.get_by_id_or_404(db, user_id=user_id)
        if user.id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No puede desactivar su propia cuenta.",
            )
        user.esta_activo = False
        db.commit()
