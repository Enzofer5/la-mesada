"""Calendario agrícola."""
import calendar as cal
from datetime import date

from flask import Blueprint, jsonify, render_template, request

from ..services import calendario as svc
from ..services import filtros
from ..utils.fechas import parse_fecha
from ..utils.formato import MESES
from ..utils.permisos import requiere_permiso
from .comun import opciones_filtros

bp = Blueprint("calendario", __name__, url_prefix="/calendario")


def _mes(args):
    hoy = date.today()
    try:
        anio = int(args.get("anio", hoy.year))
        mes = int(args.get("mes", hoy.month))
        if not (1 <= mes <= 12 and 1990 <= anio <= 2100):
            raise ValueError
    except ValueError:
        anio, mes = hoy.year, hoy.month
    return anio, mes


@bp.route("/")
@requiere_permiso("calendario")
def index():
    anio, mes = _mes(request.args)
    f = filtros.leer(request.args)
    desde = date(anio, mes, 1)
    hasta = date(anio, mes, cal.monthrange(anio, mes)[1])
    tipos = [t for t in request.args.getlist("tipo") if t in svc.TIPOS] or None
    eventos = svc.eventos(desde, hasta, f.get("finca"), f.get("cultivo"), f.get("campana"), tipos)
    por_dia = {}
    for e in eventos:
        por_dia.setdefault(e["fecha"], []).append(e)
    semanas = cal.Calendar(firstweekday=0).monthdatescalendar(anio, mes)
    anterior = (anio - 1, 12) if mes == 1 else (anio, mes - 1)
    siguiente = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
    return render_template("calendario/index.html", anio=anio, mes=mes, nombre_mes=MESES[mes], semanas=semanas,
                           por_dia=por_dia, eventos=eventos, anterior=anterior, siguiente=siguiente, hoy=date.today(),
                           f=f, opciones=opciones_filtros(), tipos=svc.TIPOS, tipos_sel=tipos or [])


@bp.route("/eventos.json")
@requiere_permiso("calendario")
def eventos_json():
    desde = parse_fecha(request.args.get("desde")) or date.today().replace(day=1)
    hasta = parse_fecha(request.args.get("hasta")) or desde.replace(day=cal.monthrange(desde.year, desde.month)[1])
    if (hasta - desde).days > 400:
        hasta = desde.replace(year=desde.year + 1)
    f = filtros.leer(request.args)
    return jsonify(svc.eventos(desde, hasta, f.get("finca"), f.get("cultivo"), f.get("campana")))
