"""Tablero de cada finca."""
from flask import Blueprint, render_template, request

from ..models import Finca
from ..services import dashboard as svc
from ..services import filtros
from ..services.tenant import obtener_o_404
from ..utils.permisos import requiere_permiso
from .comun import opciones_filtros

bp = Blueprint("fincas", __name__, url_prefix="/fincas")


@bp.route("/<int:finca_id>")
@requiere_permiso("fincas")
def dashboard(finca_id):
    finca = obtener_o_404(Finca, finca_id, "id")
    f = filtros.leer(request.args, por_defecto_campana=True)
    return render_template("fincas/dashboard.html", finca=finca, f=f, descripcion=filtros.descripcion(f),
                           opciones=opciones_filtros(), datos=svc.tablero_finca(finca, f))
