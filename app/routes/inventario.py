"""Stock actual de insumos."""
from decimal import Decimal

from flask import Blueprint, render_template, request
from sqlalchemy import or_

from ..extensions import db
from ..models import CATEGORIAS_INSUMO, Insumo
from ..services import exportar
from ..services.tenant import consulta
from ..utils.permisos import CREAR, puede, requiere_permiso

bp = Blueprint("inventario", __name__, url_prefix="/inventario")


@bp.route("/")
@requiere_permiso("inventario")
def stock():
    categoria = request.args.get("categoria", "")
    q = (request.args.get("q") or "").strip()[:60]
    stmt = consulta(Insumo).where(Insumo.estado == "activo").order_by(Insumo.categoria, Insumo.nombre)
    if categoria in dict(CATEGORIAS_INSUMO):
        stmt = stmt.where(Insumo.categoria == categoria)
    if q:
        stmt = stmt.where(or_(Insumo.nombre.ilike(f"%{q}%"), Insumo.tipo.ilike(f"%{q}%")))
    insumos = db.session.scalars(stmt).unique().all()
    if request.args.get("bajo") == "1":
        insumos = [i for i in insumos if i.stock_minimo and i.stock < i.stock_minimo]
    if request.args.get("exportar") in ("csv", "xlsx", "pdf"):
        filas = [[i.nombre, dict(CATEGORIAS_INSUMO).get(i.categoria), i.unidad.abreviatura, i.stock, i.stock_minimo,
                  i.costo_promedio, i.stock * i.costo_promedio] for i in insumos]
        return exportar.respuesta(request.args["exportar"], "Stock de insumos",
                                  ["Insumo", "Categoría", "Unidad", "Stock", "Mínimo", "Costo promedio", "Valor"], filas)
    valor = sum((i.stock * i.costo_promedio for i in insumos), Decimal("0"))
    return render_template("inventario/stock.html", insumos=insumos, categorias=CATEGORIAS_INSUMO,
                           categoria=categoria, q=q, valor=valor, puede_crear=puede("insumos", CREAR),
                           bajo=request.args.get("bajo") == "1")
