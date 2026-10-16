"""Reglas de negocio que se ejecutan al guardar o eliminar registros operativos.

Cada función guardar_x(obj, nuevo, anterior) se llama después de volcar el registro a la base (ya tiene id) y
dentro de la misma transacción: si algo falla (ej. stock insuficiente) se revierte todo.
"""
from decimal import Decimal

from sqlalchemy import func, select

from ..extensions import db
from ..models import (Cosecha, Cultivo, Empleado, Insumo, Maquina, Siembra, UnidadMedida, Venta, dec)
from ..utils.validacion import ErrorNegocio
from . import cuentas, gastos_auto, inventario

CENT = Decimal("0.01")

CATEGORIA_POR_ACTIVIDAD = {
    "preparacion": "maquinaria",
    "siembra": "otros",
    "fertilizacion": "fertilizantes",
    "agroquimicos": "agroquimicos",
    "riego": "riego",
    "malezas": "mano_obra",
    "plagas": "agroquimicos",
    "mantenimiento": "otros",
    "cosecha": "mano_obra",
    "otra": "otros",
}


def _imp(obj):
    return {"finca_id": obj.finca_id, "lote_id": obj.lote_id, "campana_id": obj.campana_id,
            "cultivo_id": obj.cultivo_id}


def _nombre(modelo, id_):
    if not id_:
        return ""
    obj = db.session.get(modelo, id_)
    return str(obj) if obj else ""


# ------------------------------------------------------------------ Siembras
ORIGENES_SEMILLA = [("propia", "Propia (guardada de nuestras cosechas, sin costo)"), ("comprada", "Comprada")]


def normalizar_semilla(s):
    """Semilla propia → nunca tiene precio. Comprada → costo del inventario o el precio cargado a mano."""
    insumo = db.session.get(Insumo, s.insumo_id) if s.insumo_id else None
    if insumo and insumo.categoria != "semilla":
        raise ErrorNegocio("El insumo elegido no es una semilla.")
    if insumo:
        origen = "propia" if insumo.propia else "comprada"
        if s.origen_semilla and s.origen_semilla != origen:
            raise ErrorNegocio(f"«{insumo.nombre}» es semilla {'propia' if insumo.propia else 'comprada'}: "
                               f"cambiá el origen de la semilla o elegí otra.")
        s.origen_semilla = origen
    if s.origen_semilla == "propia":
        s.costo_semilla = 0
        s.proveedor_id = None


def guardar_siembra(s, nuevo, anterior):
    inventario.eliminar_por_origen("siembra", s.id)
    normalizar_semilla(s)
    if s.estado == "planificada":
        # Sector marcado pero todavía no sembrado: no descuenta semilla ni genera costo hasta que se siembre.
        gastos_auto.eliminar("siembra", s.id)
        return
    if s.insumo_id and s.cantidad_semilla:
        insumo = db.session.get(Insumo, s.insumo_id)
        mov = inventario.registrar(insumo, "salida", s.cantidad_semilla, s.fecha_siembra, origen="siembra",
                                   origen_id=s.id, observaciones="Semilla usada en siembra", **_imp(s))
        s.unidad_semilla_id = insumo.unidad_id
        s.costo_semilla = (dec(s.cantidad_semilla) * dec(mov.precio_unitario)).quantize(CENT)
    if s.origen_semilla == "propia":
        s.costo_semilla = 0  # semilla guardada de cosechas propias: sin precio
    cultivo = _nombre(Cultivo, s.cultivo_id)
    gastos_auto.sincronizar("siembra", s.id, [{
        "categoria": "semillas", "monto": s.costo_semilla, "fecha": s.fecha_siembra,
        "descripcion": f"Semilla {cultivo} {s.variedad or ''} · {s.superficie} ha".strip(),
        "proveedor_id": s.proveedor_id, **_imp(s)}])


def eliminar_siembra(s):
    cosechas = db.session.scalar(select(func.count(Cosecha.id)).where(Cosecha.siembra_id == s.id))
    if cosechas:
        raise ErrorNegocio("La siembra tiene cosechas registradas. Eliminá primero las cosechas.")
    inventario.eliminar_por_origen("siembra", s.id)
    gastos_auto.eliminar("siembra", s.id)


