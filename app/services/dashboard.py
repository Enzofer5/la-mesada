"""Indicadores y series para los tableros (general y por finca)."""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import extract, func, select

from ..extensions import db
from ..models import (ActividadCultivo, Alerta, CategoriaGasto, Cosecha, CuentaPagar, Cultivo, DetalleVenta,
                      Empleado, Finca, Gasto, Ingreso, Lote, Siembra, Trabajo, Venta, dec)
from ..utils.formato import MESES_CORTOS
from . import rentabilidad as rent
from .tenant import empresa_id, fincas_permitidas

CERO = Decimal("0")

# Paleta categórica validada (orden fijo; el color sigue a la entidad, no al ranking)
PALETA = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
VERDE_MARCA = "#3f6e3a"
ROJO_PERDIDA = "#c8423f"


def colores_cultivos():
    cultivos = db.session.scalars(select(Cultivo).where(Cultivo.empresa_id == empresa_id())
                                  .order_by(Cultivo.id)).unique().all()
    return {c.id: (c.color or PALETA[i % len(PALETA)]) for i, c in enumerate(cultivos)}


def _scope(stmt, col, finca=None):
    ids = fincas_permitidas()
    if ids is not None:
        stmt = stmt.where(col.in_(ids or [-1]))
    if finca:
        stmt = stmt.where(col == finca)
    return stmt


def superficies(finca=None):
    eid = empresa_id()
    stmt = select(func.coalesce(func.sum(Finca.superficie_total), 0), func.coalesce(func.sum(Finca.superficie_cultivable), 0),
                  func.count(Finca.id)).where(Finca.empresa_id == eid, Finca.estado == "activa")
    total, cultivable, cantidad = db.session.execute(_scope(stmt, Finca.id, finca)).one()
    stmt = select(func.coalesce(func.sum(Siembra.superficie), 0)).where(Siembra.empresa_id == eid,
                                                                         Siembra.estado == "en_curso")
    cultivada = db.session.scalar(_scope(stmt, Siembra.finca_id, finca)) or 0
    return {"fincas": cantidad, "total": dec(total), "cultivable": dec(cultivable), "cultivada": dec(cultivada),
            "libre": max(dec(cultivable) - dec(cultivada), CERO)}


def cultivos_actuales(finca=None):
    stmt = (select(Cultivo.nombre, func.sum(Siembra.superficie)).join(Cultivo, Siembra.cultivo_id == Cultivo.id)
            .where(Siembra.empresa_id == empresa_id(), Siembra.estado == "en_curso").group_by(Cultivo.nombre)
            .order_by(func.sum(Siembra.superficie).desc()))
    return [(n, dec(s)) for n, s in db.session.execute(_scope(stmt, Siembra.finca_id, finca))]


def proximas_cosechas(finca=None, limite=8):
    stmt = (select(Siembra).where(Siembra.empresa_id == empresa_id(), Siembra.estado == "en_curso",
                                  Siembra.fecha_cosecha_estimada.is_not(None))
            .order_by(Siembra.fecha_cosecha_estimada).limit(limite))
    return db.session.scalars(_scope(stmt, Siembra.finca_id, finca)).unique().all()


def produccion_por_cultivo(f):
    datos = rent.produccion_base(f)
    cultivos = {c.id: c for c in db.session.scalars(select(Cultivo).where(Cultivo.empresa_id == empresa_id())).unique()}
    agg = defaultdict(lambda: [CERO, CERO])
    for (finca, cultivo, campana), (cant, merma, sup) in datos.items():
        agg[cultivo][0] += cant
        agg[cultivo][1] += merma
    salida = []
    for cid, (cant, merma) in agg.items():
        c = cultivos.get(cid)
        if c:
            toneladas = None
            if c.unidad.tipo == "masa":
                toneladas = (cant - merma) * dec(c.unidad.factor_base) / 1000
            salida.append({"id": cid, "cultivo": c.nombre, "cantidad": cant, "merma": merma,
                           "comercializable": cant - merma, "unidad": c.unidad.abreviatura, "toneladas": toneladas})
    salida.sort(key=lambda x: x["cultivo"])
    return salida


