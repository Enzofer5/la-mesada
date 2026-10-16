"""Cálculo de costos, ingresos, producción y rentabilidad.

Fuentes:
  * Costos      → tabla gastos (única fuente; los módulos generan sus gastos automáticamente).
  * Ingresos    → renglones de ventas (devengado) + otros ingresos no vinculados a ventas (no rechazados).
  * Superficie  → siembras.
  * Producción  → cosechas (cantidad, merma, superficie cosechada) en la unidad de cada cultivo.

Todas las consultas agrupan por (finca, cultivo, campaña) y luego se re-agrupan según lo que se pida.
"""
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import func, select

from ..extensions import db
from ..models import (Campana, CategoriaGasto, Cosecha, Cultivo, DetalleVenta, Finca, Gasto, Ingreso, Siembra,
                      Venta, dec)
from .tenant import empresa_id, fincas_permitidas

CERO = Decimal("0")

AGRUPACIONES = {
    "cultivo": (1,),
    "finca": (0,),
    "campana": (2,),
    "finca_cultivo": (0, 1),
    "campana_cultivo": (2, 1),
    "finca_campana_cultivo": (0, 2, 1),
}
NOMBRES_AGRUPACION = {
    "cultivo": "Por cultivo",
    "finca": "Por finca",
    "campana": "Por campaña",
    "finca_cultivo": "Por finca y cultivo",
    "campana_cultivo": "Por campaña y cultivo (comparar años)",
    "finca_campana_cultivo": "Por finca, campaña y cultivo",
}


def _aplicar(stmt, f, fecha_col, finca_col, cultivo_col, campana_col, lote_col=None, sin=()):
    if f.get("finca") and "finca" not in sin:
        stmt = stmt.where(finca_col == f["finca"])
    if f.get("cultivo") and "cultivo" not in sin:
        stmt = stmt.where(cultivo_col == f["cultivo"])
    if f.get("campana") and campana_col is not None:
        stmt = stmt.where(campana_col == f["campana"])
    if f.get("lote") and lote_col is not None and "lote" not in sin:
        stmt = stmt.where(lote_col == f["lote"])
    if f.get("desde"):
        stmt = stmt.where(fecha_col >= f["desde"])
    if f.get("hasta"):
        stmt = stmt.where(fecha_col <= f["hasta"])
    ids = fincas_permitidas()
    if ids is not None:
        stmt = stmt.where(finca_col.in_(ids or [-1]))
    return stmt


# ------------------------------------------------------------------ datos base agrupados por (finca, cultivo, campaña)
def costos_base(f, por_categoria=False, sin=()):
    cols = [Gasto.finca_id, Gasto.cultivo_id, Gasto.campana_id]
    if por_categoria:
        cols.append(Gasto.categoria_id)
    stmt = select(*cols, func.sum(Gasto.monto)).where(Gasto.empresa_id == empresa_id()).group_by(*cols)
    stmt = _aplicar(stmt, f, Gasto.fecha, Gasto.finca_id, Gasto.cultivo_id, Gasto.campana_id, Gasto.lote_id, sin)
    if f.get("categoria"):
        stmt = stmt.where(Gasto.categoria_id == f["categoria"])
    return {tuple(r[:-1]): dec(r[-1]) for r in db.session.execute(stmt)}


def ingresos_base(f, sin=()):
    salida = defaultdict(Decimal)
    stmt = (select(Venta.finca_id, DetalleVenta.cultivo_id, Venta.campana_id, func.sum(DetalleVenta.subtotal))
            .join(Venta, DetalleVenta.venta_id == Venta.id).where(Venta.empresa_id == empresa_id())
            .group_by(Venta.finca_id, DetalleVenta.cultivo_id, Venta.campana_id))
    stmt = _aplicar(stmt, f, Venta.fecha, Venta.finca_id, DetalleVenta.cultivo_id, Venta.campana_id,
                    DetalleVenta.lote_id, sin)
    for r in db.session.execute(stmt):
        salida[tuple(r[:3])] += dec(r[3])
    stmt = (select(Ingreso.finca_id, Ingreso.cultivo_id, Ingreso.campana_id, func.sum(Ingreso.monto))
            .where(Ingreso.empresa_id == empresa_id(), Ingreso.venta_id.is_(None), Ingreso.estado != "rechazado")
            .group_by(Ingreso.finca_id, Ingreso.cultivo_id, Ingreso.campana_id))
    stmt = _aplicar(stmt, f, Ingreso.fecha, Ingreso.finca_id, Ingreso.cultivo_id, Ingreso.campana_id,
                    Ingreso.lote_id, sin)
    for r in db.session.execute(stmt):
        salida[tuple(r[:3])] += dec(r[3])
    return dict(salida)


