"""Historial de actividades: quién hizo qué, cuándo y sobre qué registro."""
from datetime import datetime

from flask import has_request_context, request

from ..extensions import db
from ..models import HistorialActividad
from .tenant import empresa_id, usuario_actual

VERBOS = {"crear": "registró", "editar": "modificó", "eliminar": "eliminó", "login": "ingresó al sistema",
          "pago": "registró un pago en", "cobro": "registró un cobro en"}


def registrar(modulo, accion, descripcion, registro_id=None):
    usuario = usuario_actual()
    ip = None
    if has_request_context():
        ip = (request.headers.get("X-Forwarded-For", request.remote_addr) or "")[:45]
    db.session.add(HistorialActividad(
        empresa_id=empresa_id() if usuario is None or usuario.empresa_id else None,
        usuario_id=usuario.id if usuario else None,
        fecha_hora=datetime.now(),
        modulo=modulo,
        accion=accion,
        registro_id=registro_id,
        descripcion=descripcion[:255],
        ip=ip,
    ))


def frase(accion, que):
    """Arma frases del tipo 'Juan registró una siembra: Papa · Finca 1'."""
    usuario = usuario_actual()
    nombre = usuario.nombre if usuario else "Sistema"
    return f"{nombre} {VERBOS.get(accion, accion)} {que}"