# ------------------------------------------------------------------ Aplicaciones
def _guardar_aplicacion(a, origen, categoria):
    inventario.eliminar_por_origen(origen, a.id)
    insumo = db.session.get(Insumo, a.insumo_id)
    mov = inventario.registrar(insumo, "salida", a.cantidad, a.fecha, origen=origen, origen_id=a.id,
                               observaciones=f"Aplicación en lote", **_imp(a))
    a.costo_unitario = dec(mov.precio_unitario)
    a.costo_total = (dec(a.cantidad) * a.costo_unitario).quantize(CENT)
    gastos_auto.sincronizar(origen, a.id, [{
        "categoria": categoria, "monto": a.costo_total, "fecha": a.fecha,
        "descripcion": f"Aplicación {insumo.nombre} · {a.cantidad:.2f} {insumo.unidad.abreviatura}", **_imp(a)}])


def guardar_aplicacion_fertilizante(a, nuevo, anterior):
    _guardar_aplicacion(a, "aplicacion_fertilizante", "fertilizantes")


def eliminar_aplicacion_fertilizante(a):
    inventario.eliminar_por_origen("aplicacion_fertilizante", a.id)
    gastos_auto.eliminar("aplicacion_fertilizante", a.id)


def guardar_aplicacion_agroquimico(a, nuevo, anterior):
    if a.dosis and a.superficie and not a.cantidad:
        a.cantidad = dec(a.dosis) * dec(a.superficie)
    _guardar_aplicacion(a, "aplicacion_agroquimico", "agroquimicos")


def eliminar_aplicacion_agroquimico(a):
    inventario.eliminar_por_origen("aplicacion_agroquimico", a.id)
    gastos_auto.eliminar("aplicacion_agroquimico", a.id)


# ------------------------------------------------------------------ Movimientos manuales de inventario
def guardar_movimiento(m, nuevo, anterior):
    insumo = db.session.get(Insumo, m.insumo_id)
    if m.tipo == "salida":
        inv = inventario.inventario_de(insumo)
        m.precio_unitario = inv.costo_promedio
    if insumo.propia:
        m.precio_unitario = 0  # la semilla propia no tiene precio
    if m.tipo in ("entrada", "salida") and dec(m.cantidad) <= 0:
        raise ErrorNegocio("La cantidad debe ser mayor a cero.")
    inventario.verificar_no_negativo(m.insumo_id)
    if anterior and anterior.get("insumo_id") and anterior["insumo_id"] != m.insumo_id:
        inventario.verificar_no_negativo(anterior["insumo_id"])
    if m.tipo == "salida" and m.finca_id:
        gastos_auto.sincronizar("movimiento", m.id, [{
            "categoria": inventario.CATEGORIA_GASTO_POR_INSUMO.get(insumo.categoria, "otros"),
            "monto": dec(m.cantidad) * dec(m.precio_unitario), "fecha": m.fecha,
            "descripcion": f"Consumo de {insumo.nombre} · {m.cantidad:.2f} {insumo.unidad.abreviatura}",
            **_imp(m)}])
    else:
        gastos_auto.eliminar("movimiento", m.id)


def eliminar_movimiento(m):
    if m.origen != "manual":
        raise ErrorNegocio("Este movimiento lo generó otro registro (compra, siembra o aplicación). "
                           "Modificá o eliminá ese registro.")
    gastos_auto.eliminar("movimiento", m.id)
    insumo_id = m.insumo_id
    db.session.delete(m)
    db.session.flush()
    inventario.verificar_no_negativo(insumo_id)


# ------------------------------------------------------------------ Riego y actividades
def guardar_riego(r, nuevo, anterior):
    gastos_auto.sincronizar("riego", r.id, [{
        "categoria": "riego", "monto": r.costo, "fecha": r.fecha,
        "descripcion": f"Riego {r.sistema} · {r.horas} h", **_imp(r)}])


def eliminar_riego(r):
    gastos_auto.eliminar("riego", r.id)


