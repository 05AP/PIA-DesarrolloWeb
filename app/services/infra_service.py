import logging
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.infraestructura import (
    Dispensario,
    EstadoBomba,
    TanqueCombustible,
    TipoCombustible,
)
from app.models.operaciones import AjusteInventario, RecepcionPipa, TransaccionVenta
from app.models.user import Usuario
from app.schemas.infraestructura import (
    AjusteInventarioResponse,
    BombaCreate,
    BombaResponse,
    BombaUpdate,
    TanqueCreate,
    TanqueUpdate,
)

logger = logging.getLogger(__name__)


class InfraService:
    """Servicio de lógica de negocio para Infraestructura: Tanques subterráneos y Dispensarios/Bombas"""

    # LÓGICA DE TANQUES
    @staticmethod
    def get_tanque_by_id(db: Session, tanque_id: int, for_update: bool = False) -> TanqueCombustible:
        query = db.query(TanqueCombustible).filter(TanqueCombustible.id == tanque_id)
        if for_update:
            query = query.with_for_update()  # Bloqueo de fila (PostgreSQL) para evitar condiciones de carrera
        tanque = query.first()
        if not tanque:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tanque con ID {tanque_id} no existe",
            )
        return tanque

    @staticmethod
    def get_tanque_by_numero(db: Session, numero_tanque: int) -> Optional[TanqueCombustible]:
        return db.query(TanqueCombustible).filter(TanqueCombustible.numero_tanque == numero_tanque).first()

    @classmethod
    def create_tanque(cls, db: Session, tanque_in: TanqueCreate) -> TanqueCombustible:
        if cls.get_tanque_by_numero(db, numero_tanque=tanque_in.numero_tanque):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe un tanque registrado con el número {tanque_in.numero_tanque}",
            )

        db_tanque = TanqueCombustible(**tanque_in.model_dump())
        db.add(db_tanque)
        db.commit()
        db.refresh(db_tanque)
        return db_tanque

    @classmethod
    def list_tanques(
        cls,
        db: Session,
        skip: int = 0,
        limit: int = 100,
        tipo_combustible: Optional[TipoCombustible] = None,
        solo_activos: Optional[bool] = None,
    ) -> List[TanqueCombustible]:
        query = db.query(TanqueCombustible)
        if tipo_combustible:
            query = query.filter(TanqueCombustible.tipo_combustible == tipo_combustible)
        if solo_activos is not None:
            query = query.filter(TanqueCombustible.esta_activo == solo_activos)
        return query.order_by(TanqueCombustible.numero_tanque.asc()).offset(skip).limit(limit).all()

    @classmethod
    def update_tanque(cls, db: Session, tanque_id: int, tanque_in: TanqueUpdate) -> TanqueCombustible:
        tanque = cls.get_tanque_by_id(db, tanque_id=tanque_id)

        nueva_capacidad = tanque_in.capacidad_total if tanque_in.capacidad_total is not None else tanque.capacidad_total
        nuevo_costo = tanque_in.costo_compra_litro if tanque_in.costo_compra_litro is not None else tanque.costo_compra_litro
        nuevo_precio = tanque_in.precio_venta_litro if tanque_in.precio_venta_litro is not None else tanque.precio_venta_litro

        # Validar todas las reglas antes de modificar el objeto (no dejar estado parcial en la sesión)
        if tanque.nivel_actual > nueva_capacidad:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"La nueva capacidad ({nueva_capacidad} L) es menor que el nivel actual ({tanque.nivel_actual} L)",
            )
        if nuevo_precio < nuevo_costo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El precio de venta (${nuevo_precio:.2f}) no puede ser menor al costo de compra (${nuevo_costo:.2f})",
            )

        tanque.capacidad_total = nueva_capacidad
        tanque.costo_compra_litro = nuevo_costo
        tanque.precio_venta_litro = nuevo_precio
        if tanque_in.identificador is not None:
            tanque.identificador = tanque_in.identificador
        if tanque_in.esta_activo is not None:
            tanque.esta_activo = tanque_in.esta_activo

        db.commit()
        db.refresh(tanque)
        return tanque

    @classmethod
    def ajustar_inventario(
        cls,
        db: Session,
        tanque_id: int,
        litros: float,
        motivo: str,
        usuario: Usuario,
    ) -> TanqueCombustible:
        """Ajuste manual de inventario (merma, calibración, corrección) con registro de auditoría."""
        try:
            tanque = cls.get_tanque_by_id(db, tanque_id=tanque_id, for_update=True)
            if not tanque.esta_activo:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No se puede ajustar el inventario de un tanque inactivo",
                )

            nivel_previo = tanque.nivel_actual
            nuevo_nivel = round(nivel_previo + litros, 2)
            if nuevo_nivel < 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Operación inválida: el nivel resultaría negativo ({nuevo_nivel} L)",
                )
            if nuevo_nivel > tanque.capacidad_total:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Derrame potencial: el nuevo nivel ({nuevo_nivel} L) supera la capacidad máxima "
                        f"({tanque.capacidad_total} L)"
                    ),
                )

            tanque.nivel_actual = nuevo_nivel
            db.add(
                AjusteInventario(
                    tanque_id=tanque.id,
                    usuario_id=usuario.id,
                    litros=round(litros, 2),
                    nivel_previo_tanque=nivel_previo,
                    nivel_posterior_tanque=nuevo_nivel,
                    motivo=motivo,
                )
            )
            db.commit()
        except Exception:
            db.rollback()
            raise

        logger.info(
            "Ajuste de inventario tanque #%s: %+.2f L por %s (%s)",
            tanque.numero_tanque, litros, usuario.email, motivo,
        )
        db.refresh(tanque)
        return tanque

    # Alias conservado por compatibilidad con versiones previas
    reabastecer_tanque = ajustar_inventario

    @staticmethod
    def listar_ajustes(db: Session, tanque_id: int, skip: int = 0, limit: int = 50) -> List[AjusteInventario]:
        return (
            db.query(AjusteInventario)
            .options(joinedload(AjusteInventario.usuario))
            .filter(AjusteInventario.tanque_id == tanque_id)
            .order_by(AjusteInventario.created_at.desc(), AjusteInventario.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def map_ajuste_response(ajuste: AjusteInventario) -> AjusteInventarioResponse:
        res = AjusteInventarioResponse.model_validate(ajuste)
        if ajuste.usuario:
            res.usuario_nombre = ajuste.usuario.nombre
        return res

    @classmethod
    def delete_tanque(cls, db: Session, tanque_id: int) -> None:
        tanque = cls.get_tanque_by_id(db, tanque_id=tanque_id)

        bombas_asociadas = db.query(Dispensario).filter(Dispensario.tanque_id == tanque_id).count()
        if bombas_asociadas > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"No se puede eliminar el tanque porque tiene {bombas_asociadas} bomba(s) conectada(s). "
                    "Reasigne o elimine las bombas primero."
                ),
            )

        tiene_historial = any(
            db.query(modelo.id).filter(modelo.tanque_id == tanque_id).first() is not None
            for modelo in (TransaccionVenta, RecepcionPipa, AjusteInventario)
        )
        if tiene_historial:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "El tanque tiene historial de ventas, recepciones o ajustes y no puede eliminarse. "
                    "Desactívelo (esta_activo=false) para conservar la trazabilidad."
                ),
            )

        db.delete(tanque)
        db.commit()

    # LÓGICA DE BOMBAS / DISPENSARIOS
    @staticmethod
    def get_bomba_by_id(db: Session, bomba_id: int, for_update: bool = False) -> Dispensario:
        query = db.query(Dispensario).filter(Dispensario.id == bomba_id)
        if for_update:
            query = query.with_for_update()
        bomba = query.first()
        if not bomba:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dispensario/Bomba con ID {bomba_id} no existe",
            )
        return bomba

    @staticmethod
    def get_bomba_by_numero(db: Session, numero_bomba: int) -> Optional[Dispensario]:
        return db.query(Dispensario).filter(Dispensario.numero_bomba == numero_bomba).first()

    @classmethod
    def create_bomba(cls, db: Session, bomba_in: BombaCreate) -> Dispensario:
        if cls.get_bomba_by_numero(db, numero_bomba=bomba_in.numero_bomba):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe una bomba con el número #{bomba_in.numero_bomba}",
            )

        tanque = cls.get_tanque_by_id(db, tanque_id=bomba_in.tanque_id)
        if not tanque.esta_activo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El tanque #{tanque.numero_tanque} está inactivo y no puede recibir nuevas bombas",
            )

        db_bomba = Dispensario(**bomba_in.model_dump())
        db.add(db_bomba)
        db.commit()
        db.refresh(db_bomba)
        return db_bomba

    @classmethod
    def list_bombas(
        cls,
        db: Session,
        skip: int = 0,
        limit: int = 100,
        isla: Optional[int] = None,
        tanque_id: Optional[int] = None,
        estado: Optional[EstadoBomba] = None,
        solo_activas: Optional[bool] = None,
    ) -> List[Dispensario]:
        # joinedload evita el problema N+1 al leer el tanque de cada bomba
        query = db.query(Dispensario).options(joinedload(Dispensario.tanque))
        if isla is not None:
            query = query.filter(Dispensario.isla == isla)
        if tanque_id is not None:
            query = query.filter(Dispensario.tanque_id == tanque_id)
        if estado is not None:
            query = query.filter(Dispensario.estado == estado)
        if solo_activas is not None:
            query = query.filter(Dispensario.esta_activo == solo_activas)
        return query.order_by(Dispensario.numero_bomba.asc()).offset(skip).limit(limit).all()

    @classmethod
    def update_bomba(cls, db: Session, bomba_id: int, bomba_in: BombaUpdate) -> Dispensario:
        bomba = cls.get_bomba_by_id(db, bomba_id=bomba_id)

        if bomba_in.tanque_id is not None and bomba_in.tanque_id != bomba.tanque_id:
            tanque = cls.get_tanque_by_id(db, tanque_id=bomba_in.tanque_id)
            if not tanque.esta_activo:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"El nuevo tanque #{tanque.numero_tanque} asignado está inactivo",
                )
        if bomba_in.odometro_litros is not None and bomba_in.odometro_litros < bomba.odometro_litros:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El odómetro no puede retroceder de valor",
            )

        for campo, valor in bomba_in.model_dump(exclude_none=True).items():
            setattr(bomba, campo, valor)

        db.commit()
        db.refresh(bomba)
        return bomba

    @classmethod
    def cambiar_estado(cls, db: Session, bomba_id: int, nuevo_estado: EstadoBomba) -> Dispensario:
        bomba = cls.get_bomba_by_id(db, bomba_id=bomba_id)
        bomba.estado = nuevo_estado
        db.commit()
        db.refresh(bomba)
        return bomba

    @classmethod
    def delete_bomba(cls, db: Session, bomba_id: int) -> None:
        bomba = cls.get_bomba_by_id(db, bomba_id=bomba_id)
        if db.query(TransaccionVenta.id).filter(TransaccionVenta.bomba_id == bomba_id).first() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"La bomba #{bomba.numero_bomba} tiene ventas registradas y no puede eliminarse. "
                    "Desactívela o márquela FUERA_DE_SERVICIO para conservar la trazabilidad."
                ),
            )
        db.delete(bomba)
        db.commit()

    @staticmethod
    def map_bomba_response(bomba: Dispensario) -> BombaResponse:
        """Enriquece el esquema BombaResponse con los datos del tanque conectado."""
        res = BombaResponse.model_validate(bomba)
        if bomba.tanque:
            res.tanque_tipo_combustible = bomba.tanque.tipo_combustible.value
            res.tanque_precio_litro = bomba.tanque.precio_venta_litro
        return res