def superficie_base(f, sin=()):
    stmt = (select(Siembra.finca_id, Siembra.cultivo_id, Siembra.campana_id, func.sum(Siembra.superficie))
            .where(Siembra.empresa_id == empresa_id(), Siembra.estado != "planificada")
            .group_by(Siembra.finca_id, Siembra.cultivo_id, Siembra.campana_id))
    stmt = _aplicar(stmt, f, Siembra.fecha_siembra, Siembra.finca_id, Siembra.cultivo_id, Siembra.campana_id,
                    Siembra.lote_id, sin)
    return {tuple(r[:3]): dec(r[3]) for r in db.session.execute(stmt)}


def produccion_base(f, sin=()):
    stmt = (select(Cosecha.finca_id, Cosecha.cultivo_id, Cosecha.campana_id, func.sum(Cosecha.cantidad),
                   func.sum(Cosecha.merma + func.coalesce(Cosecha.semilla_guardada, 0)), func.sum(Cosecha.superficie))
            .where(Cosecha.empresa_id == empresa_id())
            .group_by(Cosecha.finca_id, Cosecha.cultivo_id, Cosecha.campana_id))
    stmt = _aplicar(stmt, f, Cosecha.fecha, Cosecha.finca_id, Cosecha.cultivo_id, Cosecha.campana_id,
                    Cosecha.lote_id, sin)
    return {tuple(r[:3]): (dec(r[3]), dec(r[4]), dec(r[5])) for r in db.session.execute(stmt)}


def prorratear(costos, superficies):
    """Reparte los gastos sin cultivo entre los cultivos sembrados según hectáreas.

    Claves de costos: (finca, cultivo, campaña, *extra). Un gasto de finca F sin cultivo va a los cultivos de F;
    un gasto sin finca ni cultivo, a todos. Si no hay siembras que lo reciban, queda sin asignar.
    """
    resultado = defaultdict(Decimal)
    for clave, monto in costos.items():
        finca, cultivo, campana = clave[:3]
        extra = tuple(clave[3:])
        if cultivo is not None:
            resultado[clave] += monto
            continue
        candidatos = {k: s for k, s in superficies.items()
                      if s > 0 and (finca is None or k[0] == finca) and (campana is None or k[2] == campana)}
        total = sum(candidatos.values(), CERO)
        if not candidatos:
            resultado[clave] += monto
            continue
        for k, s in candidatos.items():
            resultado[k + extra] += monto * s / total
    return dict(resultado)


def _filtrar_claves(datos, f):
    """Después de prorratear se aplican los filtros de finca y cultivo sobre el resultado."""
    salida = {}
    for clave, valor in datos.items():
        if f.get("finca") and clave[0] != f["finca"]:
            continue
        if f.get("cultivo") and clave[1] != f["cultivo"]:
            continue
        salida[clave] = valor
    return salida


def _costos(f, prorratear_generales, por_categoria=False):
    if not prorratear_generales:
        return costos_base(f, por_categoria)
    sin = ("finca", "cultivo", "lote")
    costos = prorratear(costos_base(f, por_categoria, sin=sin), superficie_base(f, sin=sin))
    return _filtrar_claves(costos, f)


# ------------------------------------------------------------------ nombres
def _nombres():
    eid = empresa_id()
    return {
        0: {x.id: x.nombre for x in db.session.scalars(select(Finca).where(Finca.empresa_id == eid)).unique()},
        1: {x.id: x for x in db.session.scalars(select(Cultivo).where(Cultivo.empresa_id == eid)).unique()},
        2: {x.id: x.nombre for x in db.session.scalars(select(Campana).where(Campana.empresa_id == eid)).unique()},
    }


SIN_NOMBRE = {0: "Sin finca (general)", 1: "Sin cultivo (estructura)", 2: "Sin campaña"}


def _div(a, b):
    if b is None or b == 0 or a is None:
        return None
    return dec(a) / dec(b)


