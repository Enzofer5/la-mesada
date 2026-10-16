"""Ventas con renglones, flete y cobros."""
from decimal import Decimal

from ..extensions import db
from ..models import Cultivo, DetalleVenta, Ingreso, UnidadMedida, Venta, dec
from ..utils.validacion import ErrorNegocio
from . import gastos_auto
from .tenant import empresa_id, usuario_actual

CENT = Decimal("0.01")


def convertir(cantidad, unidad_origen, unidad_destino):
    """Convierte cantidades entre unidades del mismo tipo usando factor_base. None si no son comparables."""
    if cantidad is None:
        return None
    if unidad_origen.id == unidad_destino.id:
        return dec(cantidad)
    if unidad_origen.tipo != unidad_destino.tipo or unidad_origen.tipo in ("otro",):
        return None
    if not unidad_destino.factor_base:
        return None
    return dec(cantidad) * dec(unidad_origen.factor_base) / dec(unidad_destino.factor_base)


def validar_renglones(renglones):
    if not renglones:
        raise ErrorNegocio("Cargá al menos un producto vendido.")
    for r in renglones:
        if dec(r["cantidad"]) <= 0:
            raise ErrorNegocio("Las cantidades deben ser mayores a cero.")
        if dec(r["precio_unitario"]) < 0:
            raise ErrorNegocio("El precio no puede ser negativo.")


def guardar_venta(venta, renglones, nuevo, cobrar_ahora=False, metodo_cobro="efectivo"):
    validar_renglones(renglones)
    if nuevo:
        db.session.add(venta)
    venta.detalles.clear()
    db.session.flush()
    total = Decimal("0")
    for r in renglones:
        subtotal = (dec(r["cantidad"]) * dec(r["precio_unitario"])).quantize(CENT)
        venta.detalles.append(DetalleVenta(
            empresa_id=empresa_id(), cultivo_id=r["cultivo_id"], lote_id=r.get("lote_id"), calidad=r.get("calidad"),
            cantidad=r["cantidad"], unidad_id=r["unidad_id"], precio_unitario=r["precio_unitario"], subtotal=subtotal))
        total += subtotal
    venta.total = total
    db.session.flush()
    if venta.cobrado > total + CENT:
        raise ErrorNegocio("El total de la venta quedó por debajo de lo ya cobrado. Revisá los cobros.")
    _sincronizar_flete(venta)
    if nuevo and cobrar_ahora and total > 0:
        registrar_cobro(venta, venta.fecha, total, metodo_cobro, "acreditado", "Cobrado al momento de la venta")
    return venta


def _sincronizar_flete(venta):
    if venta.flete_a_cargo != "vendedor" or dec(venta.costo_flete) <= 0 or not venta.total:
        gastos_auto.eliminar("venta_flete", venta.id)
        return
    por_cultivo = {}
    for d in venta.detalles:
        por_cultivo[d.cultivo_id] = por_cultivo.get(d.cultivo_id, Decimal("0")) + dec(d.subtotal)
    items = []
    for cultivo_id, subtotal in por_cultivo.items():
        parte = dec(venta.costo_flete) * subtotal / dec(venta.total)
        cultivo = db.session.get(Cultivo, cultivo_id)
        items.append({"categoria": "transporte", "monto": parte, "fecha": venta.fecha,
                      "descripcion": f"Flete venta #{venta.id} · {cultivo.nombre} · {venta.transporte or ''}".strip(),
                      "finca_id": venta.finca_id, "campana_id": venta.campana_id, "cultivo_id": cultivo_id})
    gastos_auto.sincronizar("venta_flete", venta.id, items)


def registrar_cobro(venta, fecha, monto, metodo_pago, estado="acreditado", observaciones=None):
    monto = dec(monto)
    if monto <= 0:
        raise ErrorNegocio("El monto del cobro debe ser mayor a cero.")
    if monto > venta.saldo + CENT:
        raise ErrorNegocio(f"El cobro supera el saldo pendiente de la venta ({venta.saldo:.2f}).")
    cultivos = {d.cultivo_id for d in venta.detalles}
    usuario = usuario_actual()
    ingreso = Ingreso(
        empresa_id=empresa_id(), venta_id=venta.id, cliente_id=venta.cliente_id, fecha=fecha,
        concepto=f"Cobro venta #{venta.id}", monto=monto, metodo_pago=metodo_pago, estado=estado,
        finca_id=venta.finca_id, campana_id=venta.campana_id,
        cultivo_id=cultivos.pop() if len(cultivos) == 1 else None,
        usuario_id=usuario.id if usuario else None, observaciones=observaciones)
    db.session.add(ingreso)
    venta.ingresos.append(ingreso)
    db.session.flush()
    return ingreso


def eliminar_venta(venta):
    if venta.ingresos:
        raise ErrorNegocio("La venta tiene cobros registrados. Eliminá primero los cobros.")
    gastos_auto.eliminar("venta_flete", venta.id)
    db.session.delete(venta)
    db.session.flush()


def unidad(id_):
    return db.session.get(UnidadMedida, id_)
