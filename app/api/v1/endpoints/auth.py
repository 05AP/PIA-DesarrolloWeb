from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db, require_admin
from app.models.user import Usuario
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserLogin, UserResponse
from app.services.auth_service import AuthService

router = APIRouter()


@router.post(
    "/login",
    response_model=Token,
    summary="Iniciar sesión (Form-Data compatible con Swagger UI)",
    description="Autentica a un usuario mediante email (campo username) y password. Devuelve el JWT Token con el rol RBAC.",
)
def login_for_access_token(
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    return AuthService.login(db, email=form_data.username, password=form_data.password)


@router.post(
    "/login/json",
    response_model=Token,
    summary="Iniciar sesión (JSON Body para Postman / Frontend)",
    description="Permite login enviando JSON {'email': '...', 'password': '...'}.",
)
def login_json(
    credentials: UserLogin,
    db: Session = Depends(get_db),
):
    return AuthService.login(db, email=credentials.email, password=credentials.password)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Perfil del usuario autenticado",
    description="Retorna la información del usuario correspondiente al token JWT provisto.",
)
def read_current_user(current_user: Usuario = Depends(get_current_user)):
    return current_user


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar nuevo usuario (Solo ADMIN)",
    description="Permite dar de alta a un nuevo despachador, supervisor o administrador.",
)
def register_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(require_admin),
):
    return AuthService.create_user(db, user_in=user_in)
