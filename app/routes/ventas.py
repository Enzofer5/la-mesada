"""Ventas (cabecera + renglones) y sus cobros."""
from datetime import date, timedelta
from decimal import Decimal

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import METODOS_PAGO, DetalleVenta, Ingreso, Venta
from ..services import auditoria, exportar
from ..services import opciones as ops
from ..services import ventas as svc
from ..services.tenant import consulta, empresa_id, filtrar_fincas, obtener_o_404
from ..utils.fechas import parse_fecha
from ..utils.permisos import CREAR, EDITAR, ELIMINAR, VER, puede, requiere_permiso
from ..utils.validacion import ErrorNegocio, parse_decimal
from ..crud.modulos import CALIDADES

bp = Blueprint("ventas", __name__, url_prefix="/ventas")

FORMAS_PAGO = [("contado", "Contado"), ("transferencia", "Transferencia"), ("cheque", "Cheque"),
               ("echeq", "E-cheq"), ("cuenta_corriente", "Cuenta corriente / a plazo")]
METODOS_COBRO = [m for m in METODOS_PAGO if m[0] != "cuenta_corriente"]
ESTADOS_PAGO = [("pendiente", "Pendiente"), ("parcial", "Parcial"), ("cobrada", "Cobrada")]


def _opciones():
    return {"clientes": ops.clientes(), "fincas": ops.fincas(), "campanas": ops.campanas(),
            "cultivos": ops.cultivos(), "unidades": ops.unidades(), "lotes": ops.lotes(), "calidades": CALIDADES,
            "formas_pago": FORMAS_PAGO, "metodos_cobro": METODOS_COBRO}


def _filtrar(stmt, args):
    for clave, col in (("cliente", Venta.cliente_id), ("finca", Venta.finca_id), ("campana", Venta.campana_id)):
        if args.get(clave, "").isdigit():
            stmt = stmt.where(col == int(args[clave]))
    if args.get("cultivo", "").isdigit():
        stmt = stmt.where(Venta.id.in_(select(DetalleVenta.venta_id).where(
            DetalleVenta.cultivo_id == int(args["cultivo"]))))
    if parse_fecha(args.get("desde")):
        stmt = stmt.where(Venta.fecha >= parse_fecha(args["desde"]))
    if parse_fecha(args.get("hasta")):
        stmt = stmt.where(Venta.fecha <= parse_fecha(args["hasta"]))
    cobrado = (select(func.coalesce(func.sum(Ingreso.monto), 0)).where(Ingreso.venta_id == Venta.id,
                                                                       Ingreso.estado != "rechazado")
               .correlate(Venta).scalar_subquery())
    estado = args.get("estado")
    if estado == "pendiente":
        stmt = stmt.where(cobrado == 0, Venta.total > 0)
    elif estado == "parcial":
        stmt = stmt.where(cobrado > 0, cobrado < Venta.total)
    elif estado == "cobrada":
        stmt = stmt.where(cobrado >= Venta.total)
    elif estado == "con_saldo":
        stmt = stmt.where(cobrado < Venta.total)
    return stmt


@bp.route("/")
@requiere_permiso("ventas")
def listar():
    args = request.args
    hay_filtro = any(args.get(k) for k in ("cliente", "finca", "campana", "cultivo", "desde", "hasta", "estado", "buscar"))
    base = filtrar_fincas(consulta(Venta), Venta.finca_id, incluir_generales=False)
    stmt = _filtrar(base, args).order_by(Venta.fecha.desc(), Venta.id.desc())
    if args.get("exportar") in ("csv", "xlsx", "pdf"):
        ventas = db.session.scalars(stmt.limit(20000)).unique().all()
        encabezados = ["N°", "Fecha", "Cliente", "Finca", "Productos", "Total", "Cobrado", "Saldo", "Estado"]
        filas = [[v.id, v.fecha, v.cliente.nombre, v.finca.nombre,
                  ", ".join(f"{d.cultivo.nombre} {d.cantidad:.2f} {d.unidad.abreviatura}" for d in v.detalles),
                  v.total, v.cobrado, v.saldo, v.estado_pago] for v in ventas]
        return exportar.respuesta(args["exportar"], "Ventas", encabezados, filas)
    paginacion, total = None, None
    if hay_filtro:
        paginacion = db.paginate(stmt, page=max(args.get("pagina", 1, type=int), 1),
                                 per_page=current_app.config["POR_PAGINA"], error_out=False)
        total = db.session.scalar(_filtrar(base, args).with_only_columns(func.sum(Venta.total)).order_by(None))
    return render_template("ventas/list.html", paginacion=paginacion, total=total, args=args, o=_opciones(),
                           estados=ESTADOS_PAGO + [("con_saldo", "Con saldo a cobrar")], hay_filtro=hay_filtro)


