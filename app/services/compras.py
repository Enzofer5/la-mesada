"""Compras de insumos: entran al inventario (costo promedio) y, si son a plazo, generan la cuenta a pagar.

Las compras NO son costo del cultivo: el costo se imputa cuando el insumo se aplica o se consume.
"""
from decimal import Decimal

from ..extensions import db
from ..models import DetalleCompra, Insumo, dec
from ..utils.validacion import ErrorNegocio
from . import cuentas, inventario
from .tenant import empresa_id

CENT = Decimal("0.01")


def guardar_compra(compra, renglones, nuevo):
    if not renglones:
        raise ErrorNegocio("Cargá al menos un producto comprado.")
    if nuevo:
        db.session.add(compra)
        db.session.flush()
    afectados = inventario.eliminar_por_origen("compra", compra.id)
    compra.detalles.clear()
    db.session.flush()
    total = Decimal("0")
    for r in renglones:
        if dec(r["cantidad"]) <= 0 or dec(r["precio_unitario"]) < 0:
            raise ErrorNegocio("Revisá cantidades y precios de los productos.")
        insumo = db.session.get(Insumo, r["insumo_id"])
        if insumo.propia:
            raise ErrorNegocio(f"«{insumo.nombre}» es semilla propia (no se compra). Si compraste semilla, "
                               "cargala en un insumo de semilla comprada.")
        subtotal = (dec(r["cantidad"]) * dec(r["precio_unitario"])).quantize(CENT)
        compra.detalles.append(DetalleCompra(empresa_id=empresa_id(), insumo_id=insumo.id, cantidad=r["cantidad"],
                                             precio_unitario=r["precio_unitario"], subtotal=subtotal))
        inventario.registrar(insumo, "entrada", r["cantidad"], compra.fecha, precio_unitario=r["precio_unitario"],
                             origen="compra", origen_id=compra.id, finca_id=compra.finca_id,
                             proveedor_id=compra.proveedor_id, observaciones=f"Compra {compra.comprobante or ''}",
                             validar=False)
        afectados.add(insumo.id)
        total += subtotal
    compra.total = total
    db.session.flush()
    for insumo_id in afectados:  # al editar, no puede quedar stock negativo por insumos ya consumidos
        inventario.verificar_no_negativo(insumo_id)
    if compra.condicion == "cuenta_corriente":
        cuentas.sincronizar("compra", compra.id, compra.proveedor_id, total, compra.fecha, compra.vencimiento,
                            compra.comprobante, f"Compra de insumos #{compra.id}", compra.finca_id)
    else:
        cuentas.eliminar("compra", compra.id)
    return compra


def eliminar_compra(compra):
    cuentas.eliminar("compra", compra.id)
    compra_id = compra.id
    db.session.delete(compra)
    db.session.flush()
    inventario.eliminar_por_origen("compra", compra_id, validar=True)
