"""Utilidades compartidas por los controladores: opciones de filtros de análisis."""
from datetime import date

from sqlalchemy import extract, func, select

from ..extensions import db
from ..models import CategoriaGasto, Gasto
from ..services import opciones as ops
from ..services.tenant import consulta, empresa_id


def anios_disponibles():
    minimo = db.session.scalar(select(func.min(Gasto.fecha)).where(Gasto.empresa_id == empresa_id()))
    desde = minimo.year if minimo else date.today().year
    return list(range(date.today().year + 1, desde - 1, -1))


def opciones_filtros(con_categoria=False):
    datos = {
        "fincas": [(o[0], o[1]) for o in ops.fincas(solo_activas=False)],
        "cultivos": [(o[0], o[1]) for o in ops.cultivos(False)],
        "campanas": [(o[0], o[1]) for o in ops.campanas()],
        "lotes": ops.lotes(),
        "anios": anios_disponibles(),
    }
    if con_categoria:
        datos["categorias"] = [(c.id, c.nombre) for c in db.session.scalars(
            consulta(CategoriaGasto).order_by(CategoriaGasto.orden)).unique()]
    return datos
