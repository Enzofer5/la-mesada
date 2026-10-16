"""Alertas automáticas (se calculan en el momento, siempre actualizadas) + tareas cargadas a mano."""
from datetime import date, timedelta

from flask import g, url_for
from sqlalchemy import or_, select

from ..extensions import db
from ..models import ActividadCultivo, Alerta, CuentaPagar, Documento, Maquina, Siembra, Venta
from . import inventario
from .tenant import empresa_id, fincas_permitidas, usuario_actual

ORDEN_NIVEL = {"critico": 0, "alto": 1, "medio": 2, "info": 3}


def _scope(stmt, col, generales=True):
    ids = fincas_permitidas()
    if ids is None:
        return stmt
    if generales:
        return stmt.where(or_(col.in_(ids or [-1]), col.is_(None)))
    return stmt.where(col.in_(ids or [-1]))


def calcular():
    eid = empresa_id()
    hoy = date.today()
    salida = []

    def add(tipo, nivel, titulo, detalle, fecha, url):
        salida.append({"tipo": tipo, "nivel": nivel, "titulo": titulo, "detalle": detalle, "fecha": fecha, "url": url})

    # Próximas cosechas
    stmt = select(Siembra).where(Siembra.empresa_id == eid, Siembra.estado == "en_curso",
                                 Siembra.fecha_cosecha_estimada.is_not(None),
                                 Siembra.fecha_cosecha_estimada <= hoy + timedelta(days=15))
    for s in db.session.scalars(_scope(stmt, Siembra.finca_id, False)).unique():
        dias = (s.fecha_cosecha_estimada - hoy).days
        nivel = "alto" if dias < 0 else "medio"
        texto = f"estaba prevista hace {-dias} días" if dias < 0 else ("es hoy" if dias == 0 else f"en {dias} días")
        add("cosecha", nivel, f"Cosecha de {s.cultivo.nombre} · {s.finca.nombre}", f"La cosecha {texto}.",
            s.fecha_cosecha_estimada, url_for("crud.nuevo", key="cosechas", siembra_id=s.id))

    # Sectores marcados pendientes de siembra
    stmt = select(Siembra).where(Siembra.empresa_id == eid, Siembra.estado == "planificada",
                                 Siembra.fecha_siembra <= hoy + timedelta(days=3))
    for s in db.session.scalars(_scope(stmt, Siembra.finca_id, False)).unique():
        atrasada = s.fecha_siembra < hoy
        add("siembra", "alto" if atrasada else "medio",
            f"Siembra pendiente: {s.cultivo.nombre} {s.variedad or ''} · {s.finca.nombre}".strip(),
            f"{s.lote.nombre if s.lote else ''} · {s.superficie} ha · prevista {s.fecha_siembra:%d/%m/%Y}", s.fecha_siembra,
            url_for("mapa.index", lote=s.lote_id, campana=s.campana_id) if s.lote_id
            else url_for("crud.detalle", key="siembras", id=s.id))

    # Cuentas a pagar
    stmt = select(CuentaPagar).where(CuentaPagar.empresa_id == eid, CuentaPagar.pagado < CuentaPagar.importe,
                                     CuentaPagar.vencimiento <= hoy + timedelta(days=7))
    for c in db.session.scalars(_scope(stmt, CuentaPagar.finca_id)).unique():
        vencida = c.vencimiento < hoy
        add("pago", "critico" if vencida else "alto",
            f"{'Pago vencido' if vencida else 'Pago próximo'}: {c.proveedor.razon_social}",
            f"$ {c.pendiente:,.0f} · vence {c.vencimiento:%d/%m/%Y}".replace(",", "."), c.vencimiento,
            url_for("crud.detalle", key="cuentas_pagar", id=c.id))

    # Cobros vencidos
    stmt = select(Venta).where(Venta.empresa_id == eid, Venta.fecha_vencimiento_cobro.is_not(None),
                               Venta.fecha_vencimiento_cobro <= hoy + timedelta(days=3))
    for v in db.session.scalars(_scope(stmt, Venta.finca_id, False)).unique():
        if v.saldo > 0:
            add("cobro", "alto" if v.fecha_vencimiento_cobro < hoy else "medio", f"Cobro pendiente: {v.cliente.nombre}",
                f"Saldo $ {v.saldo:,.0f} · venta #{v.id}".replace(",", "."), v.fecha_vencimiento_cobro,
                url_for("ventas.detalle", venta_id=v.id))

    # Stock bajo
    for i in inventario.insumos_bajo_stock():
        add("stock", "alto" if i.stock <= 0 else "medio", f"Stock bajo: {i.nombre}",
            f"Quedan {i.stock:.2f} {i.unidad.abreviatura} (mínimo {i.stock_minimo:.2f})".replace(".", ","), hoy,
            url_for("crud.detalle", key="insumos", id=i.id))

    # Mantenimiento de maquinaria
    stmt = select(Maquina).where(Maquina.empresa_id == eid, Maquina.estado.in_(["operativa", "en_reparacion"]))
    for m in db.session.scalars(_scope(stmt, Maquina.finca_id)).unique():
        faltan = m.horas_para_mantenimiento
        if faltan is not None and faltan <= 20:
            add("mantenimiento", "alto" if faltan <= 0 else "medio", f"Service de {m.nombre}",
                f"{'Pasado por' if faltan < 0 else 'Faltan'} {abs(faltan):.0f} horas.", hoy,
                url_for("crud.detalle", key="maquinaria", id=m.id))
        elif m.proximo_mantenimiento_fecha and m.proximo_mantenimiento_fecha <= hoy + timedelta(days=7):
            add("mantenimiento", "medio", f"Mantenimiento de {m.nombre}",
                f"Programado para el {m.proximo_mantenimiento_fecha:%d/%m/%Y}.", m.proximo_mantenimiento_fecha,
                url_for("crud.detalle", key="maquinaria", id=m.id))

    # Documentación por vencer
    stmt = select(Documento).where(Documento.empresa_id == eid, Documento.fecha_vencimiento.is_not(None),
                                   Documento.fecha_vencimiento <= hoy + timedelta(days=30))
    for d in db.session.scalars(_scope(stmt, Documento.finca_id)).unique():
        add("documento", "alto" if d.fecha_vencimiento < hoy else "medio", f"Documento por vencer: {d.nombre}",
            f"Vence el {d.fecha_vencimiento:%d/%m/%Y}.", d.fecha_vencimiento,
            url_for("documentos.listar", entidad=d.entidad, entidad_id=d.entidad_id))

    # Tareas y actividades pendientes
    usuario = usuario_actual()
    stmt = select(Alerta).where(Alerta.empresa_id == eid, Alerta.estado == "pendiente",
                                Alerta.fecha <= hoy + timedelta(days=7))
    if usuario and usuario.rol_codigo != "propietario":
        stmt = stmt.where(or_(Alerta.asignado_id == usuario.id, Alerta.asignado_id.is_(None)))
    for a in db.session.scalars(_scope(stmt, Alerta.finca_id)).unique():
        nivel = {"alta": "alto", "media": "medio", "baja": "info"}.get(a.prioridad, "medio")
        add("tarea", "alto" if a.fecha < hoy else nivel, a.titulo,
            (a.finca.nombre + " · " if a.finca else "") + f"para el {a.fecha:%d/%m/%Y}", a.fecha,
            url_for("crud.detalle", key="alertas", id=a.id))
    stmt = select(ActividadCultivo).where(ActividadCultivo.empresa_id == eid, ActividadCultivo.estado == "pendiente",
                                          ActividadCultivo.fecha <= hoy + timedelta(days=3))
    for a in db.session.scalars(_scope(stmt, ActividadCultivo.finca_id, False)).unique():
        add("tarea", "alto" if a.fecha < hoy else "medio", f"Actividad pendiente: {a.tipo.replace('_', ' ')}",
            f"{a.finca.nombre} · {a.fecha:%d/%m/%Y}", a.fecha, url_for("crud.detalle", key="actividades", id=a.id))

    salida.sort(key=lambda x: (ORDEN_NIVEL[x["nivel"]], x["fecha"]))
    return salida


def cantidad():
    """Cantidad de alertas importantes (para el globo del menú). Se calcula una vez por pedido."""
    if "alertas_cantidad" not in g:
        try:
            g.alertas_cantidad = sum(1 for a in calcular() if a["nivel"] in ("critico", "alto"))
        except Exception:  # nunca romper una pantalla por las alertas
            db.session.rollback()
            g.alertas_cantidad = 0
    return g.alertas_cantidad
