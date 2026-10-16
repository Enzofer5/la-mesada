"""Reportes: cada reporte es una función (filtros, args) → {titulo, tablas:[{subtitulo, columnas, formatos, filas,
totales}]}. Los formatos por columna son: texto | num | moneda | pct | fecha."""
from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import extract, func, select

from ..extensions import db
from ..models import (CargaCombustible, CategoriaGasto, Cliente, CuentaPagar, Cultivo, DetalleVenta, Empleado,
                      Finca, Gasto, Ingreso, Insumo, Maquina, PagoEmpleado, Proveedor, Trabajo, UsoMaquinaria,
                      Venta, dec)
from ..models.personal import TIPOS_EMPLEADO
from ..utils.formato import MESES
from . import rentabilidad as rent
from .tenant import empresa_id, fincas_permitidas

CERO = Decimal("0")


def _tabla(subtitulo, columnas, formatos, filas, totales=None):
    return {"subtitulo": subtitulo, "columnas": columnas, "formatos": formatos, "filas": filas, "totales": totales}


def _pct(a, b):
    return (dec(a) / dec(b)) if b else None


def _suma(filas, i):
    return sum((dec(f[i]) for f in filas if f[i] is not None), CERO)


def _nombres(modelo, attr="nombre"):
    return {x.id: getattr(x, attr) for x in db.session.scalars(select(modelo).where(
        modelo.empresa_id == empresa_id())).unique()}


# ================================================================== PRODUCCIÓN
def _produccion(f, agrupar, titulo):
    filas, _ = rent.rentabilidad(f, agrupar)
    datos = [[r["nombre"], r["superficie"], r["produccion"], r["merma"], r["comercializable"], r["unidad"] or "—",
              r["rendimiento_ha"]] for r in filas if r["produccion"]]
    return {"titulo": titulo, "tablas": [_tabla(
        None, ["Grupo", "Hectáreas", "Cosechado", "Merma + semilla guardada", "Comercializable", "Unidad", "Rendimiento / ha"],
        ["texto", "num", "num", "num", "num", "texto", "num"], datos)]}


def produccion_finca(f, a):
    return _produccion(f, "finca_cultivo", "Producción por finca")


def produccion_cultivo(f, a):
    return _produccion(f, "cultivo", "Producción por cultivo")


def produccion_campana(f, a):
    return _produccion(f, "campana_cultivo", "Producción por campaña")


def rendimiento(f, a):
    return _produccion(f, "finca_campana_cultivo", "Rendimiento por hectárea")


# ================================================================== GASTOS
def _gastos(f, posicion, titulo, nombres, etiqueta):
    costos = rent.costos_base(f, por_categoria=True)
    agg = defaultdict(Decimal)
    for clave, monto in costos.items():
        agg[clave[posicion]] += monto
    total = sum(agg.values(), CERO)
    filas = [[nombres.get(k, None) or ("Sin asignar" if k is None else "?"), v, _pct(v, total)]
             for k, v in sorted(agg.items(), key=lambda x: -x[1])]
    return {"titulo": titulo, "tablas": [_tabla(None, [etiqueta, "Monto", "% del total"], ["texto", "moneda", "pct"],
                                                filas, ["TOTAL", total, Decimal("1") if total else None])]}


def gastos_finca(f, a):
    return _gastos(f, 0, "Gastos por finca", _nombres(Finca), "Finca")


def gastos_cultivo(f, a):
    return _gastos(f, 1, "Gastos por cultivo", _nombres(Cultivo), "Cultivo")


def gastos_campana(f, a):
    from ..models import Campana
    return _gastos(f, 2, "Gastos por campaña", _nombres(Campana), "Campaña")


def gastos_categoria(f, a):
    return _gastos(f, 3, "Gastos por categoría", _nombres(CategoriaGasto), "Categoría")


