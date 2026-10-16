"""Administración del sistema (multi-empresa): alta de nuevas explotaciones/clientes y su propietario."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy import func, select

from ..extensions import db
from ..models import Empresa, Finca, Usuario
from ..services import auditoria
from ..services.seed import crear_empresa
from ..utils.permisos import requiere_permiso
from ..utils.validacion import clave_segura, email_valido

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/empresas")
@requiere_permiso("admin")
def empresas():
    lista = db.session.scalars(select(Empresa).order_by(Empresa.nombre)).all()
    usuarios = dict(db.session.execute(select(Usuario.empresa_id, func.count(Usuario.id)).group_by(Usuario.empresa_id)).all())
    fincas = dict(db.session.execute(select(Finca.empresa_id, func.count(Finca.id)).group_by(Finca.empresa_id)).all())
    return render_template("admin/empresas.html", empresas=lista, usuarios=usuarios, fincas=fincas)


@bp.route("/empresas/nueva", methods=["GET", "POST"])
@requiere_permiso("admin", "crear")
def nueva():
    errores = {}
    if request.method == "POST":
        f = request.form
        nombre = (f.get("nombre") or "").strip()[:120]
        propietario = (f.get("propietario") or "").strip()[:100]
        email = (f.get("email") or "").strip().lower()[:120]
        clave = f.get("clave") or ""
        if not nombre:
            errores["nombre"] = "Obligatorio."
        if not propietario:
            errores["propietario"] = "Obligatorio."
        if not email_valido(email):
            errores["email"] = "Email inválido."
        elif db.session.scalar(select(Usuario).where(Usuario.email == email)):
            errores["email"] = "Ya existe un usuario con ese email."
        if not clave_segura(clave):
            errores["clave"] = "Mínimo 8 caracteres, con letras y números."
        if not errores:
            empresa, _ = crear_empresa(nombre, propietario, email, clave,
                                       localidad=(f.get("localidad") or "").strip()[:80] or None)
            auditoria.registrar("admin", "crear", f"Alta de la empresa {nombre}", empresa.id)
            db.session.commit()
            flash(f"Empresa «{nombre}» creada. El propietario ya puede ingresar con {email}.", "exito")
            return redirect(url_for("admin.empresas"))
    return render_template("admin/empresa_form.html", errores=errores, valores=request.form)


@bp.route("/empresas/<int:empresa_id>/estado", methods=["POST"])
@requiere_permiso("admin", "editar")
def cambiar_estado(empresa_id):
    empresa = db.session.get(Empresa, empresa_id) or abort(404)
    empresa.activa = not empresa.activa
    auditoria.registrar("admin", "editar", f"Empresa {empresa.nombre} {'activada' if empresa.activa else 'suspendida'}",
                        empresa.id)
    db.session.commit()
    flash(f"Empresa {'activada' if empresa.activa else 'suspendida'}.", "exito")
    return redirect(url_for("admin.empresas"))
