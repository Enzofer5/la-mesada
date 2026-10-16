"""Configuración: datos de la empresa, logo, usuarios y permisos, historial de actividades."""
import os
import uuid

from flask import (Blueprint, abort, current_app, flash, redirect, render_template, request, send_from_directory,
                   url_for)
from flask_login import current_user
from sqlalchemy import select

from ..extensions import db
from ..models import Empresa, Finca, HistorialActividad, Rol, Usuario
from ..services import auditoria
from ..services.tenant import consulta, empresa_id
from ..utils.fechas import parse_fecha
from ..utils.permisos import requiere_permiso
from ..utils.validacion import clave_segura, cuit_valido, email_valido, normalizar_cuit

bp = Blueprint("configuracion", __name__, url_prefix="/configuracion")
ROLES_EMPRESA = ["propietario", "encargado", "trabajador"]


@bp.route("/")
def index():
    return render_template("configuracion/index.html")


# ------------------------------------------------------------------ empresa y logo
@bp.route("/empresa", methods=["GET", "POST"])
@requiere_permiso("empresa", "editar")
def empresa():
    emp = db.session.get(Empresa, empresa_id())
    errores = {}
    if request.method == "POST":
        f = request.form
        nombre = (f.get("nombre") or "").strip()[:120]
        if not nombre:
            errores["nombre"] = "El nombre es obligatorio."
        cuit = (f.get("cuit") or "").strip()
        if cuit and not cuit_valido(cuit):
            errores["cuit"] = "CUIT inválido."
        email = (f.get("email") or "").strip().lower()[:120]
        if email and not email_valido(email):
            errores["email"] = "Email inválido."
        logo = request.files.get("logo")
        extension = None
        if logo and logo.filename:
            extension = logo.filename.rsplit(".", 1)[-1].lower() if "." in logo.filename else ""
            if extension not in ("png", "jpg", "jpeg", "webp"):
                errores["logo"] = "El logo debe ser PNG, JPG o WEBP."
        if not errores:
            emp.nombre = nombre
            emp.cuit = normalizar_cuit(cuit) if cuit else None
            emp.email = email or None
            emp.telefono = (f.get("telefono") or "").strip()[:30] or None
            emp.direccion = (f.get("direccion") or "").strip()[:150] or None
            emp.localidad = (f.get("localidad") or "").strip()[:80] or None
            if extension:
                carpeta = os.path.join(current_app.config["UPLOAD_FOLDER"], "logos")
                os.makedirs(carpeta, exist_ok=True)
                archivo = f"{emp.id}_{uuid.uuid4().hex[:8]}.{extension}"
                logo.save(os.path.join(carpeta, archivo))
                emp.logo = archivo
            auditoria.registrar("empresa", "editar", auditoria.frase("editar", "los datos de la empresa"), emp.id)
            db.session.commit()
            flash("Datos de la empresa actualizados.", "exito")
            return redirect(url_for("configuracion.index"))
    return render_template("configuracion/empresa.html", emp=emp, errores=errores)


@bp.route("/logo/<int:empresa_id>")
def logo(empresa_id):
    emp = db.session.get(Empresa, empresa_id)
    if emp is None or not emp.logo or (current_user.empresa_id != emp.id and current_user.rol_codigo != "superadmin"):
        abort(404)
    return send_from_directory(os.path.join(current_app.config["UPLOAD_FOLDER"], "logos"), emp.logo)


# ------------------------------------------------------------------ usuarios
def _roles():
    return db.session.scalars(select(Rol).where(Rol.codigo.in_(ROLES_EMPRESA)).order_by(Rol.id)).all()


@bp.route("/usuarios")
@requiere_permiso("usuarios")
def usuarios():
    lista = db.session.scalars(select(Usuario).where(Usuario.empresa_id == empresa_id())
                               .order_by(Usuario.activo.desc(), Usuario.nombre)).unique().all()
    return render_template("configuracion/usuarios.html", usuarios=lista)