def gastos_detalle(f, a):
    stmt = select(Gasto).where(Gasto.empresa_id == empresa_id()).order_by(Gasto.fecha, Gasto.id)
    stmt = rent._aplicar(stmt, f, Gasto.fecha, Gasto.finca_id, Gasto.cultivo_id, Gasto.campana_id, Gasto.lote_id)
    if f.get("categoria"):
        stmt = stmt.where(Gasto.categoria_id == f["categoria"])
    filas = [[g.fecha, g.categoria.nombre, g.descripcion, g.finca.nombre if g.finca else "—",
              g.cultivo.nombre if g.cultivo else "—", g.proveedor.razon_social if g.proveedor else "—", g.monto]
             for g in db.session.scalars(stmt.limit(5000)).unique()]
    return {"titulo": "Detalle de gastos", "tablas": [_tabla(
        None, ["Fecha", "Categoría", "Descripción", "Finca", "Cultivo", "Proveedor", "Monto"],
        ["fecha", "texto", "texto", "texto", "texto", "texto", "moneda"], filas,
        ["TOTAL", "", "", "", "", "", _suma(filas, 6)])]}


# ================================================================== MANO DE OBRA
def _filtro_trabajos(stmt, f, modelo):
    return rent._aplicar(stmt, f, modelo.fecha, modelo.finca_id, modelo.cultivo_id, modelo.campana_id,
                         modelo.lote_id)


def mano_obra_trabajador(f, a):
    stmt = _filtro_trabajos(select(Trabajo.empleado_id, func.sum(Trabajo.total), func.sum(Trabajo.jornales),
                                   func.sum(Trabajo.horas)).where(Trabajo.empresa_id == empresa_id())
                            .group_by(Trabajo.empleado_id), f, Trabajo)
    devengado = {r[0]: (dec(r[1]), dec(r[2]), dec(r[3])) for r in db.session.execute(stmt)}
    stmt = _filtro_trabajos(select(PagoEmpleado.empleado_id, func.sum(PagoEmpleado.monto)).where(
        PagoEmpleado.empresa_id == empresa_id()).group_by(PagoEmpleado.empleado_id), f, PagoEmpleado)
    pagado = {r[0]: dec(r[1]) for r in db.session.execute(stmt)}
    empleados = {e.id: e for e in db.session.scalars(select(Empleado).where(
        Empleado.empresa_id == empresa_id())).unique()}
    tipos = dict(TIPOS_EMPLEADO)
    filas = []
    for eid in set(devengado) | set(pagado):
        e = empleados[eid]
        d = devengado.get(eid, (CERO, CERO, CERO))
        filas.append([e.nombre_completo, tipos.get(e.tipo, e.tipo), d[1], d[2], d[0], pagado.get(eid, CERO)])
    filas.sort(key=lambda x: -x[4])
    return {"titulo": "Mano de obra por trabajador", "tablas": [_tabla(
        "Trabajado = trabajos registrados en el período; Pagado = pagos registrados en el período.",
        ["Trabajador", "Tipo", "Jornales", "Horas", "Trabajado ($)", "Pagado ($)"],
        ["texto", "texto", "num", "num", "moneda", "moneda"], filas,
        ["TOTAL", "", _suma(filas, 2), _suma(filas, 3), _suma(filas, 4), _suma(filas, 5)])]}


def mano_obra_tipo(f, a):
    stmt = _filtro_trabajos(select(Empleado.tipo, func.sum(Trabajo.total), func.sum(Trabajo.jornales))
                            .join(Empleado, Trabajo.empleado_id == Empleado.id)
                            .where(Trabajo.empresa_id == empresa_id()).group_by(Empleado.tipo), f, Trabajo)
    devengado = {r[0]: (dec(r[1]), dec(r[2])) for r in db.session.execute(stmt)}
    stmt = _filtro_trabajos(select(Empleado.tipo, func.sum(PagoEmpleado.monto))
                            .join(Empleado, PagoEmpleado.empleado_id == Empleado.id)
                            .where(PagoEmpleado.empresa_id == empresa_id()).group_by(Empleado.tipo), f, PagoEmpleado)
    pagado = {r[0]: dec(r[1]) for r in db.session.execute(stmt)}
    tipos = dict(TIPOS_EMPLEADO)
    filas = [[tipos.get(t, t), devengado.get(t, (CERO, CERO))[1], devengado.get(t, (CERO, CERO))[0],
              pagado.get(t, CERO)] for t in set(devengado) | set(pagado)]
    filas.sort(key=lambda x: -x[2])
    return {"titulo": "Mano de obra por tipo de trabajador", "tablas": [_tabla(
        "Ej.: cuánto se pagó a cargadores, tractoristas, cosechadores…",
        ["Tipo de trabajador", "Jornales", "Trabajado ($)", "Pagado ($)"], ["texto", "num", "moneda", "moneda"], filas,
        ["TOTAL", _suma(filas, 1), _suma(filas, 2), _suma(filas, 3)])]}


