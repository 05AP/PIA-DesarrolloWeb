import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.infraestructura import (
    Dispensario,
    EstadoBomba,
    TanqueCombustible,
    TipoCombustible,
)
from app.models.operaciones import MetodoPagoEnum, RecepcionPipa, TransaccionVenta
from app.models.user import Usuario
from app.schemas.operaciones import (
    CorteTurnoResponse,
    DetalleBombaCorte,
    DetalleCombustible,
    DetalleMetodoPago,
    RecepcionPipaCreate,
    RecepcionPipaResponse,
    VentaCreate,
    VentaResponse,
)

logger = logging.getLogger(__name__)

TOLERANCIA_LITROS = 0.01  # Diferencia mínima considerada discrepancia en la auditoría de odómetros


def _to_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Normaliza a UTC; una fecha sin zona horaria se interpreta como UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class OperacionesService:
    """Servicio para la lógica de negocio central: Despacho de combustible, Recepción de pipas y Arqueo/Corte."""

    # 1. DESPACHO / VENTA DE COMBUSTIBLE (ACID)
    @classmethod
    def registrar_despacho(
        cls,
        db: Session,
        venta_in: VentaCreate,
        despachador: Usuario,
    ) -> TransaccionVenta:
        """Ejecuta la transacción central ACID de venta de combustible:

        1. Valida que la bomba exista, esté ACTIVA y habilitada.
        2. Valida que el tanque esté operativo y tenga inventario suficiente.
        3. Calcula el importe total (litros * precio_por_litro vigente).
        4. Descuenta el inventario del tanque.
        5. Avanza el odómetro de la bomba.
        6. Genera folio único y registra la transacción.

        Todo ocurre en una sola transacción: si algo falla se hace rollback completo.
        Las filas de bomba y tanque se bloquean (SELECT ... FOR UPDATE en PostgreSQL) para que
        dos ventas simultáneas no puedan sobregirar el inventario.
        """
        try:
            bomba = (
                db.query(Dispensario)
                .filter(Dispensario.id == venta_in.bomba_id)
                .with_for_update()
                .first()
            )
            if not bomba:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Bomba con ID {venta_in.bomba_id} no encontrada en catálogo.",
                )

            if not bomba.esta_activo:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"La bomba #{bomba.numero_bomba} se encuentra deshabilitada administrativamente.",
                )

            if bomba.estado != EstadoBomba.ACTIVA:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Operación rechazada: La bomba #{bomba.numero_bomba} está en estado "
                        f"'{bomba.estado.value}' y no puede despachar combustible."
                    ),
                )

            tanque = (
                db.query(TanqueCombustible)
                .filter(TanqueCombustible.id == bomba.tanque_id)
                .with_for_update()
                .first()
            )
            if not tanque or not tanque.esta_activo:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"El tanque #{tanque.numero_tanque if tanque else bomba.tanque_id} no está operativo.",
                )

            litros = round(venta_in.litros, 2)
            if tanque.nivel_actual < litros:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Inventario insuficiente en el tanque #{tanque.numero_tanque} ({tanque.tipo_combustible.value}). "
                        f"Nivel disponible: {tanque.nivel_actual:.2f} L, Cantidad solicitada: {litros:.2f} L."
                    ),
                )

            precio_unitario = tanque.precio_venta_litro
            total_pagar = round(litros * precio_unitario, 2)

            tanque.nivel_actual = round(tanque.nivel_actual - litros, 2)

            odometro_inicial = bomba.odometro_litros
            odometro_final = round(odometro_inicial + litros, 2)
            bomba.odometro_litros = odometro_final

            timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            folio_unico = f"VTA-{timestamp_str}-{uuid.uuid4().hex[:6].upper()}"

            nueva_venta = TransaccionVenta(
                folio=folio_unico,
                bomba_id=bomba.id,
                tanque_id=tanque.id,
                despachador_id=despachador.id,
                tipo_combustible=tanque.tipo_combustible,
                litros=litros,
                precio_unitario=precio_unitario,
                total=total_pagar,
                metodo_pago=venta_in.metodo_pago,
                placa_vehiculo=venta_in.placa_vehiculo.upper() if venta_in.placa_vehiculo else None,
                cliente=venta_in.cliente,
                odometro_inicial=odometro_inicial,
                odometro_final=odometro_final,
            )

            db.add(nueva_venta)
            db.commit()
        except Exception:
            # Cualquier error (de negocio o inesperado) revierte la transacción completa.
            # Los errores inesperados los registra y responde el manejador global (500 genérico).
            db.rollback()
            raise

        db.refresh(nueva_venta)
        logger.info("Venta %s: %.2f L en bomba #%s por %s", folio_unico, litros, bomba.numero_bomba, despachador.email)
        return nueva_venta

    @classmethod
    def listar_ventas(
        cls,
        db: Session,
        skip: int = 0,
        limit: int = 100,
        bomba_id: Optional[int] = None,
        tipo_combustible: Optional[TipoCombustible] = None,
        metodo_pago: Optional[MetodoPagoEnum] = None,
        despachador_id: Optional[int] = None,
    ) -> List[TransaccionVenta]:
        query = db.query(TransaccionVenta).options(joinedload(TransaccionVenta.despachador))
        if bomba_id:
            query = query.filter(TransaccionVenta.bomba_id == bomba_id)
        if tipo_combustible:
            query = query.filter(TransaccionVenta.tipo_combustible == tipo_combustible)
        if metodo_pago:
            query = query.filter(TransaccionVenta.metodo_pago == metodo_pago)
        if despachador_id:
            query = query.filter(TransaccionVenta.despachador_id == despachador_id)

        return (
            query.order_by(TransaccionVenta.created_at.desc(), TransaccionVenta.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    @classmethod
    def obtener_venta_por_id(cls, db: Session, venta_id: int) -> TransaccionVenta:
        venta = db.query(TransaccionVenta).filter(TransaccionVenta.id == venta_id).first()
        if not venta:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transacción de venta con ID {venta_id} no encontrada.",
            )
        return venta

    # 2. SUMINISTRO (RECEPCIÓN DE PIPAS)
    @classmethod
    def registrar_recepcion_pipa(
        cls,
        db: Session,
        recepcion_in: RecepcionPipaCreate,
        supervisor: Usuario,
    ) -> RecepcionPipa:
        """Registra la descarga de combustible de una pipa al tanque subterráneo:

        - Valida que el folio de remisión sea único (409 si está duplicado).
        - Valida que el tanque exista y esté activo.
        - Valida que el nuevo costo no supere el precio de venta vigente (no vender con pérdida).
        - Valida la regla anti-derrame (nivel actual + carga <= capacidad máxima).
        - Incrementa el inventario y actualiza el costo de adquisición por litro.
        """
        folio = recepcion_in.folio_remision.strip()
        try:
            existente = db.query(RecepcionPipa.id).filter(RecepcionPipa.folio_remision == folio).first()
            if existente:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"El folio de remisión '{folio}' ya fue registrado previamente en el sistema.",
                )

            tanque = (
                db.query(TanqueCombustible)
                .filter(TanqueCombustible.id == recepcion_in.tanque_id)
                .with_for_update()
                .first()
            )
            if not tanque:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Tanque con ID {recepcion_in.tanque_id} no encontrado.",
                )

            if not tanque.esta_activo:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"El tanque #{tanque.numero_tanque} se encuentra inactivo y no puede recibir combustible.",
                )

            if recepcion_in.costo_compra_litro > tanque.precio_venta_litro:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"El costo de compra (${recepcion_in.costo_compra_litro:.2f}/L) supera el precio de venta vigente "
                        f"del tanque #{tanque.numero_tanque} (${tanque.precio_venta_litro:.2f}/L). "
                        "Actualice primero el precio de venta del tanque."
                    ),
                )

            litros = round(recepcion_in.litros_recibidos, 2)
            nivel_previo = tanque.nivel_actual
            nivel_posterior = round(nivel_previo + litros, 2)
            if nivel_posterior > tanque.capacidad_total:
                espacio_disponible = round(tanque.capacidad_total - nivel_previo, 2)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Riesgo de derrame / sobrecupo: La carga de {litros:.2f} L excede "
                        f"la capacidad máxima de seguridad del tanque #{tanque.numero_tanque}. "
                        f"Capacidad total: {tanque.capacidad_total:.2f} L, Nivel actual: {nivel_previo:.2f} L, "
                        f"Espacio máximo disponible: {espacio_disponible:.2f} L."
                    ),
                )

            tanque.nivel_actual = nivel_posterior
            tanque.costo_compra_litro = recepcion_in.costo_compra_litro

            nueva_recepcion = RecepcionPipa(
                folio_remision=folio,
                tanque_id=tanque.id,
                supervisor_id=supervisor.id,
                proveedor=recepcion_in.proveedor.strip(),
                placa_pipa=recepcion_in.placa_pipa.upper() if recepcion_in.placa_pipa else None,
                chofer=recepcion_in.chofer,
                litros_recibidos=litros,
                costo_compra_litro=recepcion_in.costo_compra_litro,
                costo_total=round(litros * recepcion_in.costo_compra_litro, 2),
                nivel_previo_tanque=nivel_previo,
                nivel_posterior_tanque=nivel_posterior,
                notas=recepcion_in.notas,
            )

            db.add(nueva_recepcion)
            db.commit()
        except Exception:
            db.rollback()
            raise

        db.refresh(nueva_recepcion)
        logger.info("Recepción de pipa %s: %.2f L al tanque #%s", folio, litros, tanque.numero_tanque)
        return nueva_recepcion

    @classmethod
    def listar_recepciones_pipas(
        cls,
        db: Session,
        skip: int = 0,
        limit: int = 100,
        tanque_id: Optional[int] = None,
    ) -> List[RecepcionPipa]:
        query = db.query(RecepcionPipa).options(
            joinedload(RecepcionPipa.tanque), joinedload(RecepcionPipa.supervisor)
        )
        if tanque_id:
            query = query.filter(RecepcionPipa.tanque_id == tanque_id)
        return (
            query.order_by(RecepcionPipa.created_at.desc(), RecepcionPipa.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    # 3. ARQUEO Y CORTE DE TURNO
    @classmethod
    def generar_corte_turno(
        cls,
        db: Session,
        fecha_inicio: Optional[datetime] = None,
        fecha_fin: Optional[datetime] = None,
        despachador_id: Optional[int] = None,
    ) -> CorteTurnoResponse:
        """Genera el reporte de corte de turno y arqueo de caja:

        - Totales de transacciones, litros e ingresos (opcionalmente por despachador).
        - Desglose por método de pago y por tipo de combustible.
        - Auditoría de bombas: compara el avance real del odómetro de cada bomba contra la suma
          de litros vendidos. Si el odómetro avanzó más de lo registrado en ventas (huecos entre
          lecturas consecutivas o avance posterior a la última venta), se reporta el faltante.
          La auditoría es a nivel estación (todas las ventas del periodo, sin filtro de despachador).
        """
        fecha_inicio = _to_utc(fecha_inicio)
        fecha_fin = _to_utc(fecha_fin)
        if fecha_inicio and fecha_fin and fecha_inicio > fecha_fin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La fecha de inicio del corte no puede ser posterior a la fecha de fin.",
            )

        query_periodo = db.query(TransaccionVenta)
        if fecha_inicio:
            query_periodo = query_periodo.filter(TransaccionVenta.created_at >= fecha_inicio)
        if fecha_fin:
            query_periodo = query_periodo.filter(TransaccionVenta.created_at <= fecha_fin)
        ventas_periodo = query_periodo.order_by(TransaccionVenta.created_at.asc(), TransaccionVenta.id.asc()).all()

        ventas = (
            [v for v in ventas_periodo if v.despachador_id == despachador_id] if despachador_id else ventas_periodo
        )

        total_transacciones = len(ventas)
        litros_totales = round(sum(v.litros for v in ventas), 2)
        ingresos_totales = round(sum(v.total for v in ventas), 2)

        metodos_pago_map = {m: {"count": 0, "monto": 0.0} for m in MetodoPagoEnum}
        combustibles_map = {c: {"litros": 0.0, "monto": 0.0} for c in TipoCombustible}
        ventas_por_bomba_filtradas: Dict[int, List[TransaccionVenta]] = defaultdict(list)
        for v in ventas:
            metodos_pago_map[v.metodo_pago]["count"] += 1
            metodos_pago_map[v.metodo_pago]["monto"] += v.total
            combustibles_map[v.tipo_combustible]["litros"] += v.litros
            combustibles_map[v.tipo_combustible]["monto"] += v.total
            ventas_por_bomba_filtradas[v.bomba_id].append(v)

        desglose_metodos = [
            DetalleMetodoPago(metodo=metodo, cantidad_transacciones=d["count"], monto_total=round(d["monto"], 2))
            for metodo, d in metodos_pago_map.items()
        ]
        desglose_combustibles = [
            DetalleCombustible(tipo_combustible=tipo, litros_vendidos=round(d["litros"], 2), monto_total=round(d["monto"], 2))
            for tipo, d in combustibles_map.items()
        ]

        ventas_por_bomba_periodo: Dict[int, List[TransaccionVenta]] = defaultdict(list)
        for v in ventas_periodo:
            ventas_por_bomba_periodo[v.bomba_id].append(v)

        bombas = (
            db.query(Dispensario)
            .options(joinedload(Dispensario.tanque))
            .order_by(Dispensario.numero_bomba.asc())
            .all()
        )
        detalle_bombas: List[DetalleBombaCorte] = []
        bombas_con_discrepancia: List[str] = []
        faltante_total = 0.0

        for b in bombas:
            filtradas = ventas_por_bomba_filtradas.get(b.id, [])
            auditadas = ventas_por_bomba_periodo.get(b.id, [])

            litros_odometro = 0.0
            faltante = 0.0
            if auditadas:
                lectura_inicial = auditadas[0].odometro_inicial
                # Si el corte es abierto (hasta ahora) se compara contra la lectura actual del odómetro
                lectura_final = b.odometro_litros if fecha_fin is None else auditadas[-1].odometro_final
                litros_odometro = round(lectura_final - lectura_inicial, 2)
                litros_registrados = round(sum(v.litros for v in auditadas), 2)
                faltante = round(litros_odometro - litros_registrados, 2)

            if abs(faltante) >= TOLERANCIA_LITROS:
                bombas_con_discrepancia.append(f"#{b.numero_bomba} ({faltante:+.2f} L)")
                faltante_total += faltante

            detalle_bombas.append(
                DetalleBombaCorte(
                    bomba_id=b.id,
                    numero_bomba=b.numero_bomba,
                    isla=b.isla,
                    tipo_combustible=b.tanque.tipo_combustible.value if b.tanque else "N/A",
                    odometro_actual=b.odometro_litros,
                    litros_vendidos_periodo=round(sum(v.litros for v in filtradas), 2),
                    monto_vendido_periodo=round(sum(v.total for v in filtradas), 2),
                    litros_por_odometro=litros_odometro,
                    litros_sin_registro=faltante,
                )
            )

        if not bombas_con_discrepancia:
            cuadre_status = "CUADRADO_EXACTO"
            observaciones = (
                f"Corte sin discrepancias. Se validaron {total_transacciones} transacciones "
                f"correspondientes a {litros_totales:.2f} L despachados; los odómetros coinciden con las ventas."
            )
        else:
            cuadre_status = "DISCREPANCIA_DETECTADA"
            observaciones = (
                f"Alerta de auditoría: el avance de odómetros no coincide con las ventas registradas en "
                f"{len(bombas_con_discrepancia)} bomba(s): {', '.join(bombas_con_discrepancia)}. "
                f"Diferencia total: {faltante_total:+.2f} L."
            )

        return CorteTurnoResponse(
            fecha_corte=datetime.now(timezone.utc),
            periodo_inicio=fecha_inicio,
            periodo_fin=fecha_fin,
            total_transacciones=total_transacciones,
            litros_totales_vendidos=litros_totales,
            ingresos_totales=ingresos_totales,
            desglose_metodos_pago=desglose_metodos,
            desglose_combustibles=desglose_combustibles,
            detalle_bombas=detalle_bombas,
            cuadre_status=cuadre_status,
            observaciones=observaciones,
        )

    # MAPEOS DE RESPUESTA
    @staticmethod
    def map_venta_response(venta: TransaccionVenta) -> VentaResponse:
        res = VentaResponse.model_validate(venta)
        if venta.despachador:
            res.despachador_nombre = venta.despachador.nombre
        return res

    @staticmethod
    def map_recepcion_response(recepcion: RecepcionPipa) -> RecepcionPipaResponse:
        res = RecepcionPipaResponse.model_validate(recepcion)
        if recepcion.tanque:
            res.tanque_numero = recepcion.tanque.numero_tanque
            res.tanque_combustible = recepcion.tanque.tipo_combustible.value
        if recepcion.supervisor:
            res.supervisor_nombre = recepcion.supervisor.nombre
        return res