def guardar_actividad(a, nuevo, anterior):
    if a.categoria_gasto_id:
        from ..models import CategoriaGasto
        codigo = db.session.get(CategoriaGasto, a.categoria_gasto_id).codigo
    else:
        codigo = CATEGORIA_POR_ACTIVIDAD.get(a.tipo, "otros")
    gastos_auto.sincronizar("actividad", a.id, [{
        "categoria": codigo, "monto": a.costo, "fecha": a.fecha,
        "descripcion": f"Actividad: {a.tipo.replace('_', ' ')} {a.descripcion or ''}".strip(), **_imp(a)}])


def eliminar_actividad(a):
    gastos_auto.eliminar("actividad", a.id)


# ------------------------------------------------------------------ Maquinaria
def guardar_uso_maquinaria(u, nuevo, anterior):
    maquina = db.session.get(Maquina, u.maquina_id)
    horas_previas = dec(anterior.get("horas")) if anterior and anterior.get("maquina_id") == u.maquina_id else 0
    if anterior and anterior.get("maquina_id") and anterior["maquina_id"] != u.maquina_id:
        vieja = db.session.get(Maquina, anterior["maquina_id"])
        vieja.horas_uso = max(Decimal("0"), dec(vieja.horas_uso) - dec(anterior.get("horas")))
    maquina.horas_uso = dec(maquina.horas_uso) + dec(u.horas) - horas_previas
    u.costo_total = (dec(u.horas) * dec(u.costo_hora) + dec(u.costo_mantenimiento)
                     + dec(u.costo_combustible)).quantize(CENT)
    items = [{
        "categoria": "maquinaria", "monto": dec(u.horas) * dec(u.costo_hora) + dec(u.costo_mantenimiento),
        "fecha": u.fecha, "descripcion": f"{maquina.nombre}: {u.trabajo_realizado} · {u.horas} h", **_imp(u)}]
    if dec(u.costo_combustible) > 0:
        items.append({"categoria": "combustible", "monto": u.costo_combustible, "fecha": u.fecha,
                      "descripcion": f"Combustible {maquina.nombre} · {u.combustible_litros} l", **_imp(u)})
    gastos_auto.sincronizar("uso_maquinaria", u.id, items)


def eliminar_uso_maquinaria(u):
    maquina = db.session.get(Maquina, u.maquina_id)
    maquina.horas_uso = max(Decimal("0"), dec(maquina.horas_uso) - dec(u.horas))
    gastos_auto.eliminar("uso_maquinaria", u.id)


def guardar_combustible(c, nuevo, anterior):
    c.total = (dec(c.litros) * dec(c.precio_litro)).quantize(CENT)
    maquina = db.session.get(Maquina, c.maquina_id) if c.maquina_id else None
    descripcion = f"{c.tipo_combustible.capitalize()} {c.litros} l" + (f" · {maquina.nombre}" if maquina else "")
    if c.imputar_gasto:
        gastos_auto.sincronizar("combustible", c.id, [{
            "categoria": "combustible", "monto": c.total, "fecha": c.fecha, "descripcion": descripcion,
            "proveedor_id": c.proveedor_id, "metodo_pago": c.metodo_pago, **_imp(c)}])
    else:
        gastos_auto.eliminar("combustible", c.id)
    if c.metodo_pago == "cuenta_corriente":
        if not c.proveedor_id:
            raise ErrorNegocio("Para cargar combustible en cuenta corriente elegí el proveedor.")
        cuentas.sincronizar("combustible", c.id, c.proveedor_id, c.total, c.fecha, c.vencimiento,
                            descripcion=descripcion, finca_id=c.finca_id)
    else:
        cuentas.eliminar("combustible", c.id)


def eliminar_combustible(c):
    cuentas.eliminar("combustible", c.id)
    gastos_auto.eliminar("combustible", c.id)


# ------------------------------------------------------------------ Mano de obra
def calcular_total_trabajo(t):
    precio = dec(t.precio_unitario)
    if t.modalidad == "hora":
        return dec(t.horas) * precio
    if t.modalidad == "jornal":
        return dec(t.jornales) * precio
    if t.modalidad == "unidad":
        return dec(t.cantidad) * precio
    return precio