def _mano_obra_por(f, posicion, nombres, titulo, etiqueta):
    from .gastos_auto import categoria_id
    f2 = dict(f, categoria=categoria_id("mano_obra"))
    costos = rent.costos_base(f2)
    agg = defaultdict(Decimal)
    for clave, monto in costos.items():
        agg[clave[posicion]] += monto
    filas = [[nombres.get(k) or "Sin asignar", v] for k, v in sorted(agg.items(), key=lambda x: -x[1])]
    return {"titulo": titulo, "tablas": [_tabla(None, [etiqueta, "Mano de obra ($)"], ["texto", "moneda"], filas,
                                                ["TOTAL", _suma(filas, 1)])]}


def mano_obra_finca(f, a):
    return _mano_obra_por(f, 0, _nombres(Finca), "Mano de obra por finca", "Finca")


def mano_obra_cultivo(f, a):
    return _mano_obra_por(f, 1, _nombres(Cultivo), "Mano de obra por cultivo", "Cultivo")


def mano_obra_mes(f, a):
    anio, mes = extract("year", Trabajo.fecha), extract("month", Trabajo.fecha)
    stmt = _filtro_trabajos(select(anio, mes, func.sum(Trabajo.total)).where(Trabajo.empresa_id == empresa_id())
                            .group_by(anio, mes), f, Trabajo)
    trab = {(int(r[0]), int(r[1])): dec(r[2]) for r in db.session.execute(stmt)}
    anio, mes = extract("year", PagoEmpleado.fecha), extract("month", PagoEmpleado.fecha)
    stmt = _filtro_trabajos(select(anio, mes, func.sum(PagoEmpleado.monto)).where(
        PagoEmpleado.empresa_id == empresa_id()).group_by(anio, mes), f, PagoEmpleado)
    pag = {(int(r[0]), int(r[1])): dec(r[2]) for r in db.session.execute(stmt)}
    filas = [[f"{MESES[m]} {a_}", trab.get((a_, m), CERO), pag.get((a_, m), CERO)] for a_, m in sorted(set(trab) | set(pag))]
    return {"titulo": "Total de mano de obra por mes", "tablas": [_tabla(
        None, ["Mes", "Trabajado ($)", "Pagado ($)"], ["texto", "moneda", "moneda"], filas,
        ["TOTAL", _suma(filas, 1), _suma(filas, 2)])]}


# ================================================================== VENTAS
def _ventas_stmt(f, *cols):
    stmt = select(*cols).join(Venta, DetalleVenta.venta_id == Venta.id).where(Venta.empresa_id == empresa_id())
    return rent._aplicar(stmt, f, Venta.fecha, Venta.finca_id, DetalleVenta.cultivo_id, Venta.campana_id,
                         DetalleVenta.lote_id)


def ventas_cultivo(f, a):
    from ..models import UnidadMedida
    stmt = _ventas_stmt(f, DetalleVenta.cultivo_id, DetalleVenta.unidad_id, func.sum(DetalleVenta.cantidad),
                        func.sum(DetalleVenta.subtotal)).group_by(DetalleVenta.cultivo_id, DetalleVenta.unidad_id)
    cultivos, unidades = _nombres(Cultivo), _nombres(UnidadMedida, "abreviatura")
    filas = [[cultivos.get(c), unidades.get(u), dec(q), dec(t), dec(t) / dec(q) if q else None]
             for c, u, q, t in db.session.execute(stmt)]
    filas.sort(key=lambda x: -x[3])
    return {"titulo": "Ventas por cultivo", "tablas": [_tabla(
        None, ["Cultivo", "Unidad", "Cantidad", "Total ($)", "Precio promedio"],
        ["texto", "texto", "num", "moneda", "moneda"], filas, ["TOTAL", "", None, _suma(filas, 3), None])]}