def kpis(f):
    finca = f.get("finca")
    sup = superficies(finca)
    filas, total = rent.rentabilidad(f, "cultivo")
    ventas = sum(rent.ingresos_base(f).values(), CERO)
    produccion = produccion_por_cultivo(f)
    toneladas = sum((p["toneladas"] for p in produccion if p["toneladas"] is not None), CERO)
    stmt = select(func.count(Empleado.id)).where(Empleado.empresa_id == empresa_id(), Empleado.estado == "activo")
    empleados = db.session.scalar(_scope(stmt, Empleado.finca_id, finca)) or 0
    return {
        **sup,
        "cultivos_actuales": cultivos_actuales(finca),
        "produccion": produccion,
        "toneladas": toneladas,
        "ingresos": total["ingresos"],
        "ventas": ventas,
        "costos": total["costos"],
        "ganancia": total["ganancia"],
        "margen": total["margen"],
        "empleados": empleados,
        "por_cobrar": por_cobrar(finca),
        "por_pagar": por_pagar(finca),
    }


def por_cobrar(finca=None):
    stmt = select(Venta).where(Venta.empresa_id == empresa_id())
    ventas = db.session.scalars(_scope(stmt, Venta.finca_id, finca)).unique().all()
    return sum((v.saldo for v in ventas if v.saldo > 0), CERO)


def por_pagar(finca=None):
    stmt = select(func.coalesce(func.sum(CuentaPagar.importe - CuentaPagar.pagado), 0)).where(
        CuentaPagar.empresa_id == empresa_id(), CuentaPagar.pagado < CuentaPagar.importe)
    if finca:
        stmt = stmt.where(CuentaPagar.finca_id == finca)
    elif fincas_permitidas() is not None:
        from sqlalchemy import or_
        stmt = stmt.where(or_(CuentaPagar.finca_id.in_(fincas_permitidas() or [-1]), CuentaPagar.finca_id.is_(None)))
    return dec(db.session.scalar(stmt))


# ------------------------------------------------------------------ series para gráficos
def gastos_por_categoria(f):
    costos = rent.costos_base(f, por_categoria=True)
    cats = {c.id: c.nombre for c in db.session.scalars(select(CategoriaGasto).where(
        CategoriaGasto.empresa_id == empresa_id())).unique()}
    agg = defaultdict(Decimal)
    for clave, monto in costos.items():
        agg[clave[3]] += monto
    datos = sorted(((cats.get(k, "?"), v) for k, v in agg.items()), key=lambda x: -x[1])
    return {"labels": [d[0] for d in datos], "valores": [float(d[1]) for d in datos]}


def _cat(f):
    c = gastos_por_categoria(f)
    return c["labels"], c["valores"]


