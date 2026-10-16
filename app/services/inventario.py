"""Stock de insumos con costo promedio ponderado.

El stock y el costo promedio se recalculan SIEMPRE a partir de los movimientos (no se "suman y restan" a mano),
así nunca quedan desfasados aunque se editen o eliminen registros viejos.
"""
from decimal import Decimal

from sqlalchemy import delete, select

from ..extensions import db
from ..models import Insumo, Inventario, MovimientoInventario, dec
from ..utils.validacion import ErrorNegocio
from .tenant import empresa_id, usuario_actual

CATEGORIA_GASTO_POR_INSUMO = {
    "semilla": "semillas",
    "fertilizante": "fertilizantes",
    "agroquimico": "agroquimicos",
    "repuesto": "reparaciones",
    "combustible": "combustible",
    "otro": "otros",
}


def inventario_de(insumo):
    if insumo.inventario is None:
        inv = Inventario(empresa_id=insumo.empresa_id, insumo_id=insumo.id, cantidad=0, costo_promedio=0)
        db.session.add(inv)
        insumo.inventario = inv
        db.session.flush()
    return insumo.inventario


def recalcular(insumo_id):
    """Recorre los movimientos en orden cronológico y recalcula stock y costo promedio."""
    db.session.flush()
    insumo = db.session.get(Insumo, insumo_id)
    inv = inventario_de(insumo)
    movimientos = db.session.scalars(
        select(MovimientoInventario).where(MovimientoInventario.insumo_id == insumo_id)
        .order_by(MovimientoInventario.fecha, MovimientoInventario.id)
    ).all()
    stock = Decimal("0")
    promedio = Decimal("0")
    for m in movimientos:
        cantidad = dec(m.cantidad)
        if m.tipo == "entrada":
            precio = dec(m.precio_unitario)
            if precio > 0:
                if stock <= 0:
                    promedio = precio
                else:
                    promedio = (stock * promedio + cantidad * precio) / (stock + cantidad)
            stock += cantidad
        elif m.tipo == "salida":
            stock -= cantidad
        else:  # ajuste: cantidad con signo
            stock += cantidad
    inv.cantidad = stock.quantize(Decimal("0.001"))
    inv.costo_promedio = promedio.quantize(Decimal("0.0001"))
    return inv


def verificar_no_negativo(insumo_id):
    inv = recalcular(insumo_id)
    if inv.cantidad < 0:
        insumo = db.session.get(Insumo, insumo_id)
        faltante = -inv.cantidad
        raise ErrorNegocio(
            f"Stock insuficiente de {insumo.nombre}: faltan {faltante:.2f} {insumo.unidad.abreviatura}. "
            + ("Registrá la cosecha donde se guardó esa semilla (o un ingreso manual al stock)." if insumo.propia
               else "Registrá primero la compra o el ingreso al inventario.")
        )
    return inv


def registrar(insumo, tipo, cantidad, fecha, precio_unitario=None, origen="manual", origen_id=None,
              finca_id=None, lote_id=None, campana_id=None, cultivo_id=None, proveedor_id=None,
              observaciones=None, validar=True):
    """Crea un movimiento y recalcula. En salidas el precio es el costo promedio vigente."""
    inv = inventario_de(insumo)
    if tipo == "salida" and precio_unitario is None:
        precio_unitario = inv.costo_promedio
    usuario = usuario_actual()
    mov = MovimientoInventario(
        empresa_id=empresa_id(), insumo_id=insumo.id, tipo=tipo, fecha=fecha, cantidad=cantidad,
        precio_unitario=precio_unitario or 0, origen=origen, origen_id=origen_id, finca_id=finca_id,
        lote_id=lote_id, campana_id=campana_id, cultivo_id=cultivo_id, proveedor_id=proveedor_id,
        responsable_id=usuario.id if usuario else None, observaciones=observaciones,
    )
    db.session.add(mov)
    db.session.flush()
    if validar:
        verificar_no_negativo(insumo.id)
    else:
        recalcular(insumo.id)
    return mov


def eliminar_por_origen(origen, origen_id, validar=False):
    """Borra los movimientos generados por un registro y recalcula los insumos afectados."""
    insumos = db.session.scalars(
        select(MovimientoInventario.insumo_id).where(
            MovimientoInventario.empresa_id == empresa_id(),
            MovimientoInventario.origen == origen, MovimientoInventario.origen_id == origen_id)
    ).all()
    db.session.execute(delete(MovimientoInventario).where(
        MovimientoInventario.empresa_id == empresa_id(),
        MovimientoInventario.origen == origen, MovimientoInventario.origen_id == origen_id))
    for insumo_id in set(insumos):
        if validar:
            verificar_no_negativo(insumo_id)
        else:
            recalcular(insumo_id)
    return set(insumos)


def insumos_bajo_stock():
    stmt = select(Insumo).where(Insumo.empresa_id == empresa_id(), Insumo.estado == "activo",
                                Insumo.stock_minimo > 0)
    return [i for i in db.session.scalars(stmt).unique().all() if i.stock < i.stock_minimo]