def ventas_finca(f, a):
    stmt = _ventas_stmt(f, Venta.finca_id, func.sum(DetalleVenta.subtotal)).group_by(Venta.finca_id)
    fincas = _nombres(Finca)
    filas = sorted([[fincas.get(fi), dec(t)] for fi, t in db.session.execute(stmt)], key=lambda x: -x[1])
    return {"titulo": "Ventas por finca", "tablas": [_tabla(None, ["Finca", "Total vendido ($)"], ["texto", "moneda"],
                                                            filas, ["TOTAL", _suma(filas, 1)])]}


def _ventas_filtradas(f):
    stmt = select(Venta).where(Venta.empresa_id == empresa_id()).order_by(Venta.fecha)
    stmt = rent._aplicar(stmt, f, Venta.fecha, Venta.finca_id, Venta.finca_id, Venta.campana_id, sin=("cultivo",))
    ventas = db.session.scalars(stmt).unique().all()
    if f.get("cultivo"):
        ventas = [v for v in ventas if any(d.cultivo_id == f["cultivo"] for d in v.detalles)]
    return ventas


def ventas_comprador(f, a):
    agg = defaultdict(lambda: [0, CERO, CERO])
    for v in _ventas_filtradas(f):
        d = agg[v.cliente.nombre]
        d[0] += 1
        d[1] += dec(v.total)
        d[2] += v.cobrado
    filas = [[k, d[0], d[1], d[2], d[1] - d[2]] for k, d in sorted(agg.items(), key=lambda x: -x[1][1])]
    return {"titulo": "Ventas por comprador", "tablas": [_tabla(
        None, ["Comprador", "Ventas", "Total ($)", "Cobrado ($)", "Saldo ($)"],
        ["texto", "num", "moneda", "moneda", "moneda"], filas,
        ["TOTAL", _suma(filas, 1), _suma(filas, 2), _suma(filas, 3), _suma(filas, 4)])]}


def ingresos_periodo(f, a):
    anio, mes = extract("year", Venta.fecha), extract("month", Venta.fecha)
    stmt = _ventas_stmt(f, anio, mes, func.sum(DetalleVenta.subtotal)).group_by(anio, mes)
    ventas = {(int(r[0]), int(r[1])): dec(r[2]) for r in db.session.execute(stmt)}
    anio, mes = extract("year", Ingreso.fecha), extract("month", Ingreso.fecha)
    base = select(anio, mes, func.sum(Ingreso.monto)).where(Ingreso.empresa_id == empresa_id(),
                                                             Ingreso.estado != "rechazado").group_by(anio, mes)
    base = rent._aplicar(base, f, Ingreso.fecha, Ingreso.finca_id, Ingreso.cultivo_id, Ingreso.campana_id)
    cobros = {(int(r[0]), int(r[1])): dec(r[2]) for r in db.session.execute(base.where(Ingreso.venta_id.is_not(None)))}
    otros = {(int(r[0]), int(r[1])): dec(r[2]) for r in db.session.execute(base.where(Ingreso.venta_id.is_(None)))}
    meses = sorted(set(ventas) | set(cobros) | set(otros))
    filas = [[f"{MESES[m]} {a_}", ventas.get((a_, m), CERO), otros.get((a_, m), CERO), cobros.get((a_, m), CERO)]
             for a_, m in meses]
    return {"titulo": "Ingresos por período", "tablas": [_tabla(
        "Ventas = facturado en el mes; Cobros = dinero efectivamente cobrado de ventas.",
        ["Mes", "Ventas ($)", "Otros ingresos ($)", "Cobros de ventas ($)"], ["texto", "moneda", "moneda", "moneda"],
        filas, ["TOTAL", _suma(filas, 1), _suma(filas, 2), _suma(filas, 3)])]}


