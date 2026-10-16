"""Opciones para los <select> de los formularios, siempre filtradas por empresa y fincas permitidas.

Cada opción es una tupla (valor, etiqueta, padre, extra):
  * padre: valor del campo del que depende (ej. la finca de un lote) para filtrar en el navegador.
  * extra: diccionario de campos a autocompletar al elegirla (ej. la siembra completa finca/lote/cultivo).
"""
from sqlalchemy import select

from ..extensions import db
from ..models import (Campana, CategoriaGasto, Cliente, Cultivo, Empleado, Finca, Insumo, Lote, Maquina, Proveedor,
                      Siembra, UnidadMedida, Usuario)
from .tenant import consulta, empresa_id, fincas_permitidas


def _todas(stmt):
    return db.session.scalars(stmt).unique().all()


def fincas(solo_activas=True, todas=False):
    stmt = consulta(Finca).order_by(Finca.nombre)
    if solo_activas:
        stmt = stmt.where(Finca.estado == "activa")
    ids = fincas_permitidas()
    if ids is not None and not todas:
        stmt = stmt.where(Finca.id.in_(ids or [-1]))
    return [(f.id, f.nombre, None, None) for f in _todas(stmt)]


def lotes():
    stmt = consulta(Lote).where(Lote.estado == "activo").order_by(Lote.nombre)
    ids = fincas_permitidas()
    if ids is not None:
        stmt = stmt.where(Lote.finca_id.in_(ids or [-1]))
    return [(l.id, f"{l.nombre} ({l.superficie} ha)", l.finca_id, None) for l in _todas(stmt)]


def campanas():
    stmt = consulta(Campana).order_by(Campana.fecha_inicio.desc())
    return [(c.id, c.nombre + (" (activa)" if c.estado == "activa" else ""), None, None) for c in _todas(stmt)]


def cultivos(solo_activos=True):
    stmt = consulta(Cultivo).order_by(Cultivo.nombre)
    if solo_activos:
        stmt = stmt.where(Cultivo.estado == "activo")
    return [(c.id, f"{c.nombre} ({c.unidad.abreviatura})", None, {"unidad_id": c.unidad_id}) for c in _todas(stmt)]


def unidades():
    stmt = consulta(UnidadMedida).where(UnidadMedida.activa.is_(True)).order_by(UnidadMedida.nombre)
    return [(u.id, f"{u.nombre} ({u.abreviatura})", None, None) for u in _todas(stmt)]


def categorias_gasto():
    stmt = consulta(CategoriaGasto).where(CategoriaGasto.activa.is_(True)).order_by(CategoriaGasto.orden,
                                                                                    CategoriaGasto.nombre)
    return [(c.id, c.nombre, None, None) for c in _todas(stmt)]


def proveedores():
    stmt = consulta(Proveedor).where(Proveedor.estado == "activo").order_by(Proveedor.razon_social)
    return [(p.id, p.razon_social, None, None) for p in _todas(stmt)]


def clientes():
    stmt = consulta(Cliente).where(Cliente.estado == "activo").order_by(Cliente.nombre)
    return [(c.id, c.nombre, None, None) for c in _todas(stmt)]


def empleados(solo_activos=True):
    stmt = consulta(Empleado).order_by(Empleado.apellido, Empleado.nombre)
    if solo_activos:
        stmt = stmt.where(Empleado.estado == "activo")
    ids = fincas_permitidas()
    if ids is not None:
        from sqlalchemy import or_
        stmt = stmt.where(or_(Empleado.finca_id.in_(ids or [-1]), Empleado.finca_id.is_(None)))
    return [(e.id, f"{e.apellido}, {e.nombre} · {e.tipo}", None,
             {"modalidad": e.modalidad_pago, "precio_unitario": str(e.tarifa) if e.tarifa else None})
            for e in _todas(stmt)]


def maquinas():
    stmt = consulta(Maquina).where(Maquina.estado != "vendida").order_by(Maquina.nombre)
    return [(m.id, str(m), None, {"costo_hora": str(m.costo_hora) if m.costo_hora else None}) for m in _todas(stmt)]


def insumos(categoria=None):
    stmt = consulta(Insumo).where(Insumo.estado == "activo").order_by(Insumo.nombre)
    if categoria:
        stmt = stmt.where(Insumo.categoria == categoria)
    salida = []
    for i in _todas(stmt):
        etiqueta = (f"{i.nombre}{' (propia)' if i.propia else ''} · stock {i.stock:.2f} "
                    f"{i.unidad.abreviatura}").replace(".", ",")
        salida.append((i.id, etiqueta, None, None))
    return salida


def semillas_propias():
    stmt = consulta(Insumo).where(Insumo.estado == "activo", Insumo.categoria == "semilla",
                                  Insumo.propia.is_(True)).order_by(Insumo.nombre)
    return [(i.id, f"{i.nombre} · stock {i.stock:.2f} {i.unidad.abreviatura}".replace(".", ","), None, None)
            for i in _todas(stmt)]


def siembras_en_curso():
    stmt = consulta(Siembra).where(Siembra.estado.in_(["en_curso", "cosechada"])).order_by(
        Siembra.fecha_siembra.desc())
    ids = fincas_permitidas()
    if ids is not None:
        stmt = stmt.where(Siembra.finca_id.in_(ids or [-1]))
    salida = []
    for s in _todas(stmt)[:300]:
        salida.append((s.id, str(s), None, {
            "finca_id": s.finca_id, "lote_id": s.lote_id, "campana_id": s.campana_id,
            "cultivo_id": s.cultivo_id, "superficie": str(s.superficie),
            "unidad_id": s.cultivo.unidad_id if s.cultivo else None,
        }))
    return salida


def usuarios():
    stmt = select(Usuario).where(Usuario.empresa_id == empresa_id(), Usuario.activo.is_(True)).order_by(
        Usuario.nombre)
    return [(u.id, u.nombre, None, None) for u in _todas(stmt)]


def campana_activa():
    return db.session.scalar(
        consulta(Campana).where(Campana.estado == "activa").order_by(Campana.fecha_inicio.desc()).limit(1))


def campana_activa_id():
    c = campana_activa()
    return c.id if c else None


def finca_unica_id():
    """Si el usuario maneja una sola finca, se preselecciona."""
    opciones = fincas()
    return opciones[0][0] if len(opciones) == 1 else None