def guardar_trabajo(t, nuevo, anterior):
    if t.modalidad == "hora" and not t.horas:
        raise ErrorNegocio("Indicá la cantidad de horas trabajadas.")
    if t.modalidad == "jornal" and not t.jornales:
        raise ErrorNegocio("Indicá la cantidad de jornales.")
    if t.modalidad == "unidad" and not t.cantidad:
        raise ErrorNegocio("Indicá la cantidad de unidades (bolsas, cajones, etc.).")
    t.total = calcular_total_trabajo(t).quantize(CENT)
    empleado = db.session.get(Empleado, t.empleado_id)
    gastos_auto.sincronizar("trabajo", t.id, [{
        "categoria": "mano_obra", "monto": t.total, "fecha": t.fecha,
        "descripcion": f"{t.tipo_trabajo} · {empleado.nombre_completo}", **_imp(t)}])


def eliminar_trabajo(t):
    gastos_auto.eliminar("trabajo", t.id)


def guardar_pago_empleado(p, nuevo, anterior):
    if p.imputar_costo:
        empleado = db.session.get(Empleado, p.empleado_id)
        gastos_auto.sincronizar("pago_empleado", p.id, [{
            "categoria": "mano_obra", "monto": p.monto, "fecha": p.fecha, "metodo_pago": p.metodo_pago,
            "descripcion": f"{p.concepto} · {empleado.nombre_completo} {p.periodo or ''}".strip(), **_imp(p)}])
    else:
        gastos_auto.eliminar("pago_empleado", p.id)


def eliminar_pago_empleado(p):
    gastos_auto.eliminar("pago_empleado", p.id)


# ------------------------------------------------------------------ Cosechas
def preparar_cosecha(c):
    """Antes de grabar: la producción siempre se guarda en la unidad del cultivo."""
    if c.cultivo_id:
        c.unidad_id = db.session.get(Cultivo, c.cultivo_id).unidad_id


def guardar_cosecha(c, nuevo, anterior):
    cultivo = db.session.get(Cultivo, c.cultivo_id)
    c.unidad_id = cultivo.unidad_id  # la producción siempre se guarda en la unidad del cultivo
    if dec(c.merma) > dec(c.cantidad):
        raise ErrorNegocio("La merma no puede ser mayor a la cantidad cosechada.")
    if c.siembra_id:
        siembra = db.session.get(Siembra, c.siembra_id)
        if siembra.cultivo_id != c.cultivo_id:
            raise ErrorNegocio("El cultivo de la cosecha no coincide con el de la siembra elegida.")
        if not c.superficie or dec(c.superficie) == 0:
            c.superficie = siembra.superficie
        siembra.estado = "cosechada"
    if anterior and anterior.get("siembra_id") and anterior["siembra_id"] != c.siembra_id:
        _reabrir_siembra(anterior["siembra_id"], excluir=c.id)
    _guardar_semilla_propia(c, cultivo)


def cantidad_en_unidad_insumo(cantidad, unidad_origen, insumo):
    """Convierte (ej. 40 t de papa → 40.000 kg del insumo semilla). Sólo entre unidades del mismo tipo."""
    if unidad_origen.id == insumo.unidad_id:
        return dec(cantidad)
    if unidad_origen.tipo != insumo.unidad.tipo:
        raise ErrorNegocio(f"No se puede pasar de {unidad_origen.abreviatura} a {insumo.unidad.abreviatura} "
                           f"(la semilla «{insumo.nombre}» usa otra clase de unidad).")
    return (dec(cantidad) * dec(unidad_origen.factor_base) / dec(insumo.unidad.factor_base)).quantize(Decimal("0.001"))