def ingresos_dia(f, a):
    stmt = select(Ingreso).where(Ingreso.empresa_id == empresa_id(), Ingreso.estado != "rechazado").order_by(
        Ingreso.fecha)
    stmt = rent._aplicar(stmt, f, Ingreso.fecha, Ingreso.finca_id, Ingreso.cultivo_id, Ingreso.campana_id)
    filas = [[i.fecha, i.concepto, i.cliente.nombre if i.cliente else "—", i.finca.nombre if i.finca else "—",
              i.metodo_pago, i.monto] for i in db.session.scalars(stmt.limit(5000)).unique()]
    return {"titulo": "Detalle de ingresos (cobros)", "tablas": [_tabla(
        None, ["Fecha", "Concepto", "Cliente", "Finca", "Medio", "Monto"],
        ["fecha", "texto", "texto", "texto", "texto", "moneda"], filas, ["TOTAL", "", "", "", "", _suma(filas, 5)])]}


# ================================================================== RENTABILIDAD
def _rent(f, a, agrupar, titulo):
    prorratear = a.get("prorratear") == "1"
    filas, total = rent.rentabilidad(f, agrupar, prorratear)
    datos = [[r["nombre"], r["superficie"], r["ingresos"], r["costos"], r["ganancia"], r["margen"], r["costo_ha"],
              r["ganancia_ha"], r["costo_unidad"], r["ganancia_unidad"], r["unidad"] or ""] for r in filas]
    sub = "Gastos generales prorrateados por hectárea." if prorratear else \
        "Los gastos sin cultivo se muestran como 'Sin cultivo (estructura)'."
    return {"titulo": titulo, "tablas": [_tabla(
        sub, ["Grupo", "Hectáreas", "Ingresos", "Costos", "Ganancia", "Margen", "Costo/ha", "Ganancia/ha",
              "Costo/unidad", "Ganancia/unidad", "Unidad"],
        ["texto", "num", "moneda", "moneda", "moneda", "pct", "moneda", "moneda", "moneda", "moneda", "texto"], datos,
        ["TOTAL", total["superficie"], total["ingresos"], total["costos"], total["ganancia"], total["margen"],
         total["costo_ha"], total["ganancia_ha"], None, None, ""])]}


def rent_finca(f, a):
    return _rent(f, a, "finca", "Ganancia por finca")


def rent_cultivo(f, a):
    return _rent(f, a, "cultivo", "Ganancia por cultivo")


def rent_campana(f, a):
    return _rent(f, a, "campana_cultivo", "Ganancia por campaña")


def rent_hectarea(f, a):
    return _rent(f, a, "finca_cultivo", "Ganancia por hectárea (finca y cultivo)")


def costo_produccion(f, a):
    bloques = rent.costo_produccion(f, a.get("prorratear") == "1")
    tablas = []
    for b in bloques:
        filas = [[r["categoria"], r["monto"], r["pct"], r["por_ha"], r["por_unidad"]] for r in b["filas"]]
        sub = b["cultivo"]
        if b["superficie"]:
            sub += f" · {b['superficie']:.2f} ha".replace(".", ",")
        if b["produccion"]:
            sub += f" · {b['produccion']:.2f} {b['unidad']} comercializables".replace(".", ",")
        tablas.append(_tabla(sub, ["Concepto", "Monto", "%", "Por hectárea", f"Por {b['unidad'] or 'unidad'}"],
                             ["texto", "moneda", "pct", "moneda", "moneda"], filas,
                             ["COSTO TOTAL DE PRODUCCIÓN", b["total"], Decimal("1"), b["por_ha"], b["por_unidad"]]))
    return {"titulo": "Costo de producción", "tablas": tablas}


# ================================================================== DEUDAS
def cuentas_pagar(f, a):
    stmt = select(CuentaPagar).where(CuentaPagar.empresa_id == empresa_id(),
                                     CuentaPagar.pagado < CuentaPagar.importe).order_by(CuentaPagar.vencimiento)
    if f.get("finca"):
        stmt = stmt.where(CuentaPagar.finca_id == f["finca"])
    cuentas = db.session.scalars(stmt).unique().all()
    detalle = [[c.proveedor.razon_social, c.comprobante or "—", c.vencimiento, c.importe, c.pagado, c.pendiente,
                c.estado] for c in cuentas]
    agg = defaultdict(lambda: [CERO, CERO])
    for c in cuentas:
        agg[c.proveedor.razon_social][0] += c.pendiente
        if c.estado == "vencido":
            agg[c.proveedor.razon_social][1] += c.pendiente
    resumen = [[k, v[0], v[1]] for k, v in sorted(agg.items(), key=lambda x: -x[1][0])]
    return {"titulo": "Deuda con proveedores", "tablas": [
        _tabla("Resumen por proveedor", ["Proveedor", "Pendiente ($)", "Vencido ($)"], ["texto", "moneda", "moneda"],
               resumen, ["TOTAL", _suma(resumen, 1), _suma(resumen, 2)]),
        _tabla("Detalle", ["Proveedor", "Comprobante", "Vence", "Importe", "Pagado", "Pendiente", "Estado"],
               ["texto", "texto", "fecha", "moneda", "moneda", "moneda", "texto"], detalle,
               ["TOTAL", "", None, _suma(detalle, 3), _suma(detalle, 4), _suma(detalle, 5), ""])]}