def _leer_formulario(venta):
    """Lee cabecera y renglones. Devuelve (renglones, errores). Valida ids contra las opciones permitidas."""
    o = _opciones()
    validos = {k: {str(x[0]) for x in o[k]} for k in ("clientes", "fincas", "campanas", "cultivos", "unidades", "lotes")}
    errores = []
    f = request.form
    if f.get("cliente_id") not in validos["clientes"]:
        errores.append("Elegí el cliente.")
    if f.get("finca_id") not in validos["fincas"] and not (venta.id and f.get("finca_id") == str(venta.finca_id)):
        errores.append("Elegí la finca.")
    if f.get("campana_id") and f.get("campana_id") not in validos["campanas"]:
        errores.append("Campaña no válida.")
    fecha = parse_fecha(f.get("fecha"))
    if not fecha:
        errores.append("Fecha inválida.")
    if f.get("forma_pago") not in dict(FORMAS_PAGO):
        errores.append("Forma de pago no válida.")
    try:
        flete = parse_decimal(f.get("costo_flete")) or Decimal("0")
    except ValueError:
        flete = Decimal("0")
        errores.append("Costo de flete inválido.")
    if not errores:
        venta.cliente_id = int(f["cliente_id"])
        venta.finca_id = int(f["finca_id"])
        venta.campana_id = int(f["campana_id"]) if f.get("campana_id") else None
        venta.fecha = fecha
        venta.forma_pago = f["forma_pago"]
        venta.fecha_vencimiento_cobro = parse_fecha(f.get("fecha_vencimiento_cobro"))
        venta.comprobante = (f.get("comprobante") or "").strip()[:40] or None
        venta.transporte = (f.get("transporte") or "").strip()[:120] or None
        venta.costo_flete = flete
        venta.flete_a_cargo = "vendedor" if f.get("flete_a_cargo") == "vendedor" else "comprador"
        venta.observaciones = (f.get("observaciones") or "").strip()[:5000] or None
    renglones = []
    listas = zip(f.getlist("cultivo_id"), f.getlist("unidad_id"), f.getlist("cantidad"), f.getlist("precio_unitario"),
                 f.getlist("calidad"), f.getlist("lote_id"))
    for n, (cultivo, unidad, cantidad, precio, calidad, lote) in enumerate(listas, start=1):
        if not (cultivo or cantidad or precio):
            continue
        try:
            cant, prec = parse_decimal(cantidad), parse_decimal(precio)
        except ValueError:
            errores.append(f"Renglón {n}: número inválido.")
            continue
        if cultivo not in validos["cultivos"] or unidad not in validos["unidades"] or not cant or prec is None:
            errores.append(f"Renglón {n}: completá cultivo, unidad, cantidad y precio.")
            continue
        if lote and lote not in validos["lotes"]:
            errores.append(f"Renglón {n}: lote no válido.")
            continue
        renglones.append({"cultivo_id": int(cultivo), "unidad_id": int(unidad), "cantidad": cant,
                          "precio_unitario": prec, "calidad": calidad if calidad in dict(CALIDADES) else None,
                          "lote_id": int(lote) if lote else None})
    if not renglones and not errores:
        errores.append("Cargá al menos un producto vendido.")
    return renglones, errores


def _renglones_desde_form():
    f = request.form
    return [{"cultivo_id": c, "unidad_id": u, "cantidad": q, "precio_unitario": p, "calidad": cal, "lote_id": l}
            for c, u, q, p, cal, l in zip(f.getlist("cultivo_id"), f.getlist("unidad_id"), f.getlist("cantidad"),
                                           f.getlist("precio_unitario"), f.getlist("calidad"), f.getlist("lote_id"))]


@bp.route("/nueva", methods=["GET", "POST"])
@requiere_permiso("ventas", CREAR)
def nuevo():
    venta = Venta(empresa_id=empresa_id(), fecha=date.today(), campana_id=ops.campana_activa_id(),
                  finca_id=ops.finca_unica_id(), forma_pago="transferencia", flete_a_cargo="comprador",
                  costo_flete=0, usuario_id=current_user.id)
    if request.args.get("cliente_id", "").isdigit():
        venta.cliente_id = int(request.args["cliente_id"])
    if request.method == "POST":
        renglones, errores = _leer_formulario(venta)
        if not errores:
            try:
                svc.guardar_venta(venta, renglones, True, cobrar_ahora=request.form.get("cobrar_ahora") == "1",
                                  metodo_cobro=request.form.get("metodo_cobro") or "efectivo")
                auditoria.registrar("ventas", "crear", auditoria.frase(
                    "crear", f"una venta a {venta.cliente.nombre} por $ {venta.total:,.0f}".replace(",", ".")), venta.id)
                db.session.commit()
                flash("Venta registrada.", "exito")
                return redirect(url_for("ventas.detalle", venta_id=venta.id))
            except ErrorNegocio as e:
                db.session.rollback()
                errores = [str(e)]
        for e in errores:
            flash(e, "error")
        return render_template("ventas/form.html", venta=venta, renglones=_renglones_desde_form(), o=_opciones(),
                               nueva=True), 400
    return render_template("ventas/form.html", venta=venta, renglones=[], o=_opciones(), nueva=True)


