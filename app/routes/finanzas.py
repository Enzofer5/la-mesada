"""Caja / Finanzas: ingresos vs gastos, cuentas a cobrar y a pagar, deuda con empleados."""
from collections import defaultdict
from datetime import date
from decimal import Decimal

from flask import Blueprint, render_template, request
from sqlalchemy import func, select

from ..extensions import db
from ..models import CuentaPagar, Empleado, Ingreso, PagoEmpleado, PagoProveedor, Trabajo, Venta
from ..services import dashboard as svc_dash
from ..services import filtros
from ..services.tenant import empresa_id, fincas_permitidas
from ..utils.permisos import requiere_permiso
from .comun import opciones_filtros

bp = Blueprint("finanzas", __name__, url_prefix="/finanzas")
CERO = Decimal("0")


def _suma(stmt):
    return Decimal(str(db.session.scalar(stmt) or 0))


@bp.route("/")
@requiere_permiso("finanzas")
def index():
    f = filtros.leer(request.args)
    if not any(f[k] for k in ("desde", "hasta", "campana", "anio")):
        f["anio"] = date.today().year
        f["desde"], f["hasta"] = date(f["anio"], 1, 1), date(f["anio"], 12, 31)
    eid = empresa_id()
    ids = fincas_permitidas()

    def periodo(stmt, col):
        if f.get("desde"):
            stmt = stmt.where(col >= f["desde"])
        if f.get("hasta"):
            stmt = stmt.where(col <= f["hasta"])
        return stmt

    def fincas(stmt, col):
        if f.get("finca"):
            stmt = stmt.where(col == f["finca"])
        if ids is not None:
            stmt = stmt.where(col.in_(ids or [-1]))
        return stmt

    cobrado = _suma(fincas(periodo(select(func.sum(Ingreso.monto)).where(
        Ingreso.empresa_id == eid, Ingreso.estado == "acreditado"), Ingreso.fecha), Ingreso.finca_id))
    a_depositar = _suma(fincas(select(func.sum(Ingreso.monto)).where(
        Ingreso.empresa_id == eid, Ingreso.estado == "a_depositar"), Ingreso.finca_id))
    pagos_prov = _suma(periodo(select(func.sum(PagoProveedor.monto)).where(PagoProveedor.empresa_id == eid),
                               PagoProveedor.fecha)) if ids is None and not f.get("finca") else None
    pagos_emp = _suma(fincas(periodo(select(func.sum(PagoEmpleado.monto)).where(PagoEmpleado.empresa_id == eid),
                                     PagoEmpleado.fecha), PagoEmpleado.finca_id))
    devengado_emp = _suma(fincas(select(func.sum(Trabajo.total)).where(Trabajo.empresa_id == eid), Trabajo.finca_id)) \
        + _suma(fincas(select(func.sum(PagoEmpleado.monto)).where(PagoEmpleado.empresa_id == eid,
                                                                  PagoEmpleado.imputar_costo.is_(True)),
                       PagoEmpleado.finca_id))
    pagado_emp_total = _suma(fincas(select(func.sum(PagoEmpleado.monto)).where(PagoEmpleado.empresa_id == eid),
                                    PagoEmpleado.finca_id))

    ventas_stmt = select(Venta).where(Venta.empresa_id == eid)
    ventas_pend = [v for v in db.session.scalars(fincas(ventas_stmt, Venta.finca_id)).unique() if v.saldo > 0]
    ventas_pend.sort(key=lambda v: v.fecha_vencimiento_cobro or v.fecha)
    cuentas_stmt = select(CuentaPagar).where(CuentaPagar.empresa_id == eid, CuentaPagar.pagado < CuentaPagar.importe)
    if f.get("finca"):
        cuentas_stmt = cuentas_stmt.where(CuentaPagar.finca_id == f["finca"])
    cuentas = db.session.scalars(cuentas_stmt.order_by(CuentaPagar.vencimiento)).unique().all()
    serie = svc_dash.ingresos_gastos_por_mes(f)
    kpis = svc_dash.kpis(f)
    return render_template(
        "finanzas/index.html", f=f, descripcion=filtros.descripcion(f), opciones=opciones_filtros(),
        cobrado=cobrado, a_depositar=a_depositar, pagos_prov=pagos_prov, pagos_emp=pagos_emp,
        deuda_empleados=devengado_emp - pagado_emp_total, ventas_pend=ventas_pend[:15],
        por_cobrar=sum((v.saldo for v in ventas_pend), CERO), cuentas=cuentas[:15],
        por_pagar=sum((c.pendiente for c in cuentas), CERO),
        vencido=sum((c.pendiente for c in cuentas if c.estado == "vencido"), CERO),
        serie=serie, kpis=kpis, query=filtros.a_query(f),
    )
