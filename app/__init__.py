"""La Mesada · Sistema de Gestión Agrícola — fábrica de la aplicación Flask."""
import logging
import os

from flask import Flask, g, render_template, request, url_for
from flask_login import current_user
from flask_wtf.csrf import CSRFError

from .config import Config
from .extensions import csrf, db, login_manager


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config_class)
    if app.config["SECRET_KEY"] == "cambiar-esta-clave-en-produccion" and not app.config.get("TESTING"):
        app.logger.warning("SECRET_KEY por defecto: definí SECRET_KEY en el archivo .env antes de usar en producción.")
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from . import models  # noqa: F401  (registra modelos)

    _registrar_blueprints(app)
    _registrar_contexto(app)
    _registrar_errores(app)
    _registrar_seguridad(app)

    from .cli import registrar_comandos
    registrar_comandos(app)

    if not app.debug and not app.testing:
        logging.basicConfig(level=logging.INFO)
        _log_a_archivo(app)
    return app


def _log_a_archivo(app):
    """Los errores inesperados quedan guardados en logs/errores.log para poder diagnosticarlos."""
    from logging.handlers import RotatingFileHandler
    try:
        carpeta = os.path.join(os.path.dirname(app.root_path), "logs")
        os.makedirs(carpeta, exist_ok=True)
        manejador = RotatingFileHandler(os.path.join(carpeta, "errores.log"), maxBytes=1_000_000, backupCount=3,
                                        encoding="utf-8")
        manejador.setLevel(logging.ERROR)
        manejador.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        app.logger.addHandler(manejador)
    except OSError:
        pass


def _registrar_blueprints(app):
    from .crud import bp as crud_bp
    from .routes.admin import bp as admin_bp
    from .routes.alertas import bp as alertas_bp
    from .routes.auth import bp as auth_bp
    from .routes.calendario import bp as calendario_bp
    from .routes.compras import bp as compras_bp
    from .routes.configuracion import bp as configuracion_bp
    from .routes.cuentas import bp as cuentas_bp
    from .routes.dashboard import bp as dashboard_bp
    from .routes.documentos import bp as documentos_bp
    from .routes.finanzas import bp as finanzas_bp
    from .routes.fincas import bp as fincas_bp
    from .routes.inventario import bp as inventario_bp
    from .routes.mapa import bp as mapa_bp
    from .routes.rentabilidad import bp as rentabilidad_bp
    from .routes.reportes import bp as reportes_bp
    from .routes.trabajador import bp as trabajador_bp
    from .routes.ventas import bp as ventas_bp

    for bp in (auth_bp, dashboard_bp, crud_bp, fincas_bp, ventas_bp, compras_bp, cuentas_bp, inventario_bp,
               finanzas_bp, rentabilidad_bp, reportes_bp, calendario_bp, alertas_bp, documentos_bp,
               configuracion_bp, admin_bp, trabajador_bp, mapa_bp):
        app.register_blueprint(bp)


def _registrar_contexto(app):
    from .utils.formato import registrar_filtros
    from .utils.permisos import puede
    from .routes.menu import menu_para

    registrar_filtros(app)

    @app.context_processor
    def contexto_global():
        from .services import alertas
        datos = {"APP_NOMBRE": app.config["APP_NOMBRE"], "APP_SUBTITULO": app.config["APP_SUBTITULO"],
                 "puede": puede}
        if current_user.is_authenticated:
            empresa = current_user.empresa
            datos["empresa"] = empresa
            datos["menu"] = menu_para(current_user)
            datos["logo_url"] = _logo_url(empresa)
            datos["alertas_pendientes"] = alertas.cantidad() if empresa else 0
        else:
            datos["logo_url"] = url_for("static", filename="img/logo_lamesada.png")
        return datos


def _logo_url(empresa):
    if empresa and empresa.logo:
        if empresa.logo.startswith("img/"):
            return url_for("static", filename=empresa.logo)
        return url_for("configuracion.logo", empresa_id=empresa.id)
    return url_for("static", filename="img/logo_lamesada.png")


def _registrar_errores(app):
    @app.errorhandler(403)
    def prohibido(e):
        return render_template("errors/error.html", codigo=403, titulo="Sin permiso",
                               mensaje="No tenés permiso para ver esta sección."), 403

    @app.errorhandler(404)
    def no_encontrado(e):
        return render_template("errors/error.html", codigo=404, titulo="No encontrado",
                               mensaje="La página o el registro que buscás no existe."), 404

    @app.errorhandler(413)
    def muy_grande(e):
        return render_template("errors/error.html", codigo=413, titulo="Archivo muy grande",
                               mensaje="El archivo supera el tamaño máximo permitido."), 413

    @app.errorhandler(CSRFError)
    def csrf_error(e):
        return render_template("errors/error.html", codigo=400, titulo="Formulario vencido",
                               mensaje="El formulario venció o no es válido. Volvé atrás, recargá la página e "
                                       "intentá de nuevo."), 400

    @app.errorhandler(500)
    def error_interno(e):
        app.logger.error("Error 500 en %s %s: %r", request.method, request.path,
                         getattr(e, "original_exception", e), exc_info=getattr(e, "original_exception", None))
        db.session.rollback()
        return render_template("errors/error.html", codigo=500, titulo="Error inesperado",
                               mensaje="Ocurrió un error. Ya quedó registrado; intentá de nuevo en unos minutos."), 500


def _registrar_seguridad(app):
    PUBLICOS = {"auth.login", "auth.raiz", "static"}

    @app.before_request
    def requerir_login():
        """Todas las rutas requieren sesión, salvo el login y los archivos estáticos."""
        if request.endpoint is None or request.endpoint in PUBLICOS:
            return None
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        return None

    @app.after_request
    def cabeceras(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "SAMEORIGIN"
        resp.headers["Referrer-Policy"] = "same-origin"
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://server.arcgisonline.com https://services.arcgisonline.com "
            "https://tile.openstreetmap.org; "
            "font-src 'self'; connect-src 'self'; frame-ancestors 'self'; form-action 'self'; base-uri 'self'")
        if request.endpoint and request.endpoint != "static" and current_user.is_authenticated:
            resp.headers["Cache-Control"] = "no-store"
        return resp
