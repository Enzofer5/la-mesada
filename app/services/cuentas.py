"""Cuentas a pagar a proveedores y sus pagos."""
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select

from ..extensions import db
from ..models import CuentaPagar, PagoProveedor, dec
from ..utils.validacion import ErrorNegocio
from .tenant import empresa_id, usuario_actual


def _cuenta_de(origen, origen_id):
    return db.session.scalar(select(CuentaPagar).where(
        CuentaPagar.empresa_id == empresa_id(), CuentaPagar.origen == origen, CuentaPagar.origen_id == origen_id))


def sincronizar(origen, origen_id, proveedor_id, importe, fecha, vencimiento=None, comprobante=None,
                descripcion=None, finca_id=None):
    """Crea/actualiza la cuenta a pagar de un registro (compra, gasto o combustible en cuenta corriente)."""
    cuenta = _cuenta_de(origen, origen_id)
    importe = dec(importe)
    if not proveedor_id or importe <= 0:
        if cuenta:
            eliminar(origen, origen_id)
        return None
    vencimiento = vencimiento or (fecha + timedelta(days=30))
    if cuenta is None:
        cuenta = CuentaPagar(empresa_id=empresa_id(), origen=origen, origen_id=origen_id, pagado=0)
        db.session.add(cuenta)
    elif dec(cuenta.pagado) > importe:
        raise ErrorNegocio("El nuevo importe es menor a lo ya pagado al proveedor. Revisá los pagos de la cuenta.")
    cuenta.proveedor_id = proveedor_id
    cuenta.importe = importe
    cuenta.fecha = fecha
    cuenta.vencimiento = vencimiento
    cuenta.comprobante = comprobante
    cuenta.descripcion = (descripcion or "")[:200]
    cuenta.finca_id = finca_id
    db.session.flush()
    return cuenta


def eliminar(origen, origen_id):
    cuenta = _cuenta_de(origen, origen_id)
    if cuenta is None:
        return
    if dec(cuenta.pagado) > 0:
        raise ErrorNegocio("No se puede eliminar: la cuenta a pagar asociada ya tiene pagos registrados.")
    db.session.delete(cuenta)
    db.session.flush()


def registrar_pago(cuenta, fecha, monto, metodo_pago, observaciones=None):
    monto = dec(monto)
    if monto <= 0:
        raise ErrorNegocio("El monto del pago debe ser mayor a cero.")
    if monto > cuenta.pendiente + Decimal("0.01"):
        raise ErrorNegocio(f"El pago supera el saldo pendiente de la cuenta ({cuenta.pendiente:.2f}).")
    usuario = usuario_actual()
    pago = PagoProveedor(empresa_id=empresa_id(), cuenta_id=cuenta.id, fecha=fecha, monto=monto,
                         metodo_pago=metodo_pago, observaciones=observaciones,
                         usuario_id=usuario.id if usuario else None)
    db.session.add(pago)
    cuenta.pagado = dec(cuenta.pagado) + monto
    db.session.flush()
    return pago


def eliminar_pago(pago):
    cuenta = pago.cuenta
    cuenta.pagado = dec(cuenta.pagado) - dec(pago.monto)
    db.session.delete(pago)
    db.session.flush()
