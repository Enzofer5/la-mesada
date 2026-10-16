"""Tablero general (vista del propietario y de los encargados sobre sus fincas)."""
from flask import Blueprint, render_template, request

from ..services import alertas as svc_alertas
from ..services import dashboard as svc
from ..services import filtros
from ..utils.permisos import requiere_permiso
from .comun import opciones_filtros
from .menu import ACCESOS_RAPIDOS

bp = Blueprint("dashboard", __name__)


@bp.route("/dashboard")
@requiere_permiso("dashboard")
def index():
    f = filtros.leer(request.args, por_defecto_campana=True)
    return render_template(
        "dashboard/index.html",
        f=f, descripcion=filtros.descripcion(f), opciones=opciones_filtros(),
        kpis=svc.kpis(f), graficos=svc.graficos(f), proximas=svc.proximas_cosechas(f.get("finca")),
        alertas=svc_alertas.calcular()[:6], accesos=ACCESOS_RAPIDOS, query=filtros.a_query(f),
    )