@bp.route("/<int:venta_id>/editar", methods=["GET", "POST"])
@requiere_permiso("ventas", EDITAR)
def editar(venta_id):
    venta = obtener_o_404(Venta, venta_id)
    if request.method == "POST":
        renglones, errores = _leer_formulario(venta)
        if not errores:
            try:
                svc.guardar_venta(venta, renglones, False)
                auditoria.registrar("ventas", "editar", auditoria.frase(
                    "editar", f"la venta #{venta.id} (total $ {venta.total:,.0f})".replace(",", ".")), venta.id)
                db.session.commit()
                flash("Venta actualizada.", "exito")
                return redirect(url_for("ventas.detalle", venta_id=venta.id))
            except ErrorNegocio as e:
                db.session.rollback()
                errores = [str(e)]
        db.session.rollback()
        for e in errores:
            flash(e, "error")
        venta = obtener_o_404(Venta, venta_id)
        return render_template("ventas/form.html", venta=venta, renglones=_renglones_desde_form(), o=_opciones(),
                               nueva=False), 400
    renglones = [{"cultivo_id": str(d.cultivo_id), "unidad_id": str(d.unidad_id), "cantidad": str(d.cantidad.normalize()),
                  "precio_unitario": str(d.precio_unitario.normalize()), "calidad": d.calidad or "",
                  "lote_id": str(d.lote_id or "")} for d in venta.detalles]
    return render_template("ventas/form.html", venta=venta, renglones=renglones, o=_opciones(), nueva=False)


@bp.route("/<int:venta_id>")
@requiere_permiso("ventas")
def detalle(venta_id):
    venta = obtener_o_404(Venta, venta_id)
    return render_template("ventas/detail.html", venta=venta, metodos=METODOS_COBRO, hoy=date.today(),
                           puede_cobrar=puede("ingresos", CREAR), puede_editar=puede("ventas", EDITAR),
                           puede_eliminar=puede("ventas", ELIMINAR),
                           estados_ingreso=[("acreditado", "Acreditado"), ("a_depositar", "A depositar")])


@bp.route("/<int:venta_id>/cobro", methods=["POST"])
@requiere_permiso("ingresos", CREAR)
def cobrar(venta_id):
    venta = obtener_o_404(Venta, venta_id)
    try:
        monto = parse_decimal(request.form.get("monto"))
        fecha = parse_fecha(request.form.get("fecha")) or date.today()
        metodo = request.form.get("metodo_pago")
        if metodo not in dict(METODOS_COBRO):
            raise ErrorNegocio("Elegí el medio de cobro.")
        estado = "a_depositar" if request.form.get("estado") == "a_depositar" else "acreditado"
        svc.registrar_cobro(venta, fecha, monto or 0, metodo, estado, (request.form.get("observaciones") or "")[:500])
        auditoria.registrar("ingresos", "crear", auditoria.frase(
            "cobro", f"la venta #{venta.id} por $ {monto:,.0f}".replace(",", ".")), venta.id)
        db.session.commit()
        flash("Cobro registrado.", "exito")
    except (ErrorNegocio, ValueError) as e:
        db.session.rollback()
        flash(str(e) if isinstance(e, ErrorNegocio) else "Monto inválido.", "error")
    return redirect(url_for("ventas.detalle", venta_id=venta_id))


@bp.route("/<int:venta_id>/eliminar", methods=["POST"])
@requiere_permiso("ventas", ELIMINAR)
def eliminar(venta_id):
    venta = obtener_o_404(Venta, venta_id)
    try:
        descripcion = f"la venta #{venta.id} a {venta.cliente.nombre}"
        svc.eliminar_venta(venta)
        auditoria.registrar("ventas", "eliminar", auditoria.frase("eliminar", descripcion), venta_id)
        db.session.commit()
        flash("Venta eliminada.", "exito")
        return redirect(url_for("ventas.listar"))
    except (ErrorNegocio, IntegrityError) as e:
        db.session.rollback()
        flash(str(e) if isinstance(e, ErrorNegocio) else "No se pudo eliminar la venta.", "error")
        return redirect(url_for("ventas.detalle", venta_id=venta_id))