def ingresos_gastos_por_mes(f):
    eid = empresa_id()
    anio_v, mes_v = extract("year", Venta.fecha), extract("month", Venta.fecha)
    stmt = (select(anio_v, mes_v, func.sum(DetalleVenta.subtotal)).join(Venta, DetalleVenta.venta_id == Venta.id)
            .where(Venta.empresa_id == eid).group_by(anio_v, mes_v))
    stmt = rent._aplicar(stmt, f, Venta.fecha, Venta.finca_id, DetalleVenta.cultivo_id, Venta.campana_id,
                         DetalleVenta.lote_id)
    ingresos = defaultdict(Decimal)
    for a, m, v in db.session.execute(stmt):
        ingresos[(int(a), int(m))] += dec(v)
    anio_i, mes_i = extract("year", Ingreso.fecha), extract("month", Ingreso.fecha)
    stmt = (select(anio_i, mes_i, func.sum(Ingreso.monto)).where(
        Ingreso.empresa_id == eid, Ingreso.venta_id.is_(None), Ingreso.estado != "rechazado").group_by(anio_i, mes_i))
    stmt = rent._aplicar(stmt, f, Ingreso.fecha, Ingreso.finca_id, Ingreso.cultivo_id, Ingreso.campana_id,
                         Ingreso.lote_id)
    for a, m, v in db.session.execute(stmt):
        ingresos[(int(a), int(m))] += dec(v)
    anio_g, mes_g = extract("year", Gasto.fecha), extract("month", Gasto.fecha)
    stmt = select(anio_g, mes_g, func.sum(Gasto.monto)).where(Gasto.empresa_id == eid).group_by(anio_g, mes_g)
    stmt = rent._aplicar(stmt, f, Gasto.fecha, Gasto.finca_id, Gasto.cultivo_id, Gasto.campana_id, Gasto.lote_id)
    if f.get("categoria"):
        stmt = stmt.where(Gasto.categoria_id == f["categoria"])
    gastos = defaultdict(Decimal)
    for a, m, v in db.session.execute(stmt):
        gastos[(int(a), int(m))] += dec(v)
    meses = sorted(set(ingresos) | set(gastos))
    if meses:  # completar meses vacíos para que el eje sea continuo
        completos, (a, m) = [], meses[0]
        while (a, m) <= meses[-1] and len(completos) < 60:
            completos.append((a, m))
            a, m = (a + 1, 1) if m == 12 else (a, m + 1)
        meses = completos
    return {"labels": [f"{MESES_CORTOS[m]} {str(a)[2:]}" for a, m in meses],
            "ingresos": [float(ingresos.get(k, 0)) for k in meses],
            "gastos": [float(gastos.get(k, 0)) for k in meses]}


def superficie_por_cultivo(f):
    datos = rent.superficie_base(f)
    colores = colores_cultivos()
    cultivos = {c.id: c.nombre for c in db.session.scalars(select(Cultivo).where(
        Cultivo.empresa_id == empresa_id())).unique()}
    agg = defaultdict(Decimal)
    for (finca, cultivo, campana), s in datos.items():
        agg[cultivo] += s
    orden = sorted(agg.items(), key=lambda x: -x[1])
    return {"labels": [cultivos.get(k, "?") for k, _ in orden], "valores": [float(v) for _, v in orden],
            "colores": [colores.get(k, PALETA[0]) for k, _ in orden]}


def g_barras(labels, valores, nombre="", moneda=True, unidad=None, horizontal=False, color=VERDE_MARCA,
             polaridad=False, colores=None):
    serie = {"nombre": nombre, "datos": valores, "color": color}
    if polaridad:
        serie["color_negativo"] = ROJO_PERDIDA
    if colores:
        serie["colores"] = colores
    return {"tipo": "barras_h" if horizontal else "barras", "labels": labels, "series": [serie], "moneda": moneda,
            "unidad": unidad}


def g_ingresos_gastos(serie):
    return {"tipo": "linea", "labels": serie["labels"], "moneda": True, "series": [
        {"nombre": "Ingresos", "datos": serie["ingresos"], "color": PALETA[0]},
        {"nombre": "Gastos", "datos": serie["gastos"], "color": PALETA[1]}]}


