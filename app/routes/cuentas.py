"""Pagos de cuentas a pagar a proveedores."""
from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..extensions import db
from ..models import METODOS_PAGO, CuentaPagar, PagoProveedor
from ..services import auditoria
from ..services import cuentas as svc
from ..services.tenant import obtener_o_404
from ..utils.fechas import parse_fecha
from ..utils.permisos import EDITAR, ELIMINAR, requiere_permiso
from ..utils.validacion import ErrorNegocio, parse_decimal

bp = Blueprint("cuentas", __name__, url_prefix="/cuentas-pagar")
METODOS = [m for m in METODOS_PAGO if m[0] != "cuenta_corriente"]


@bp.route("/<int:cuenta_id>/pagar", methods=["GET", "POST"])
@requiere_permiso("cuentas_pagar", EDITAR)
def pagar(cuenta_id):
    cuenta = obtener_o_404(CuentaPagar, cuenta_id)
    if request.method == "POST":
        try:
            monto = parse_decimal(request.form.get("monto"))
            metodo = request.form.get("metodo_pago")
            if metodo not in dict(METODOS):
                raise ErrorNegocio("Elegí el método de pago.")
            fecha = parse_fecha(request.form.get("fecha")) or date.today()
            svc.registrar_pago(cuenta, fecha, monto or 0, metodo, (request.form.get("observaciones") or "")[:500])
            auditoria.registrar("cuentas_pagar", "pago", auditoria.frase(
                "pago", f"la cuenta de {cuenta.proveedor.razon_social} por $ {monto:,.0f}".replace(",", ".")), cuenta.id)
            db.session.commit()
            flash("Pago registrado.", "exito")
            return redirect(url_for("crud.detalle", key="cuentas_pagar", id=cuenta.id))
        except (ErrorNegocio, ValueError) as e:
            db.session.rollback()
            flash(str(e) if isinstance(e, ErrorNegocio) else "Monto inválido.", "error")
            cuenta = obtener_o_404(CuentaPagar, cuenta_id)
    return render_template("cuentas/pagar.html", cuenta=cuenta, metodos=METODOS, hoy=date.today())


@bp.route("/pagos/<int:pago_id>/eliminar", methods=["POST"])
@requiere_permiso("cuentas_pagar", ELIMINAR)
def eliminar_pago(pago_id):
    pago = obtener_o_404(PagoProveedor, pago_id, None)
    cuenta_id = pago.cuenta_id
    svc.eliminar_pago(pago)
    auditoria.registrar("cuentas_pagar", "eliminar", auditoria.frase("eliminar", f"un pago de la cuenta #{cuenta_id}"),
                        cuenta_id)
    db.session.commit()
    flash("Pago eliminado.", "exito")
    return redirect(url_for("crud.detalle", key="cuentas_pagar", id=cuenta_id))
