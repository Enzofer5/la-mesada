"""Aislamiento multi-empresa y alcance por fincas.

TODAS las consultas de negocio pasan por estas funciones: filtran por la empresa del usuario logueado y, para
encargados y trabajadores, por las fincas que tienen asignadas.
"""
from flask import abort, g, has_request_context
from flask_login import current_user
from sqlalchemy import or_, select

from ..extensions import db


def usuario_actual():
    if "usuario_forzado" in g:
        return g.usuario_forzado
    if has_request_context() and current_user and current_user.is_authenticated:
        return current_user
    return None


def empresa_id():
    """Empresa en uso. En comandos (seed) se fija con usar_empresa()."""
    if "empresa_forzada" in g:
        return g.empresa_forzada
    usuario = usuario_actual()
    return usuario.empresa_id if usuario else None


def usar_empresa(empresa_id_, usuario=None):
    """Para scripts y comandos: fija la empresa (y opcionalmente el usuario) del contexto."""
    g.empresa_forzada = empresa_id_
    if usuario is not None:
        g.usuario_forzado = usuario


def fincas_permitidas():
    """None = todas las fincas de la empresa. Lista = sólo esas fincas."""
    usuario = usuario_actual()
    if usuario is None or usuario.rol_codigo in ("propietario", "superadmin"):
        return None
    if usuario.rol_codigo == "trabajador":
        from ..models import Empleado
        emp = db.session.scalar(select(Empleado).where(Empleado.usuario_id == usuario.id))
        return [emp.finca_id] if emp and emp.finca_id else []
    return [f.id for f in usuario.fincas]


def consulta(modelo):
    """SELECT base del modelo filtrado por empresa."""
    return select(modelo).where(modelo.empresa_id == empresa_id())


def filtrar_fincas(stmt, columna, incluir_generales=True):
    ids = fincas_permitidas()
    if ids is None:
        return stmt
    if incluir_generales:
        return stmt.where(or_(columna.in_(ids or [-1]), columna.is_(None)))
    return stmt.where(columna.in_(ids or [-1]))


def finca_permitida(finca_id, permitir_general=True):
    if finca_id is None:
        return permitir_general
    ids = fincas_permitidas()
    return ids is None or finca_id in ids


def obtener_o_404(modelo, id_, finca_attr="finca_id"):
    obj = db.session.get(modelo, id_)
    if obj is None or getattr(obj, "empresa_id", None) != empresa_id():
        abort(404)
    if finca_attr and hasattr(obj, finca_attr) and not finca_permitida(getattr(obj, finca_attr)):
        abort(403)
    return obj


def pertenece(modelo, id_):
    """True si el id existe y es de la empresa actual (para validar ids recibidos)."""
    if id_ is None:
        return True
    obj = db.session.get(modelo, id_)
    return obj is not None and obj.empresa_id == empresa_id()
