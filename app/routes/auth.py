"""Ingreso, salida y cambio de contraseña."""
from datetime import datetime, timedelta
from urllib.parse import urlparse

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import select

from ..extensions import db, login_manager
from ..models import Usuario
from ..services import auditoria
from ..utils.permisos import pagina_inicio
from ..utils.validacion import clave_segura

bp = Blueprint("auth", __name__)


@login_manager.user_loader
def cargar_usuario(identificador):
    try:
        uid, token = identificador.split(":", 1)
        usuario = db.session.get(Usuario, int(uid))
    except (ValueError, TypeError):
        return None
    if usuario is None or usuario.token_sesion != token:
        return None
    return usuario


def _destino_seguro(destino):
    if not destino:
        return None
    partes = urlparse(destino)
    if partes.netloc or partes.scheme or not destino.startswith("/"):
        return None
    return destino


@bp.route("/")
def raiz():
    if current_user.is_authenticated:
        return redirect(url_for(pagina_inicio(current_user)))
    return redirect(url_for("auth.login"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(pagina_inicio(current_user)))
    email = ""
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()[:120]
        clave = request.form.get("clave") or ""
        usuario = db.session.scalar(select(Usuario).where(Usuario.email == email))
        ahora = datetime.now()
        if usuario and usuario.bloqueado_hasta and usuario.bloqueado_hasta > ahora:
            minutos = int((usuario.bloqueado_hasta - ahora).total_seconds() // 60) + 1
            flash(f"Usuario bloqueado por intentos fallidos. Probá de nuevo en {minutos} minutos.", "error")
        elif usuario and usuario.check_password(clave) and usuario.is_active:
            usuario.intentos_fallidos = 0
            usuario.bloqueado_hasta = None
            usuario.ultimo_acceso = ahora
            session.clear()
            login_user(usuario, remember=bool(request.form.get("recordar")))
            session.permanent = True
            auditoria.registrar("auth", "login", f"{usuario.nombre} ingresó al sistema", usuario.id)
            db.session.commit()
            return redirect(_destino_seguro(request.args.get("next")) or url_for(pagina_inicio(usuario)))
        else:
            if usuario:
                usuario.intentos_fallidos += 1
                if usuario.intentos_fallidos >= current_app.config["MAX_INTENTOS_LOGIN"]:
                    usuario.bloqueado_hasta = ahora + timedelta(minutes=current_app.config["MINUTOS_BLOQUEO"])
                    usuario.intentos_fallidos = 0
                db.session.commit()
            flash("Email o contraseña incorrectos.", "error")
    return render_template("auth/login.html", email=email)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    session.clear()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/mi-cuenta/clave", methods=["GET", "POST"])
@login_required
def cambiar_clave():
    errores = {}
    if request.method == "POST":
        actual = request.form.get("actual") or ""
        nueva = request.form.get("nueva") or ""
        repetir = request.form.get("repetir") or ""
        if not current_user.check_password(actual):
            errores["actual"] = "La contraseña actual no es correcta."
        if not clave_segura(nueva):
            errores["nueva"] = "Mínimo 8 caracteres, con letras y números."
        if nueva != repetir:
            errores["repetir"] = "Las contraseñas no coinciden."
        if not errores:
            current_user.set_password(nueva)
            auditoria.registrar("usuarios", "editar", f"{current_user.nombre} cambió su contraseña", current_user.id)
            db.session.commit()
            login_user(current_user)  # renueva la sesión con el nuevo token
            flash("Contraseña actualizada.", "exito")
            return redirect(url_for(pagina_inicio(current_user)))
    return render_template("auth/clave.html", errores=errores)