def cuentas_cobrar(f, a):
    ventas = [v for v in _ventas_filtradas(dict(f, desde=None, hasta=None) if not f.get("anio") else f) if v.saldo > 0]
    hoy = date.today()
    filas = [[v.cliente.nombre, f"#{v.id}", v.fecha, v.fecha_vencimiento_cobro, v.total, v.cobrado, v.saldo,
              "vencida" if v.fecha_vencimiento_cobro and v.fecha_vencimiento_cobro < hoy else v.estado_pago]
             for v in ventas]
    return {"titulo": "Ventas pendientes de cobro", "tablas": [_tabla(
        None, ["Cliente", "Venta", "Fecha", "Vence", "Total", "Cobrado", "Saldo", "Estado"],
        ["texto", "texto", "fecha", "fecha", "moneda", "moneda", "moneda", "texto"], filas,
        ["TOTAL", "", None, None, _suma(filas, 4), _suma(filas, 5), _suma(filas, 6), ""])]}


# ================================================================== COMBUSTIBLE E INVENTARIO
def combustible(f, a):
    def base(*cols):
        stmt = select(*cols).where(CargaCombustible.empresa_id == empresa_id())
        stmt = rent._aplicar(stmt, f, CargaCombustible.fecha, CargaCombustible.finca_id, CargaCombustible.cultivo_id,
                             CargaCombustible.campana_id)
        return stmt
    maquinas, fincas, cultivos = _nombres(Maquina), _nombres(Finca), _nombres(Cultivo)
    por_maquina = [[maquinas.get(m) or "Sin máquina", dec(l), dec(t)] for m, l, t in db.session.execute(
        base(CargaCombustible.maquina_id, func.sum(CargaCombustible.litros), func.sum(CargaCombustible.total))
        .group_by(CargaCombustible.maquina_id))]
    por_finca = [[fincas.get(x) or "Sin finca", dec(l), dec(t)] for x, l, t in db.session.execute(
        base(CargaCombustible.finca_id, func.sum(CargaCombustible.litros), func.sum(CargaCombustible.total))
        .group_by(CargaCombustible.finca_id))]
    anio, mes = extract("year", CargaCombustible.fecha), extract("month", CargaCombustible.fecha)
    por_mes = [[f"{MESES[int(m)]} {int(a_)}", dec(l), dec(t)] for a_, m, l, t in db.session.execute(
        base(anio, mes, func.sum(CargaCombustible.litros), func.sum(CargaCombustible.total))
        .group_by(anio, mes).order_by(anio, mes))]
    from .gastos_auto import categoria_id
    costos = rent.costos_base(dict(f, categoria=categoria_id("combustible")))
    agg = defaultdict(Decimal)
    for clave, monto in costos.items():
        agg[clave[1]] += monto
    por_cultivo = [[cultivos.get(k) or "Sin cultivo", v] for k, v in sorted(agg.items(), key=lambda x: -x[1])]
    cols, fmts = ["", "Litros", "Total ($)"], ["texto", "num", "moneda"]
    return {"titulo": "Combustible", "tablas": [
        _tabla("Consumo por máquina", ["Máquina"] + cols[1:], fmts, por_maquina,
               ["TOTAL", _suma(por_maquina, 1), _suma(por_maquina, 2)]),
        _tabla("Consumo por finca", ["Finca"] + cols[1:], fmts, por_finca,
               ["TOTAL", _suma(por_finca, 1), _suma(por_finca, 2)]),
        _tabla("Gasto mensual", ["Mes"] + cols[1:], fmts, por_mes, ["TOTAL", _suma(por_mes, 1), _suma(por_mes, 2)]),
        _tabla("Gasto por cultivo (todas las fuentes de combustible)", ["Cultivo", "Total ($)"], ["texto", "moneda"],
               por_cultivo, ["TOTAL", _suma(por_cultivo, 1)]),
    ]}