def graficos(f):
    por_finca, _ = rent.rentabilidad(f, "finca")
    por_cultivo, _ = rent.rentabilidad(f, "cultivo")
    por_finca = [x for x in por_finca if not x["sin_asignar"]] + [x for x in por_finca if x["sin_asignar"]]
    produccion = [p for p in produccion_por_cultivo(f) if p["toneladas"] is not None]
    colores = colores_cultivos()
    categorias = gastos_por_categoria(f)
    superficie = superficie_por_cultivo(f)
    return {
        "gastos_categoria": g_barras(categorias["labels"], categorias["valores"], "Gastos", horizontal=True),
        "ingresos_mes": g_ingresos_gastos(ingresos_gastos_por_mes(f)),
        "ganancia_finca": g_barras([x["nombre"] for x in por_finca], [float(x["ganancia"]) for x in por_finca],
                                   "Ganancia", polaridad=True),
        "costos_finca": g_barras([x["nombre"] for x in por_finca], [float(x["costos"]) for x in por_finca], "Costos",
                                 color=PALETA[1]),
        "produccion_cultivo": g_barras([p["cultivo"] for p in produccion], [round(float(p["toneladas"]), 1) for p in produccion],
                                       "Producción comercializable", moneda=False, unidad="t",
                                       colores=[colores.get(p["id"], PALETA[0]) for p in produccion]),
        "superficie_cultivo": {"tipo": "dona", "labels": superficie["labels"], "moneda": False, "unidad": "ha",
                               "series": [{"nombre": "Hectáreas", "datos": superficie["valores"],
                                           "colores": superficie["colores"]}]},
        "rentabilidad_cultivo": {"tipo": "barras", "labels": [x["nombre"] for x in por_cultivo], "moneda": True,
                                 "series": [
                                     {"nombre": "Ingresos", "datos": [float(x["ingresos"]) for x in por_cultivo], "color": PALETA[0]},
                                     {"nombre": "Costos", "datos": [float(x["costos"]) for x in por_cultivo], "color": PALETA[1]},
                                     {"nombre": "Ganancia", "datos": [float(x["ganancia"]) for x in por_cultivo], "color": PALETA[2]},
                                 ]},
        "rankings": {"fincas": sorted([x for x in por_finca if not x["sin_asignar"]], key=lambda x: -x["ganancia"]),
                     "cultivos": sorted([x for x in por_cultivo if not x["sin_asignar"]], key=lambda x: -x["ganancia"])},
    }


# ------------------------------------------------------------------ tablero de finca
def tablero_finca(finca, f):
    f = dict(f, finca=finca.id)
    datos = kpis(f)
    siembras = db.session.scalars(select(Siembra).where(Siembra.finca_id == finca.id, Siembra.estado == "en_curso")
                                  .order_by(Siembra.fecha_siembra)).unique().all()
    estimada = defaultdict(Decimal)
    unidades = {}
    for s in siembras:
        if s.produccion_estimada:
            estimada[s.cultivo.nombre] += s.produccion_estimada
            unidades[s.cultivo.nombre] = s.cultivo.unidad.abreviatura
    lotes = []
    for lote in db.session.scalars(select(Lote).where(Lote.finca_id == finca.id).order_by(Lote.nombre)).unique():
        actual = next((s for s in siembras if s.lote_id == lote.id), None)
        lotes.append({"lote": lote, "siembra": actual})
    hoy = date.today()
    pendientes = db.session.scalars(select(ActividadCultivo).where(
        ActividadCultivo.finca_id == finca.id, ActividadCultivo.estado == "pendiente")
        .order_by(ActividadCultivo.fecha).limit(10)).unique().all()
    tareas = db.session.scalars(select(Alerta).where(
        Alerta.finca_id == finca.id, Alerta.estado == "pendiente").order_by(Alerta.fecha).limit(10)).unique().all()
    empleados = db.session.scalars(select(Empleado).where(Empleado.finca_id == finca.id, Empleado.estado == "activo")
                                   .order_by(Empleado.apellido)).unique().all()
    mano_obra_mes = db.session.scalar(select(func.coalesce(func.sum(Trabajo.total), 0)).where(
        Trabajo.finca_id == finca.id, Trabajo.fecha >= hoy.replace(day=1))) or 0
    return {
        "kpis": datos,
        "siembras": siembras,
        "estimada": [(k, v, unidades[k]) for k, v in estimada.items()],
        "lotes": lotes,
        "proximas": proximas_cosechas(finca.id),
        "pendientes": pendientes,
        "tareas": tareas,
        "empleados": empleados,
        "mano_obra_mes": dec(mano_obra_mes),
        "graficos": {"gastos_categoria": g_barras(*_cat(f), "Gastos", horizontal=True),
                     "ingresos_mes": g_ingresos_gastos(ingresos_gastos_por_mes(f))},
        "rent_cultivo": rent.rentabilidad(f, "cultivo")[0],
    }
