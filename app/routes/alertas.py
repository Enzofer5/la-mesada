"""Centro de alertas."""
from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..extensions import db
from ..models import Alerta
from ..services import alertas as svc
from ..services import auditoria
from ..services.tenant import obtener_o_404
from ..utils.permisos import EDITAR, puede, requiere_permiso

bp = Blueprint("alertas", __name__, url_prefix="/alertas")

NOMBRES = {"siembra": "Siembras pendientes", "cosecha": "Próximas cosechas", "pago": "Pagos a proveedores", "cobro": "Cobros", "stock": "Stock",
           "mantenimiento": "Maquinaria", "documento": "Documentación", "tarea": "Tareas pendientes"}


@bp.route("/")
def index():
    alertas = svc.calcular()
    tipo = request.args.get("tipo")
    if tipo in NOMBRES:
        alertas = [a for a in alertas if a["tipo"] == tipo]
    conteo = {}
    for a in svc.calcular():
        conteo[a["tipo"]] = conteo.get(a["tipo"], 0) + 1
    return render_template("alertas/index.html", alertas=alertas, nombres=NOMBRES, conteo=conteo, tipo=tipo,
                           puede_tareas=puede("alertas", EDITAR))


@bp.route("/tareas/<int:tarea_id>/resolver", methods=["POST"])
@requiere_permiso("alertas", EDITAR)
def resolver(tarea_id):
    tarea = obtener_o_404(Alerta, tarea_id)
    tarea.estado = "resuelta"
    auditoria.registrar("alertas", "editar", auditoria.frase("editar", f"la tarea «{tarea.titulo}» (resuelta)"), tarea.id)
    db.session.commit()
    flash("Tarea marcada como resuelta.", "exito")
    return redirect(request.referrer if request.referrer and request.referrer.startswith(request.host_url)
                    else url_for("alertas.index"))