@bp.route("/usuarios/nuevo", methods=["GET", "POST"])
@bp.route("/usuarios/<int:usuario_id>", methods=["GET", "POST"])
@requiere_permiso("usuarios", "editar")
def usuario_form(usuario_id=None):
    usuario = None
    if usuario_id:
        usuario = db.session.get(Usuario, usuario_id)
        if usuario is None or usuario.empresa_id != empresa_id():
            abort(404)
    fincas = db.session.scalars(consulta(Finca).order_by(Finca.nombre)).unique().all()
    roles = _roles()
    errores = {}
    if request.method == "POST":
        f = request.form
        nombre = (f.get("nombre") or "").strip()[:100]
        email = (f.get("email") or "").strip().lower()[:120]
        rol = next((r for r in roles if str(r.id) == f.get("rol_id")), None)
        clave = f.get("clave") or ""
        if not nombre:
            errores["nombre"] = "Obligatorio."
        if not email_valido(email):
            errores["email"] = "Email inválido."
        else:
            otro = db.session.scalar(select(Usuario).where(Usuario.email == email))
            if otro and (usuario is None or otro.id != usuario.id):
                errores["email"] = "Ya existe un usuario con ese email."
        if rol is None:
            errores["rol_id"] = "Elegí el rol."
        if (usuario is None or clave) and not clave_segura(clave):
            errores["clave"] = "Mínimo 8 caracteres, con letras y números."
        activo = f.get("activo") == "1"
        if usuario and usuario.id == current_user.id and (not activo or (rol and rol.codigo != "propietario")):
            errores["rol_id"] = "No podés quitarte el rol de propietario ni desactivarte a vos mismo."
        if not errores:
            nuevo = usuario is None
            if nuevo:
                usuario = Usuario(empresa_id=empresa_id())
                db.session.add(usuario)
            usuario.nombre, usuario.email, usuario.rol_id = nombre, email, rol.id
            if usuario.activo and not activo:
                import secrets
                usuario.token_sesion = secrets.token_hex(16)  # cierra su sesión
            usuario.activo = activo
            if clave:
                usuario.set_password(clave)
            ids = {int(x) for x in f.getlist("fincas") if x.isdigit()}
            usuario.fincas = [fi for fi in fincas if fi.id in ids]
            db.session.flush()
            auditoria.registrar("usuarios", "crear" if nuevo else "editar",
                                auditoria.frase("crear" if nuevo else "editar", f"el usuario {usuario.nombre} ({rol.nombre})"),
                                usuario.id)
            db.session.commit()
            flash("Usuario guardado.", "exito")
            return redirect(url_for("configuracion.usuarios"))
    return render_template("configuracion/usuario_form.html", usuario=usuario, fincas=fincas, roles=roles,
                           errores=errores, valores=request.form if request.method == "POST" else None)


# ------------------------------------------------------------------ historial
@bp.route("/historial")
@requiere_permiso("historial")
def historial():
    stmt = select(HistorialActividad).where(HistorialActividad.empresa_id == empresa_id()).order_by(
        HistorialActividad.fecha_hora.desc())
    args = request.args
    if args.get("usuario", "").isdigit():
        stmt = stmt.where(HistorialActividad.usuario_id == int(args["usuario"]))
    if args.get("modulo"):
        stmt = stmt.where(HistorialActividad.modulo == args["modulo"][:40])
    if args.get("accion"):
        stmt = stmt.where(HistorialActividad.accion == args["accion"][:20])
    if parse_fecha(args.get("desde")):
        stmt = stmt.where(HistorialActividad.fecha_hora >= parse_fecha(args["desde"]))
    if parse_fecha(args.get("hasta")):
        from datetime import datetime, time
        stmt = stmt.where(HistorialActividad.fecha_hora <= datetime.combine(parse_fecha(args["hasta"]), time.max))
    paginacion = db.paginate(stmt, page=max(args.get("pagina", 1, type=int), 1), per_page=40, error_out=False)
    usuarios_ = db.session.scalars(select(Usuario).where(Usuario.empresa_id == empresa_id())
                                   .order_by(Usuario.nombre)).unique().all()
    modulos = db.session.scalars(select(HistorialActividad.modulo).where(
        HistorialActividad.empresa_id == empresa_id()).distinct().order_by(HistorialActividad.modulo)).all()
    return render_template("configuracion/historial.html", paginacion=paginacion, usuarios=usuarios_, modulos=modulos,
                           args=args)
