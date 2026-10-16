"""Panel del trabajador: sólo sus trabajos, pagos, saldo y tareas."""
from datetime import date, timedelta
from decimal import Decimal

from flask import Blueprint, render_template
from flask_login import current_user
from sqlalchemy import func, or_, select

from ..extensions import db
from ..models import ActividadCultivo, Alerta, Empleado, PagoEmpleado, Trabajo
from ..utils.permisos import requiere_permiso

bp = Blueprint("trabajador", __name__, url_prefix="/mi-panel")


@bp.route("/")
@requiere_permiso("mi_panel")
def panel():
    empleado = db.session.scalar(select(Empleado).where(Empleado.usuario_id == current_user.id,
                                                        Empleado.empresa_id == current_user.empresa_id))
    datos = {"empleado": empleado, "trabajos": [], "pagos": [], "tareas": [], "actividades": [],
             "trabajado": Decimal("0"), "pagado": Decimal("0")}
    if empleado:
        datos["trabajos"] = db.session.scalars(select(Trabajo).where(Trabajo.empleado_id == empleado.id)
                                               .order_by(Trabajo.fecha.desc()).limit(30)).unique().all()
        datos["pagos"] = db.session.scalars(select(PagoEmpleado).where(PagoEmpleado.empleado_id == empleado.id)
                                            .order_by(PagoEmpleado.fecha.desc()).limit(15)).unique().all()
        datos["trabajado"] = Decimal(str(db.session.scalar(select(func.coalesce(func.sum(Trabajo.total), 0)).where(
            Trabajo.empleado_id == empleado.id)) or 0))
        datos["pagado"] = Decimal(str(db.session.scalar(select(func.coalesce(func.sum(PagoEmpleado.monto), 0)).where(
            PagoEmpleado.empleado_id == empleado.id)) or 0))
        if empleado.finca_id:
            datos["actividades"] = db.session.scalars(select(ActividadCultivo).where(
                ActividadCultivo.finca_id == empleado.finca_id, ActividadCultivo.estado == "pendiente",
                ActividadCultivo.fecha <= date.today() + timedelta(days=14)).order_by(ActividadCultivo.fecha)).unique().all()
    datos["tareas"] = db.session.scalars(select(Alerta).where(
        Alerta.empresa_id == current_user.empresa_id, Alerta.estado == "pendiente",
        Alerta.asignado_id == current_user.id).order_by(Alerta.fecha)).unique().all()
    return render_template("trabajador/panel.html", **datos)
