from typing import Annotated, Optional

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)

from app.core.security import BCRYPT_MAX_BYTES
from app.models.user import RolEnum
from app.schemas.common import OptionalCleanStr, UTCDatetime


def _validate_password_bytes(value: str) -> str:
    if len(value.encode("utf-8")) > BCRYPT_MAX_BYTES:
        raise ValueError(f"La contraseña no puede exceder {BCRYPT_MAX_BYTES} bytes")
    return value


PasswordStr = Annotated[str, AfterValidator(_validate_password_bytes)]


class UserBase(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=120, description="Nombre completo del usuario")
    email: EmailStr = Field(..., description="Correo electrónico único")
    rol: RolEnum = Field(default=RolEnum.DESPACHADOR, description="Rol del usuario (ADMIN, SUPERVISOR, DESPACHADOR)")
    telefono: OptionalCleanStr = Field(None, max_length=20, description="Teléfono de contacto")
    esta_activo: bool = Field(True, description="Estado de activación del usuario")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class UserCreate(UserBase):
    password: PasswordStr = Field(..., min_length=6, max_length=72, description="Contraseña en texto plano (6-72 caracteres)")


class UserUpdate(BaseModel):
    nombre: Optional[str] = Field(None, min_length=2, max_length=120)
    email: Optional[EmailStr] = None
    rol: Optional[RolEnum] = None
    telefono: OptionalCleanStr = Field(None, max_length=20)
    esta_activo: Optional[bool] = None
    password: Optional[PasswordStr] = Field(None, min_length=6, max_length=72)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: Optional[str]) -> Optional[str]:
        return v.strip().lower() if v else v


class UserResponse(BaseModel):
    id: int
    nombre: str
    email: str
    rol: RolEnum
    telefono: Optional[str] = None
    esta_activo: bool
    created_at: UTCDatetime
    updated_at: UTCDatetime

    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)
