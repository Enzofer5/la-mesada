"""Compras de insumos (cabecera + renglones)."""
from datetime import date, timedelta

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Compra
from ..services import auditoria, exportar
from ..services import compras as svc
from ..services import opciones as ops
from ..services.tenant import consulta, empresa_id, filtrar_fincas, obtener_o_404
from ..utils.fechas import parse_fecha
from ..utils.permisos import CREAR, EDITAR, ELIMINAR, puede, requiere_permiso
from ..utils.validacion import ErrorNegocio, parse_decimal

bp = Blueprint("compras", __name__, url_prefix="/compras")

CONDICIONES = [("contado", "Contado (pagada)"), ("cuenta_corriente", "Cuenta corriente (a pagar)")]


def _opciones():
    return {"proveedores": ops.proveedores(), "fincas": ops.fincas(), "insumos": ops.insumos(),
            "condiciones": CONDICIONES}


def _filtrar(stmt, args):
    if args.get("proveedor", "").isdigit():
        stmt = stmt.where(Compra.proveedor_id == int(args["proveedor"]))
    if args.get("finca", "").isdigit():
        stmt = stmt.where(Compra.finca_id == int(args["finca"]))
    if parse_fecha(args.get("desde")):
        stmt = stmt.where(Compra.fecha >= parse_fecha(args["desde"]))
    if parse_fecha(args.get("hasta")):
        stmt = stmt.where(Compra.fecha <= parse_fecha(args["hasta"]))
    if args.get("condicion") in dict(CONDICIONES):
        stmt = stmt.where(Compra.condicion == args["condicion"])
    return stmt


@bp.route("/")
@requiere_permiso("compras")
def listar():
    args = request.args
    base = filtrar_fincas(consulta(Compra), Compra.finca_id)
    stmt = _filtrar(base, args).order_by(Compra.fecha.desc(), Compra.id.desc())
    if args.get("exportar") in ("csv", "xlsx", "pdf"):
        compras = db.session.scalars(stmt.limit(20000)).unique().all()
        filas = [[c.id, c.fecha, c.proveedor.razon_social, c.comprobante or "",
                  ", ".join(f"{d.insumo.nombre} {d.cantidad:.2f}" for d in c.detalles), c.condicion, c.total]
                 for c in compras]
        return exportar.respuesta(args["exportar"], "Compras de insumos",
                                  ["N°", "Fecha", "Proveedor", "Comprobante", "Productos", "Condición", "Total"], filas)
    paginacion = db.paginate(stmt, page=max(args.get("pagina", 1, type=int), 1),
                             per_page=current_app.config["POR_PAGINA"], error_out=False)
    total = db.session.scalar(_filtrar(base, args).with_only_columns(func.sum(Compra.total)).order_by(None))
    return render_template("compras/list.html", paginacion=paginacion, total=total, args=args, o=_opciones())


def _leer(compra):
    o = _opciones()
    prov = {str(x[0]) for x in o["proveedores"]}
    fincas = {str(x[0]) for x in o["fincas"]}
    insumos = {str(x[0]) for x in o["insumos"]}
    f = request.form
    errores = []
    if f.get("proveedor_id") not in prov:
        errores.append("Elegí el proveedor.")
    if f.get("finca_id") and f.get("finca_id") not in fincas:
        errores.append("Finca no válida.")
    fecha = parse_fecha(f.get("fecha"))
    if not fecha:
        errores.append("Fecha inválida.")
    if f.get("condicion") not in dict(CONDICIONES):
        errores.append("Elegí la condición de pago.")
    if not errores:
        compra.proveedor_id = int(f["proveedor_id"])
        compra.finca_id = int(f["finca_id"]) if f.get("finca_id") else None
        compra.fecha = fecha
        compra.condicion = f["condicion"]
        compra.vencimiento = parse_fecha(f.get("vencimiento")) or (fecha + timedelta(days=30)
                                                                   if f["condicion"] == "cuenta_corriente" else None)
        compra.comprobante = (f.get("comprobante") or "").strip()[:40] or None
        compra.observaciones = (f.get("observaciones") or "").strip()[:5000] or None
    renglones = []
    for n, (insumo, cantidad, precio) in enumerate(zip(f.getlist("insumo_id"), f.getlist("cantidad"),
                                                        f.getlist("precio_unitario")), start=1):
        if not (insumo or cantidad or precio):
            continue
        try:
            cant, prec = parse_decimal(cantidad), parse_decimal(precio)
        except ValueError:
            errores.append(f"Renglón {n}: número inválido.")
            continue
        if insumo not in insumos or not cant or prec is None:
            errores.append(f"Renglón {n}: completá producto, cantidad y precio.")
            continue
        renglones.append({"insumo_id": int(insumo), "cantidad": cant, "precio_unitario": prec})
    if not renglones and not errores:
        errores.append("Cargá al menos un producto.")
    return renglones, errores