def rentabilidad(f, agrupar="cultivo", prorratear_generales=False):
    """Filas de rentabilidad + fila de totales."""
    idx = AGRUPACIONES.get(agrupar, AGRUPACIONES["cultivo"])
    nombres = _nombres()
    costos = _costos(f, prorratear_generales)
    ingresos = ingresos_base(f)
    superficies = superficie_base(f)
    produccion = produccion_base(f)

    grupos = defaultdict(lambda: {"ingresos": CERO, "costos": CERO, "superficie": CERO, "produccion": CERO,
                                  "merma": CERO, "sup_cosechada": CERO, "cultivos": set()})

    def g(clave):
        return tuple(clave[i] for i in idx)

    for clave, v in costos.items():
        grupos[g(clave)]["costos"] += v
        if clave[1]:
            grupos[g(clave)]["cultivos"].add(clave[1])
    for clave, v in ingresos.items():
        grupos[g(clave)]["ingresos"] += v
        if clave[1]:
            grupos[g(clave)]["cultivos"].add(clave[1])
    for clave, v in superficies.items():
        grupos[g(clave)]["superficie"] += v
        grupos[g(clave)]["cultivos"].add(clave[1])
    for clave, (cant, merma, sup) in produccion.items():
        d = grupos[g(clave)]
        d["cultivos"].add(clave[1])
        d.setdefault("prod_por_cultivo", defaultdict(lambda: [CERO, CERO, CERO]))
        pc = d["prod_por_cultivo"][clave[1]]
        pc[0] += cant
        pc[1] += merma
        pc[2] += sup

    filas = []
    for clave, d in grupos.items():
        etiquetas = []
        for pos, i in enumerate(idx):
            valor = clave[pos]
            if valor is None:
                etiquetas.append(SIN_NOMBRE[i])
            else:
                obj = nombres[i].get(valor)
                etiquetas.append(obj.nombre if i == 1 and obj else (obj or "?"))
        unidad = None
        prod = merma = sup_cos = None
        cultivos = {c for c in d["cultivos"] if c}
        unidades = {nombres[1][c].unidad_id for c in cultivos if c in nombres[1]}
        if len(unidades) == 1 and cultivos:
            unidad = nombres[1][next(iter(cultivos))].unidad.abreviatura
            ppc = d.get("prod_por_cultivo", {})
            prod = sum((v[0] for v in ppc.values()), CERO)
            merma = sum((v[1] for v in ppc.values()), CERO)
            sup_cos = sum((v[2] for v in ppc.values()), CERO)
        ganancia = d["ingresos"] - d["costos"]
        comercializable = (prod - merma) if prod is not None else None
        filas.append({
            "clave": clave,
            "nombre": " · ".join(etiquetas),
            "etiquetas": etiquetas,
            "ingresos": d["ingresos"],
            "costos": d["costos"],
            "ganancia": ganancia,
            "margen": _div(ganancia, d["ingresos"]) if None not in clave else None,
            "superficie": d["superficie"],
            "costo_ha": _div(d["costos"], d["superficie"]),
            "ingreso_ha": _div(d["ingresos"], d["superficie"]),
            "ganancia_ha": _div(ganancia, d["superficie"]),
            "produccion": prod,
            "merma": merma,
            "comercializable": comercializable,
            "unidad": unidad,
            "rendimiento_ha": _div(prod, sup_cos if sup_cos else d["superficie"]) if prod else None,
            "costo_unidad": _div(d["costos"], comercializable) if comercializable else None,
            "ganancia_unidad": _div(ganancia, comercializable) if comercializable else None,
            "sin_asignar": None in clave,
        })
    filas.sort(key=lambda x: (x["sin_asignar"], -x["ganancia"]))
    tot_ing = sum((x["ingresos"] for x in filas), CERO)
    tot_cos = sum((x["costos"] for x in filas), CERO)
    tot_sup = sum((x["superficie"] for x in filas), CERO)
    total = {"nombre": "TOTAL", "ingresos": tot_ing, "costos": tot_cos, "ganancia": tot_ing - tot_cos,
             "margen": _div(tot_ing - tot_cos, tot_ing), "superficie": tot_sup, "costo_ha": _div(tot_cos, tot_sup),
             "ingreso_ha": _div(tot_ing, tot_sup), "ganancia_ha": _div(tot_ing - tot_cos, tot_sup)}
    return filas, total


def costo_produccion(f, prorratear_generales=False):
    """Desglose del costo de producción por cultivo y categoría (con costo por ha y por unidad)."""
    nombres = _nombres()
    categorias = {c.id: c for c in db.session.scalars(select(CategoriaGasto).where(
        CategoriaGasto.empresa_id == empresa_id())).unique()}
    costos = _costos(f, prorratear_generales, por_categoria=True)
    superficies = superficie_base(f)
    produccion = produccion_base(f)

    bloques = defaultdict(lambda: {"categorias": defaultdict(Decimal), "total": CERO})
    for (finca, cultivo, campana, categoria), monto in costos.items():
        b = bloques[cultivo]
        b["categorias"][categoria] += monto
        b["total"] += monto
    salida = []
    for cultivo_id, b in bloques.items():
        cultivo = nombres[1].get(cultivo_id)
        sup = sum((s for k, s in superficies.items() if k[1] == cultivo_id), CERO)
        prod = sum((p[0] - p[1] for k, p in produccion.items() if k[1] == cultivo_id), CERO)
        filas = []
        for cat_id, monto in sorted(b["categorias"].items(), key=lambda x: -x[1]):
            cat = categorias.get(cat_id)
            filas.append({"categoria": cat.nombre if cat else "?", "monto": monto, "pct": _div(monto, b["total"]),
                          "por_ha": _div(monto, sup) if cultivo_id else None,
                          "por_unidad": _div(monto, prod) if cultivo_id and prod else None})
        salida.append({
            "cultivo": cultivo.nombre if cultivo else SIN_NOMBRE[1],
            "cultivo_id": cultivo_id,
            "unidad": cultivo.unidad.abreviatura if cultivo else None,
            "superficie": sup if cultivo_id else None,
            "produccion": prod if cultivo_id else None,
            "filas": filas,
            "total": b["total"],
            "por_ha": _div(b["total"], sup) if cultivo_id else None,
            "por_unidad": _div(b["total"], prod) if cultivo_id and prod else None,
        })
    salida.sort(key=lambda x: (x["cultivo_id"] is None, -x["total"]))
    return salida