def _guardar_semilla_propia(c, cultivo):
    """Lo que se guarda de la cosecha para semilla entra al stock de la semilla propia, sin costo."""
    inventario.eliminar_por_origen("cosecha", c.id, validar=True)
    guardada = dec(c.semilla_guardada)
    if guardada < 0:
        raise ErrorNegocio("La semilla guardada no puede ser negativa.")
    if dec(c.merma) + guardada > dec(c.cantidad):
        raise ErrorNegocio("Merma más semilla guardada no puede superar lo cosechado.")
    if not guardada:
        c.insumo_semilla_id = None
        return
    if not c.insumo_semilla_id:
        raise ErrorNegocio("Elegí en qué semilla propia se guarda (ej. «Semilla de papa propia»).")
    insumo = db.session.get(Insumo, c.insumo_semilla_id)
    if not insumo or insumo.categoria != "semilla" or not insumo.propia:
        raise ErrorNegocio("La semilla guardada tiene que ir a un insumo marcado como «semilla propia».")
    unidad = db.session.get(UnidadMedida, cultivo.unidad_id)
    inventario.registrar(insumo, "entrada", cantidad_en_unidad_insumo(guardada, unidad, insumo), c.fecha,
                         precio_unitario=0, origen="cosecha", origen_id=c.id,
                         observaciones=f"Semilla guardada de la cosecha de {cultivo.nombre}", **_imp(c))


def _reabrir_siembra(siembra_id, excluir=None):
    stmt = select(func.count(Cosecha.id)).where(Cosecha.siembra_id == siembra_id)
    if excluir:
        stmt = stmt.where(Cosecha.id != excluir)
    if not db.session.scalar(stmt):
        siembra = db.session.get(Siembra, siembra_id)
        if siembra and siembra.estado == "cosechada":
            siembra.estado = "en_curso"


def eliminar_cosecha(c):
    inventario.eliminar_por_origen("cosecha", c.id, validar=True)  # no si esa semilla ya se usó
    if c.siembra_id:
        _reabrir_siembra(c.siembra_id, excluir=c.id)


# ------------------------------------------------------------------ Gastos manuales
def guardar_gasto(g, nuevo, anterior):
    if g.origen != "manual":
        raise ErrorNegocio("Este gasto se generó automáticamente. Modificá el registro que lo originó.")
    if g.metodo_pago == "cuenta_corriente":
        if not g.proveedor_id:
            raise ErrorNegocio("Para un gasto en cuenta corriente elegí el proveedor.")
        cuentas.sincronizar("gasto", g.id, g.proveedor_id, g.monto, g.fecha, g.vencimiento, g.comprobante,
                            g.descripcion, g.finca_id)
    else:
        cuentas.eliminar("gasto", g.id)


def eliminar_gasto(g):
    if g.origen != "manual":
        raise ErrorNegocio("Este gasto se generó automáticamente. Eliminá el registro que lo originó.")
    cuentas.eliminar("gasto", g.id)


# ------------------------------------------------------------------ Ingresos / cobros
def guardar_ingreso(i, nuevo, anterior):
    if dec(i.monto) <= 0:
        raise ErrorNegocio("El monto debe ser mayor a cero.")
    if i.venta_id:
        venta = db.session.get(Venta, i.venta_id)
        db.session.refresh(venta)
        if i.estado != "rechazado" and venta.cobrado > dec(venta.total) + Decimal("0.01"):
            raise ErrorNegocio(f"El cobro supera el saldo de la venta (total {venta.total:.2f}).")
        i.cliente_id = venta.cliente_id
        i.finca_id = venta.finca_id
        i.campana_id = venta.campana_id
        cultivos = {d.cultivo_id for d in venta.detalles}
        i.cultivo_id = cultivos.pop() if len(cultivos) == 1 else None


def eliminar_ingreso(i):
    pass


# ------------------------------------------------------------------ Cuentas a pagar manuales
def guardar_cuenta_pagar(c, nuevo, anterior):
    if not nuevo and c.origen != "manual" and anterior and dec(anterior.get("importe")) != dec(c.importe):
        raise ErrorNegocio("El importe de esta cuenta se genera desde su origen (compra, gasto o combustible).")
    if dec(c.importe) < dec(c.pagado):
        raise ErrorNegocio("El importe no puede ser menor a lo ya pagado.")


def eliminar_cuenta_pagar(c):
    if c.origen != "manual":
        raise ErrorNegocio("Esta cuenta se generó desde una compra, gasto o carga de combustible. "
                           "Eliminá ese registro.")
    if dec(c.pagado) > 0:
        raise ErrorNegocio("La cuenta tiene pagos registrados.")
