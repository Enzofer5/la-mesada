"""Gastos automáticos: cada módulo que genera un costo crea o actualiza sus gastos vinculados.

gastos.origen + gastos.origen_id identifican el registro que los generó. Al editar el registro se regeneran; al
eliminarlo se borran. Así la tabla gastos es la única fuente de costos del sistema.
"""
from decimal import Decimal

from sqlalchemy import delete, select

from ..extensions import db
from ..models import CATEGORIAS_BASE, CategoriaGasto, Gasto, dec
from .tenant import empresa_id, usuario_actual


def categoria_id(codigo):
    cat = db.session.scalar(select(CategoriaGasto).where(
        CategoriaGasto.empresa_id == empresa_id(), CategoriaGasto.codigo == codigo))
    if cat is None:
        nombre = dict(CATEGORIAS_BASE).get(codigo, codigo.replace("_", " ").capitalize())
        cat = CategoriaGasto(empresa_id=empresa_id(), codigo=codigo, nombre=nombre, orden=100)
        db.session.add(cat)
        db.session.flush()
    return cat.id


def crear_categorias_base(empresa_id_):
    existentes = set(db.session.scalars(select(CategoriaGasto.codigo).where(
        CategoriaGasto.empresa_id == empresa_id_)).all())
    for orden, (codigo, nombre) in enumerate(CATEGORIAS_BASE, start=1):
        if codigo not in existentes:
            db.session.add(CategoriaGasto(empresa_id=empresa_id_, codigo=codigo, nombre=nombre, orden=orden))


def eliminar(origen, origen_id):
    db.session.execute(delete(Gasto).where(
        Gasto.empresa_id == empresa_id(), Gasto.origen == origen, Gasto.origen_id == origen_id))


def sincronizar(origen, origen_id, items):
    """items: lista de dicts con categoria (código), monto, fecha, descripcion y opcionales
    finca_id, lote_id, campana_id, cultivo_id, proveedor_id, metodo_pago."""
    eliminar(origen, origen_id)
    usuario = usuario_actual()
    for item in items:
        monto = dec(item.get("monto")).quantize(Decimal("0.01"))
        if monto <= 0:
            continue
        db.session.add(Gasto(
            empresa_id=empresa_id(),
            fecha=item["fecha"],
            categoria_id=categoria_id(item["categoria"]),
            finca_id=item.get("finca_id"),
            lote_id=item.get("lote_id"),
            campana_id=item.get("campana_id"),
            cultivo_id=item.get("cultivo_id"),
            proveedor_id=item.get("proveedor_id"),
            descripcion=(item.get("descripcion") or "")[:200],
            monto=monto,
            metodo_pago=item.get("metodo_pago") or "efectivo",
            usuario_id=usuario.id if usuario else None,
            origen=origen,
            origen_id=origen_id,
        ))
    db.session.flush()
