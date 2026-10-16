"""Roles y permisos por módulo y acción.

La matriz está en código (y no en tablas) a propósito: es corta, se versiona con la aplicación y es fácil de
auditar. Para cambiar lo que puede hacer un rol, se edita PERMISOS.
"""
from functools import wraps

from flask import abort
from flask_login import current_user

VER, CREAR, EDITAR, ELIMINAR = "ver", "crear", "editar", "eliminar"
TODO = {VER, CREAR, EDITAR, ELIMINAR}
CARGA = {VER, CREAR, EDITAR, ELIMINAR}  # los encargados cargan y corrigen lo de sus fincas
LECTURA = {VER}

MODULOS_OPERATIVOS = [
    "siembras", "actividades", "riegos", "movimientos", "aplicaciones_fertilizantes",
    "aplicaciones_agroquimicos", "compras", "uso_maquinaria", "combustibles", "trabajos",
    "pagos_empleados", "cosechas", "ventas", "ingresos", "gastos", "documentos", "alertas",
]
MODULOS_CATALOGO_ENCARGADO = ["empleados", "clientes", "proveedores", "insumos", "maquinaria", "lotes"]
MODULOS_CONSULTA = [
    "dashboard", "fincas", "campanas", "cultivos", "unidades", "categorias_gasto", "inventario",
    "rentabilidad", "reportes", "calendario", "finanzas", "cuentas_pagar",
]
MODULOS_PROPIETARIO = ["usuarios", "empresa", "historial"]

PERMISOS = {
    "superadmin": {"admin": TODO},
    "propietario": {m: TODO for m in MODULOS_OPERATIVOS + MODULOS_CATALOGO_ENCARGADO + MODULOS_CONSULTA
                    + MODULOS_PROPIETARIO},
    "encargado": {
        **{m: CARGA for m in MODULOS_OPERATIVOS},
        **{m: {VER, CREAR, EDITAR} for m in MODULOS_CATALOGO_ENCARGADO},
        **{m: LECTURA for m in MODULOS_CONSULTA},
        "cuentas_pagar": {VER, CREAR, EDITAR},
    },
    "trabajador": {"mi_panel": LECTURA, "calendario": LECTURA},
}

ROLES = [
    ("superadmin", "Administrador del sistema"),
    ("propietario", "Propietario"),
    ("encargado", "Encargado"),
    ("trabajador", "Trabajador"),
]


def puede(modulo, accion=VER, usuario=None):
    usuario = usuario or current_user
    if not usuario or not usuario.is_authenticated:
        return False
    return accion in PERMISOS.get(usuario.rol_codigo, {}).get(modulo, set())


def requiere_permiso(modulo, accion=VER):
    def decorador(f):
        @wraps(f)
        def envoltura(*args, **kwargs):
            if not current_user.is_authenticated:
                from ..extensions import login_manager
                return login_manager.unauthorized()
            if not puede(modulo, accion):
                abort(403)
            return f(*args, **kwargs)
        return envoltura
    return decorador


def es_propietario(usuario=None):
    usuario = usuario or current_user
    return usuario.is_authenticated and usuario.rol_codigo == "propietario"


def pagina_inicio(usuario):
    """Pantalla a la que va cada rol después del login."""
    rol = usuario.rol_codigo
    if rol == "superadmin":
        return "admin.empresas"
    if rol == "trabajador":
        return "trabajador.panel"
    return "dashboard.index"
