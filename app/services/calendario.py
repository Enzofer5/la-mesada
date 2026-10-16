"""Eventos del calendario agrícola (siembras, aplicaciones, trabajos, riegos, cosechas, vencimientos, pagos,
mantenimientos, tareas)."""
from collections import defaultdict

from flask import url_for
from sqlalchemy import func, select

from ..extensions import db
from ..models import (ActividadCultivo, Alerta, AplicacionAgroquimico, AplicacionFertilizante, Cosecha, CuentaPagar,
                      Documento, Maquina, PagoEmpleado, PagoProveedor, Riego, Siembra, Trabajo, Venta)
from ..utils.formato import numero
from .tenant import empresa_id, fincas_permitidas

TIPOS = {
    "siembra": "Siembras",
    "cosecha": "Cosechas",
    "cosecha_estimada": "Cosechas estimadas",
    "aplicacion": "Aplicaciones",
    "actividad": "Actividades",
    "riego": "Riegos",
    "trabajo": "Trabajos",
    "vencimiento": "Vencimientos",
    "pago": "Pagos",
    "mantenimiento": "Mantenimientos",
    "tarea": "Tareas",
}


def eventos(desde, hasta, finca=None, cultivo=None, campana=None, tipos=None):
    eid = empresa_id()
    ids = fincas_permitidas()
    salida = []
    tipos = set(tipos or TIPOS.keys())

    def filtrar(stmt, modelo, fecha_col, con_cultivo=True, con_finca=True):
        stmt = stmt.where(modelo.empresa_id == eid, fecha_col >= desde, fecha_col <= hasta)
        if con_finca:
            if finca:
                stmt = stmt.where(modelo.finca_id == finca)
            if ids is not None:
                stmt = stmt.where(modelo.finca_id.in_(ids or [-1]))
        if con_cultivo and hasattr(modelo, "cultivo_id"):
            if cultivo:
                stmt = stmt.where(modelo.cultivo_id == cultivo)
            if campana and hasattr(modelo, "campana_id"):
                stmt = stmt.where(modelo.campana_id == campana)
        return stmt

    def add(fecha, tipo, titulo, url, detalle=""):
        salida.append({"fecha": fecha.isoformat(), "tipo": tipo, "titulo": titulo, "detalle": detalle, "url": url})

    solo_generales = not (cultivo or campana)

    if "siembra" in tipos:
        for s in db.session.scalars(filtrar(select(Siembra), Siembra, Siembra.fecha_siembra)).unique():
            add(s.fecha_siembra, "siembra", f"Siembra {s.cultivo.nombre}" + (" (pendiente)" if s.estado == "planificada" else ""), url_for("crud.detalle", key="siembras", id=s.id),
                f"{s.finca.nombre} · {s.superficie} ha")
    if "cosecha_estimada" in tipos:
        stmt = filtrar(select(Siembra).where(Siembra.estado.in_(["en_curso", "planificada"])), Siembra,
                       Siembra.fecha_cosecha_estimada)
        for s in db.session.scalars(stmt).unique():
            add(s.fecha_cosecha_estimada, "cosecha_estimada", f"Cosecha prevista {s.cultivo.nombre}",
                url_for("crud.nuevo", key="cosechas", siembra_id=s.id), s.finca.nombre)
    if "cosecha" in tipos:
        for c in db.session.scalars(filtrar(select(Cosecha), Cosecha, Cosecha.fecha)).unique():
            add(c.fecha, "cosecha", f"Cosecha {c.cultivo.nombre}", url_for("crud.detalle", key="cosechas", id=c.id),
                f"{c.finca.nombre} · {c.cantidad} {c.unidad.abreviatura}")
    if "aplicacion" in tipos:
        for modelo, key in ((AplicacionFertilizante, "aplicaciones_fertilizantes"),
                            (AplicacionAgroquimico, "aplicaciones_agroquimicos")):
            for a in db.session.scalars(filtrar(select(modelo), modelo, modelo.fecha)).unique():
                add(a.fecha, "aplicacion", f"{a.insumo.nombre}", url_for("crud.detalle", key=key, id=a.id),
                    a.finca.nombre)
    if "actividad" in tipos:
        for a in db.session.scalars(filtrar(select(ActividadCultivo), ActividadCultivo, ActividadCultivo.fecha)).unique():
            add(a.fecha, "actividad", a.tipo.replace("_", " ").capitalize() + (" (pendiente)" if a.estado == "pendiente" else ""),
                url_for("crud.detalle", key="actividades", id=a.id), a.finca.nombre)
    if "riego" in tipos:
        for r in db.session.scalars(filtrar(select(Riego), Riego, Riego.fecha)).unique():
            add(r.fecha, "riego", f"Riego {numero(r.horas, 'auto')} h", url_for("crud.detalle", key="riegos", id=r.id), r.finca.nombre)
    if "trabajo" in tipos:  # agrupados por día y finca para no llenar el calendario
        stmt = filtrar(select(Trabajo.fecha, Trabajo.finca_id, func.count(Trabajo.id)).group_by(
            Trabajo.fecha, Trabajo.finca_id), Trabajo, Trabajo.fecha)
        from ..models import Finca
        nombres = {f.id: f.nombre for f in db.session.scalars(select(Finca).where(Finca.empresa_id == eid)).unique()}
        for fecha, finca_id, n in db.session.execute(stmt):
            add(fecha, "trabajo", f"{n} trabajo{'s' if n > 1 else ''}",
                url_for("crud.listar", key="trabajos", finca=finca_id, desde=fecha.isoformat(), hasta=fecha.isoformat()),
                nombres.get(finca_id, ""))
    if solo_generales and "vencimiento" in tipos:
        stmt = select(CuentaPagar).where(CuentaPagar.empresa_id == eid, CuentaPagar.vencimiento >= desde,
                                         CuentaPagar.vencimiento <= hasta)
        if finca:
            stmt = stmt.where(CuentaPagar.finca_id == finca)
        for c in db.session.scalars(stmt).unique():
            if ids is None or c.finca_id in (ids or []) or c.finca_id is None:
                add(c.vencimiento, "vencimiento", f"Vence {c.proveedor.razon_social}",
                    url_for("crud.detalle", key="cuentas_pagar", id=c.id), f"$ {c.pendiente:,.0f}".replace(",", "."))
        stmt = filtrar(select(Venta).where(Venta.fecha_vencimiento_cobro.is_not(None)), Venta,
                       Venta.fecha_vencimiento_cobro, con_cultivo=False)
        for v in db.session.scalars(stmt).unique():
            if v.saldo > 0:
                add(v.fecha_vencimiento_cobro, "vencimiento", f"Cobro {v.cliente.nombre}",
                    url_for("ventas.detalle", venta_id=v.id), f"$ {v.saldo:,.0f}".replace(",", "."))
        stmt = select(Documento).where(Documento.empresa_id == eid, Documento.fecha_vencimiento >= desde,
                                       Documento.fecha_vencimiento <= hasta)
        for d in db.session.scalars(stmt).unique():
            add(d.fecha_vencimiento, "vencimiento", f"Vence doc. {d.nombre}",
                url_for("documentos.listar", entidad=d.entidad, entidad_id=d.entidad_id))
    if solo_generales and "pago" in tipos:
        stmt = filtrar(select(PagoEmpleado), PagoEmpleado, PagoEmpleado.fecha, con_cultivo=False)
        agrupado = defaultdict(lambda: [0, 0])
        for p in db.session.scalars(stmt).unique():
            agrupado[p.fecha][0] += 1
            agrupado[p.fecha][1] += p.monto
        for fecha, (n, total) in agrupado.items():
            add(fecha, "pago", f"{n} pago{'s' if n > 1 else ''} a empleados",
                url_for("crud.listar", key="pagos_empleados", desde=fecha.isoformat(), hasta=fecha.isoformat()),
                f"$ {total:,.0f}".replace(",", "."))
        if ids is None:
            stmt = select(PagoProveedor).where(PagoProveedor.empresa_id == eid, PagoProveedor.fecha >= desde,
                                               PagoProveedor.fecha <= hasta)
            for p in db.session.scalars(stmt).unique():
                add(p.fecha, "pago", f"Pago a {p.cuenta.proveedor.razon_social}",
                    url_for("crud.detalle", key="cuentas_pagar", id=p.cuenta_id), f"$ {p.monto:,.0f}".replace(",", "."))
    if solo_generales and "mantenimiento" in tipos:
        stmt = select(Maquina).where(Maquina.empresa_id == eid, Maquina.proximo_mantenimiento_fecha >= desde,
                                     Maquina.proximo_mantenimiento_fecha <= hasta)
        for m in db.session.scalars(stmt).unique():
            add(m.proximo_mantenimiento_fecha, "mantenimiento", f"Mantenimiento {m.nombre}",
                url_for("crud.detalle", key="maquinaria", id=m.id))
    if solo_generales and "tarea" in tipos:
        stmt = select(Alerta).where(Alerta.empresa_id == eid, Alerta.fecha >= desde, Alerta.fecha <= hasta)
        if finca:
            stmt = stmt.where(Alerta.finca_id == finca)
        for a in db.session.scalars(stmt).unique():
            if ids is None or a.finca_id is None or a.finca_id in ids:
                add(a.fecha, "tarea", a.titulo + (" ✓" if a.estado == "resuelta" else ""),
                    url_for("crud.detalle", key="alertas", id=a.id))
    salida.sort(key=lambda e: (e["fecha"], e["tipo"]))
    return salida
