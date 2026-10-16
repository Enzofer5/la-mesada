"""Rentabilidad y costo de producción."""
from flask import Blueprint, render_template, request

from ..services import filtros
from ..services import rentabilidad as svc
from ..utils.permisos import requiere_permiso
from .comun import opciones_filtros

bp = Blueprint("rentabilidad", __name__, url_prefix="/rentabilidad")


@bp.route("/")
@requiere_permiso("rentabilidad")
def index():
    f = filtros.leer(request.args, por_defecto_campana=True)
    agrupar = request.args.get("agrupar", "cultivo")
    if agrupar not in svc.AGRUPACIONES:
        agrupar = "cultivo"
    prorratear = request.args.get("prorratear") == "1"
    filas, total = svc.rentabilidad(f, agrupar, prorratear)
    costos = svc.costo_produccion(f, prorratear)
    return render_template("rentabilidad/index.html", f=f, descripcion=filtros.descripcion(f),
                           opciones=opciones_filtros(), filas=filas, total=total, costos=costos, agrupar=agrupar,
                           agrupaciones=svc.NOMBRES_AGRUPACION, prorratear=prorratear, query=filtros.a_query(f))