def stock(f, a):
    insumos = db.session.scalars(select(Insumo).where(Insumo.empresa_id == empresa_id(), Insumo.estado == "activo")
                                 .order_by(Insumo.categoria, Insumo.nombre)).unique().all()
    filas = [[i.nombre, i.categoria, i.unidad.abreviatura, i.stock, i.stock_minimo, i.costo_promedio,
              i.stock * i.costo_promedio, "BAJO" if i.stock_minimo and i.stock < i.stock_minimo else ""] for i in insumos]
    return {"titulo": "Stock de insumos", "tablas": [_tabla(
        None, ["Insumo", "Categoría", "Unidad", "Stock", "Mínimo", "Costo prom.", "Valor ($)", "Alerta"],
        ["texto", "texto", "texto", "num", "num", "moneda", "moneda", "texto"], filas,
        ["TOTAL", "", "", None, None, None, _suma(filas, 6), ""])]}


# ================================================================== CATÁLOGO
REPORTES = {
    "Producción": [
        ("produccion_finca", "Producción por finca", produccion_finca),
        ("produccion_cultivo", "Producción por cultivo", produccion_cultivo),
        ("produccion_campana", "Producción por campaña", produccion_campana),
        ("rendimiento", "Rendimiento por hectárea", rendimiento),
    ],
    "Gastos": [
        ("gastos_finca", "Gastos por finca", gastos_finca),
        ("gastos_cultivo", "Gastos por cultivo", gastos_cultivo),
        ("gastos_categoria", "Gastos por categoría", gastos_categoria),
        ("gastos_campana", "Gastos por campaña", gastos_campana),
        ("gastos_detalle", "Detalle de gastos", gastos_detalle),
        ("combustible", "Combustible", combustible),
    ],
    "Mano de obra": [
        ("mano_obra_mes", "Total pagado por mes", mano_obra_mes),
        ("mano_obra_trabajador", "Por trabajador", mano_obra_trabajador),
        ("mano_obra_tipo", "Por tipo de trabajador", mano_obra_tipo),
        ("mano_obra_finca", "Por finca", mano_obra_finca),
        ("mano_obra_cultivo", "Por cultivo", mano_obra_cultivo),
    ],
    "Ventas e ingresos": [
        ("ventas_cultivo", "Ventas por cultivo", ventas_cultivo),
        ("ventas_finca", "Ventas por finca", ventas_finca),
        ("ventas_comprador", "Ventas por comprador", ventas_comprador),
        ("ingresos_periodo", "Ingresos por período", ingresos_periodo),
        ("ingresos_dia", "Detalle de cobros", ingresos_dia),
        ("cuentas_cobrar", "Pendiente de cobro", cuentas_cobrar),
    ],
    "Rentabilidad": [
        ("rent_finca", "Ganancia por finca", rent_finca),
        ("rent_cultivo", "Ganancia por cultivo", rent_cultivo),
        ("rent_campana", "Ganancia por campaña", rent_campana),
        ("rent_hectarea", "Ganancia por hectárea", rent_hectarea),
        ("costo_produccion", "Costo de producción", costo_produccion),
    ],
    "Deudas e insumos": [
        ("cuentas_pagar", "Deuda con proveedores", cuentas_pagar),
        ("stock", "Stock de insumos", stock),
    ],
}

POR_CLAVE = {clave: (titulo, fn, grupo) for grupo, items in REPORTES.items() for clave, titulo, fn in items}
USA_PRORRATEO = {"rent_finca", "rent_cultivo", "rent_campana", "rent_hectarea", "costo_produccion"}
USA_CATEGORIA = {"gastos_finca", "gastos_cultivo", "gastos_campana", "gastos_detalle"}