def _renglones_form():
    f = request.form
    return [{"insumo_id": i, "cantidad": c, "precio_unitario": p}
            for i, c, p in zip(f.getlist("insumo_id"), f.getlist("cantidad"), f.getlist("precio_unitario"))]


@bp.route("/nueva", methods=["GET", "POST"])
@requiere_permiso("compras", CREAR)
def nuevo():
    compra = Compra(empresa_id=empresa_id(), fecha=date.today(), condicion="contado", usuario_id=current_user.id,
                    finca_id=ops.finca_unica_id())
    if request.method == "POST":
        renglones, errores = _leer(compra)
        if not errores:
            try:
                svc.guardar_compra(compra, renglones, True)
                auditoria.registrar("compras", "crear", auditoria.frase(
                    "crear", f"una compra a {compra.proveedor.razon_social} por $ {compra.total:,.0f}".replace(",", ".")),
                    compra.id)
                db.session.commit()
                flash("Compra registrada. El stock ya se actualizó.", "exito")
                return redirect(url_for("compras.detalle", compra_id=compra.id))
            except ErrorNegocio as e:
                db.session.rollback()
                errores = [str(e)]
        for e in errores:
            flash(e, "error")
        return render_template("compras/form.html", compra=compra, renglones=_renglones_form(), o=_opciones(),
                               nueva=True), 400
    return render_template("compras/form.html", compra=compra, renglones=[], o=_opciones(), nueva=True)


@bp.route("/<int:compra_id>/editar", methods=["GET", "POST"])
@requiere_permiso("compras", EDITAR)
def editar(compra_id):
    compra = obtener_o_404(Compra, compra_id)
    if request.method == "POST":
        renglones, errores = _leer(compra)
        if not errores:
            try:
                svc.guardar_compra(compra, renglones, False)
                auditoria.registrar("compras", "editar", auditoria.frase("editar", f"la compra #{compra.id}"), compra.id)
                db.session.commit()
                flash("Compra actualizada.", "exito")
                return redirect(url_for("compras.detalle", compra_id=compra.id))
            except ErrorNegocio as e:
                errores = [str(e)]
        db.session.rollback()
        for e in errores:
            flash(e, "error")
        compra = obtener_o_404(Compra, compra_id)
        return render_template("compras/form.html", compra=compra, renglones=_renglones_form(), o=_opciones(),
                               nueva=False), 400
    renglones = [{"insumo_id": str(d.insumo_id), "cantidad": str(d.cantidad.normalize()),
                  "precio_unitario": str(d.precio_unitario.normalize())} for d in compra.detalles]
    return render_template("compras/form.html", compra=compra, renglones=renglones, o=_opciones(), nueva=False)


@bp.route("/<int:compra_id>")
@requiere_permiso("compras")
def detalle(compra_id):
    compra = obtener_o_404(Compra, compra_id)
    from sqlalchemy import select
    from ..models import CuentaPagar
    cuenta = db.session.scalar(select(CuentaPagar).where(CuentaPagar.origen == "compra",
                                                         CuentaPagar.origen_id == compra.id,
                                                         CuentaPagar.empresa_id == empresa_id()))
    return render_template("compras/detail.html", compra=compra, cuenta=cuenta,
                           puede_editar=puede("compras", EDITAR), puede_eliminar=puede("compras", ELIMINAR))


@bp.route("/<int:compra_id>/eliminar", methods=["POST"])
@requiere_permiso("compras", ELIMINAR)
def eliminar(compra_id):
    compra = obtener_o_404(Compra, compra_id)
    try:
        svc.eliminar_compra(compra)
        auditoria.registrar("compras", "eliminar", auditoria.frase("eliminar", f"la compra #{compra_id}"), compra_id)
        db.session.commit()
        flash("Compra eliminada y stock actualizado.", "exito")
        return redirect(url_for("compras.listar"))
    except (ErrorNegocio, IntegrityError) as e:
        db.session.rollback()
        flash(str(e) if isinstance(e, ErrorNegocio) else "No se pudo eliminar la compra.", "error")
        return redirect(url_for("compras.detalle", compra_id=compra_id))
