"""Declaración de todos los módulos ABM del sistema.

Para agregar un módulo nuevo alcanza con declarar aquí su modelo, campos, columnas y reglas: el motor
(engine.py) genera listado con filtros, formulario, detalle, eliminación, exportación, permisos y auditoría.
"""
from datetime import date
from decimal import Decimal

from flask import url_for
from sqlalchemy import func, select

from ..extensions import db
from ..models import (CATEGORIAS_INSUMO, METODOS_PAGO, MODALIDADES_PAGO, TIPOS_EMPLEADO, ActividadCultivo, Alerta,
                      AplicacionAgroquimico, AplicacionFertilizante, Campana, CargaCombustible, CategoriaGasto,
                      Cliente, Cosecha, CuentaPagar, Cultivo, Empleado, Finca, Gasto, Ingreso, Insumo, Lote, Maquina,
                      MovimientoInventario, PagoEmpleado, Proveedor, Riego, Siembra, Trabajo, UnidadMedida,
                      UsoMaquinaria, Venta, dec)
from ..services import gastos_auto, inventario, operaciones as op
from ..services import opciones as ops
from ..services.tenant import consulta, empresa_id, fincas_permitidas, usuario_actual
from ..utils.formato import fecha as ffecha, moneda, numero
from ..utils.validacion import ErrorNegocio
from .campos import ESTADOS_ACTIVA, ESTADOS_ACTIVO, C, Campo
from .modulo import Modulo

HOY = date.today


def _usuario_id():
    u = usuario_actual()
    return u.id if u else None


# ---------------------------------------------------------------- listas de opciones
TIPOS_CULTIVO = [("hortaliza", "Hortaliza"), ("cereal", "Cereal"), ("oleaginosa", "Oleaginosa"),
                 ("legumbre", "Legumbre"), ("forrajera", "Forrajera"), ("frutal", "Frutal"), ("otro", "Otro")]
TIPOS_UNIDAD = [("masa", "Peso (base kg)"), ("volumen", "Volumen (base litro)"), ("unidad", "Unidades"),
                ("otro", "Otro")]
ESTADOS_CAMPANA = [("planificada", "Planificada"), ("activa", "Activa"), ("cerrada", "Cerrada")]
ESTADOS_SIEMBRA = [("planificada", "Pendiente de siembra"), ("en_curso", "Sembrado / en curso"), ("cosechada", "Cosechada"),
                   ("perdida", "Perdida")]
TIPOS_ACTIVIDAD = [("preparacion", "Preparación del terreno"), ("siembra", "Siembra"),
                   ("fertilizacion", "Fertilización"), ("agroquimicos", "Aplicación de agroquímicos"),
                   ("riego", "Riego"), ("malezas", "Control de malezas"), ("plagas", "Control de plagas"),
                   ("mantenimiento", "Mantenimiento"), ("cosecha", "Cosecha"), ("otra", "Otra")]
ESTADOS_ACTIVIDAD = [("pendiente", "Pendiente"), ("realizada", "Realizada")]
SISTEMAS_RIEGO = [("goteo", "Goteo"), ("aspersion", "Aspersión"), ("gravedad", "Gravedad / surco"),
                  ("pivote", "Pivote"), ("otro", "Otro")]
TIPOS_INSUMO_SUGERIDOS = ["Urea", "NPK", "Fosfato diamónico", "Nitrato de amonio", "Sulfato de potasio",
                          "Foliar", "Orgánico", "Herbicida", "Fungicida", "Insecticida", "Acaricida",
                          "Coadyuvante", "Semilla certificada", "Semilla propia", "Filtro", "Aceite", "Otro"]
TIPOS_MOVIMIENTO = [("entrada", "Entrada (ingreso al stock)"), ("salida", "Salida (consumo)"),
                    ("ajuste", "Ajuste de inventario (+/-)")]
TIPOS_MAQUINA = [("tractor", "Tractor"), ("sembradora", "Sembradora"), ("cosechadora", "Cosechadora"),
                 ("pulverizadora", "Pulverizadora"), ("acoplado", "Acoplado"), ("camion", "Camión"),
                 ("arado", "Arado / rastra"), ("otra", "Otra maquinaria")]
ESTADOS_MAQUINA = [("operativa", "Operativa"), ("en_reparacion", "En reparación"),
                   ("fuera_servicio", "Fuera de servicio"), ("vendida", "Vendida")]
TRABAJOS_MAQUINA = ["Preparación del terreno", "Arada", "Rastreada", "Siembra", "Pulverización", "Fertilización",
                    "Cosecha", "Transporte", "Carga", "Mantenimiento de caminos"]
TIPOS_COMBUSTIBLE = [("gasoil", "Gasoil"), ("gasoil_premium", "Gasoil premium"), ("nafta", "Nafta"),
                     ("otro", "Otro")]
TIPOS_TRABAJO = ["Carga de bolsas", "Trabajo con tractor", "Cosecha", "Siembra", "Riego", "Carpida / limpieza",
                 "Aplicación", "Embolsado", "Clasificación", "Mantenimiento", "Sueldo mensual", "Otro"]
CONCEPTOS_PAGO = ["Pago de jornales", "Quincena", "Sueldo mensual", "Adelanto", "Aguinaldo", "Bono", "Otro"]
CALIDADES = [("primera", "Primera"), ("segunda", "Segunda"), ("tercera", "Tercera"), ("mixta", "Mixta"),
             ("descarte", "Descarte")]
ESTADOS_INGRESO = [("acreditado", "Acreditado"), ("a_depositar", "A depositar / pendiente"),
                   ("rechazado", "Rechazado")]
TIPOS_CLIENTE = [("mayorista", "Mayorista"), ("minorista", "Minorista"), ("acopiador", "Acopiador"),
                 ("industria", "Industria"), ("mercado", "Mercado / feria"), ("exportador", "Exportador"),
                 ("particular", "Particular"), ("otro", "Otro")]
TIPOS_PROVEEDOR = [("semillas", "Semillas"), ("fertilizantes", "Fertilizantes"), ("agroquimicos", "Agroquímicos"),
                   ("combustible", "Combustible"), ("repuestos", "Repuestos"), ("maquinaria", "Maquinaria"),
                   ("servicios", "Servicios"), ("transporte", "Transporte"), ("otro", "Otro")]
TIPOS_ALERTA = [("tarea", "Tarea"), ("recordatorio", "Recordatorio"), ("mantenimiento", "Mantenimiento"),
                ("vencimiento", "Vencimiento"), ("otro", "Otro")]
PRIORIDADES = [("baja", "Baja"), ("media", "Media"), ("alta", "Alta")]
ESTADOS_ALERTA = [("pendiente", "Pendiente"), ("resuelta", "Resuelta")]
ESTADOS_CUENTA = [("pendiente", "Pendiente"), ("parcial", "Parcial"), ("vencido", "Vencido"), ("pagado", "Pagado")]


# ---------------------------------------------------------------- campos reutilizables
def c_finca(requerido=True):
    return Campo("finca_id", "Finca", "select", requerido=requerido, opciones=ops.fincas, defecto=ops.finca_unica_id,
                 mostrar="finca.nombre")


def c_lote():
    return Campo("lote_id", "Lote", "select", opciones=ops.lotes, depende="finca_id", mostrar="lote.nombre")


def c_campana(requerido=False):
    return Campo("campana_id", "Campaña", "select", requerido=requerido, opciones=ops.campanas,
                 defecto=ops.campana_activa_id, mostrar="campana.nombre")


def c_cultivo(requerido=False):
    return Campo("cultivo_id", "Cultivo", "select", requerido=requerido, opciones=ops.cultivos,
                 mostrar="cultivo.nombre")


def imputacion(finca=True, campana=False, cultivo=False, lote=True):
    campos = [c_finca(finca)]
    if lote:
        campos.append(c_lote())
    campos += [c_campana(campana), c_cultivo(cultivo)]
    return campos


def c_fecha(nombre="fecha", etiqueta="Fecha"):
    return Campo(nombre, etiqueta, "date", requerido=True, defecto=HOY)


def c_obs():
    return Campo("observaciones", "Observaciones", "textarea", ancho="completo", maxlen=5000)


def c_responsable(nombre="responsable_id"):
    return Campo(nombre, "Responsable", "select", opciones=ops.usuarios, defecto=_usuario_id,
                 mostrar="responsable.nombre")


COLS_IMPUTACION = [C("finca.nombre", "Finca"), C("lote.nombre", "Lote", movil=False),
                   C("cultivo.nombre", "Cultivo")]


def tabla(titulo, columnas, filas, enlace=None, vacio="Sin registros."):
    return {"tipo": "tabla", "titulo": titulo, "columnas": columnas, "filas": filas, "enlace": enlace,
            "vacio": vacio}


def kpis(titulo, items):
    return {"tipo": "kpis", "titulo": titulo, "items": items}


# ================================================================ FINCAS
def _superficie_cultivada(finca_id):
    return db.session.scalar(select(func.coalesce(func.sum(Siembra.superficie), 0)).where(
        Siembra.finca_id == finca_id, Siembra.estado == "en_curso")) or Decimal("0")


def _validar_finca(datos, obj):
    if datos.get("superficie_cultivable") and datos.get("superficie_total") is not None \
            and datos["superficie_cultivable"] > datos["superficie_total"]:
        return {"superficie_cultivable": "No puede superar la superficie total."}
    return {}


Modulo(
    "fincas", "Fincas", "Finca", Finca, genero="a", icono="finca", finca_attr="id",
    campos=[
        Campo("nombre", "Nombre", requerido=True, maxlen=80, placeholder="Ej: Finca 1, El Alto…"),
        Campo("ubicacion", "Ubicación", maxlen=150),
        Campo("superficie_total", "Superficie total (ha)", "decimal", requerido=True),
        Campo("superficie_cultivable", "Hectáreas disponibles para cultivo", "decimal", requerido=True,
              ayuda="Superficie apta para sembrar. Las hectáreas cultivadas se calculan con las siembras en curso."),
        Campo("tipo_suelo", "Tipo de suelo", maxlen=60),
        Campo("responsable_id", "Responsable", "select", opciones=ops.usuarios, mostrar="responsable.nombre"),
        Campo("estado", "Estado", "choice", requerido=True, opciones=ESTADOS_ACTIVA, defecto="activa"),
        c_obs(),
    ],
    columnas=[
        C("nombre", "Finca"), C("ubicacion", "Ubicación", movil=False),
        C("superficie_total", "Total (ha)", "num"), C("superficie_cultivable", "Disponibles (ha)", "num"),
        C(lambda f: _superficie_cultivada(f.id), "Cultivadas (ha)", "num"),
        C(lambda f: dec(f.superficie_cultivable) - _superficie_cultivada(f.id), "Sin cultivar (ha)", "num"),
        C("responsable.nombre", "Responsable", movil=False), C("estado", "Estado", "estado"),
    ],
    filtros=["q", "estado"], buscar_en=["nombre", "ubicacion"], estados=ESTADOS_ACTIVA,
    orden=lambda: Finca.nombre, validar=_validar_finca,
    detalle_url=lambda f: url_for("fincas.dashboard", finca_id=f.id),
    entidad_documento="finca", descripcion=lambda f: f.nombre,
    ayuda="Las fincas se crean y renombran desde aquí. Cada una tiene su propio tablero con producción, gastos y ganancia.",
)


# ================================================================ LOTES
def _validar_lote(datos, obj):
    finca = db.session.get(Finca, datos.get("finca_id")) if datos.get("finca_id") else None
    if finca and datos.get("superficie") is not None:
        stmt = select(func.coalesce(func.sum(Lote.superficie), 0)).where(Lote.finca_id == finca.id,
                                                                          Lote.estado == "activo")
        if obj is not None and obj.id:
            stmt = stmt.where(Lote.id != obj.id)
        ocupado = db.session.scalar(stmt) or 0
        if dec(ocupado) + datos["superficie"] > dec(finca.superficie_total):
            return {"superficie": f"La suma de lotes ({dec(ocupado) + datos['superficie']:.2f} ha) supera la "
                                  f"superficie total de la finca ({finca.superficie_total} ha)."}
    return {}


Modulo(
    "lotes", "Lotes", "Lote", Lote, icono="lotes",
    campos=[
        c_finca(),
        Campo("nombre", "Nombre / número", requerido=True, maxlen=60, placeholder="Ej: Lote A"),
        Campo("superficie", "Superficie (ha)", "decimal", requerido=True),
        Campo("tipo_suelo", "Tipo de suelo", maxlen=60),
        Campo("estado", "Estado", "choice", requerido=True, opciones=ESTADOS_ACTIVO, defecto="activo"),
        c_obs(),
    ],
    columnas=[C("finca.nombre", "Finca"), C("nombre", "Lote"), C("superficie", "Superficie (ha)", "num"),
              C(lambda l: {"circulo": "Pivote", "rectangulo": "Rectángulo", "poligono": "Polígono"}.get(l.forma, "Sin dibujar"),
                "Mapa", movil=False),
              C("tipo_suelo", "Suelo", movil=False), C("estado", "Estado", "estado")],
    filtros=["finca", "q", "estado"], buscar_en=["nombre"], estados=ESTADOS_ACTIVO, totales=["superficie"],
    orden=lambda: (Lote.finca_id, Lote.nombre), validar=_validar_lote,
    descripcion=lambda l: f"{l.nombre} ({l.finca.nombre})",
    acciones_detalle=lambda l: [("Ver en el mapa", url_for("mapa.index", lote=l.id), "btn")],
    detalle_extra=lambda l: [tabla(
        "Siembras en este lote", ["Fecha", "Campaña", "Cultivo", "Ha", "Estado"],
        [[ffecha(s.fecha_siembra), s.campana.nombre, s.cultivo.nombre, numero(s.superficie), s.estado]
         for s in db.session.scalars(select(Siembra).where(Siembra.lote_id == l.id)
                                     .order_by(Siembra.fecha_siembra.desc()).limit(20)).unique()])],
)


# ================================================================ CAMPAÑAS
def _validar_campana(datos, obj):
    if datos.get("fecha_inicio") and datos.get("fecha_fin") and datos["fecha_fin"] < datos["fecha_inicio"]:
        return {"fecha_fin": "La fecha de fin debe ser posterior al inicio."}
    return {}


Modulo(
    "campanas", "Campañas", "Campaña", Campana, genero="a", icono="campana", finca_attr=None,
    campos=[
        Campo("nombre", "Nombre", requerido=True, maxlen=40, placeholder="Ej: 2026/2027"),
        Campo("fecha_inicio", "Inicio", "date", requerido=True),
        Campo("fecha_fin", "Fin", "date", requerido=True),
        Campo("estado", "Estado", "choice", requerido=True, opciones=ESTADOS_CAMPANA, defecto="activa",
              ayuda="La campaña activa se preselecciona en todos los formularios."),
        c_obs(),
    ],
    columnas=[C("nombre", "Campaña"), C("fecha_inicio", "Inicio", "fecha"), C("fecha_fin", "Fin", "fecha"),
              C("estado", "Estado", "estado")],
    filtros=["estado"], estados=ESTADOS_CAMPANA, orden=lambda: Campana.fecha_inicio.desc(),
    validar=_validar_campana, descripcion=lambda c: c.nombre,
    acciones_detalle=lambda c: [("Ver rentabilidad", url_for("rentabilidad.index", campana=c.id), "btn")],
)


# ================================================================ CULTIVOS
Modulo(
    "cultivos", "Cultivos", "Cultivo", Cultivo, icono="cultivo", finca_attr=None,
    campos=[
        Campo("nombre", "Nombre", requerido=True, maxlen=60, placeholder="Ej: Papa"),
        Campo("tipo", "Tipo", "choice", requerido=True, opciones=TIPOS_CULTIVO, defecto="hortaliza"),
        Campo("unidad_id", "Unidad de producción", "select", requerido=True, opciones=ops.unidades,
              mostrar="unidad.nombre", ayuda="En esta unidad se cargan las cosechas (toneladas, bolsas, quintales…)."),
        Campo("color", "Color en gráficos", maxlen=7, placeholder="#4a7c3a"),
        Campo("descripcion", "Descripción", "textarea", ancho="completo"),
        Campo("estado", "Estado", "choice", requerido=True, opciones=ESTADOS_ACTIVO, defecto="activo"),
    ],
    columnas=[C("nombre", "Cultivo"), C("tipo", "Tipo"), C("unidad.nombre", "Unidad"), C("estado", "Estado", "estado")],
    filtros=["q", "estado"], buscar_en=["nombre"], estados=ESTADOS_ACTIVO, orden=lambda: Cultivo.nombre,
    descripcion=lambda c: c.nombre,
    acciones_detalle=lambda c: [("Ver rentabilidad", url_for("rentabilidad.index", cultivo=c.id), "btn")],
)


# ================================================================ UNIDADES
Modulo(
    "unidades", "Unidades de medida", "Unidad", UnidadMedida, genero="a", icono="regla", finca_attr=None,
    campos=[
        Campo("nombre", "Nombre", requerido=True, maxlen=40, placeholder="Ej: Bolsa 25 kg"),
        Campo("abreviatura", "Abreviatura", requerido=True, maxlen=12, placeholder="Ej: bolsa"),
        Campo("tipo", "Tipo", "choice", requerido=True, opciones=TIPOS_UNIDAD, defecto="masa"),
        Campo("factor_base", "Equivalencia", "decimal", requerido=True, defecto="1",
              ayuda="Cuántos kg (o litros) equivale 1 unidad. Tonelada = 1000, Quintal = 100, Bolsa 25 kg = 25."),
        Campo("activa", "Activa", "bool", defecto=True),
    ],
    columnas=[C("nombre", "Unidad"), C("abreviatura", "Abrev."), C("tipo", "Tipo"),
              C("factor_base", "Equivale a", "num"), C("activa", "Activa", "bool")],
    orden=lambda: UnidadMedida.nombre, descripcion=lambda u: u.nombre,
)


# ================================================================ CATEGORÍAS DE GASTO
def _guardar_categoria(c, nuevo, anterior):
    if not c.codigo:
        import re
        import unicodedata
        base = unicodedata.normalize("NFKD", c.nombre).encode("ascii", "ignore").decode().lower()
        c.codigo = (re.sub(r"[^a-z0-9]+", "_", base).strip("_") or "categoria")[:25] + f"_{c.id}"


Modulo(
    "categorias_gasto", "Categorías de gasto", "Categoría", CategoriaGasto, genero="a", icono="tag",
    finca_attr=None,
    campos=[
        Campo("nombre", "Nombre", requerido=True, maxlen=60),
        Campo("orden", "Orden", "int", defecto=50),
        Campo("activa", "Activa", "bool", defecto=True),
    ],
    columnas=[C("nombre", "Categoría"), C("codigo", "Código", movil=False), C("orden", "Orden"),
              C("activa", "Activa", "bool")],
    orden=lambda: (CategoriaGasto.orden, CategoriaGasto.nombre), guardar=_guardar_categoria,
    descripcion=lambda c: c.nombre,
)


# ================================================================ SIEMBRAS
def _validar_siembra(datos, obj):
    errores = {}
    if datos.get("lote_id") and datos.get("superficie"):
        lote = db.session.get(Lote, datos["lote_id"])
        if lote and datos["superficie"] > dec(lote.superficie):
            errores["superficie"] = f"El lote tiene {lote.superficie} ha."
    if datos.get("insumo_id") and not datos.get("cantidad_semilla"):
        errores["cantidad_semilla"] = "Indicá la cantidad de semilla que sale del inventario."
    insumo = db.session.get(Insumo, datos["insumo_id"]) if datos.get("insumo_id") else None
    if insumo and datos.get("origen_semilla") and datos["origen_semilla"] != ("propia" if insumo.propia else "comprada"):
        errores["insumo_id"] = (f"«{insumo.nombre}» es semilla {'propia' if insumo.propia else 'comprada'}; "
                                "cambiá el origen o elegí otra semilla.")
    if datos.get("origen_semilla") == "propia" and datos.get("costo_semilla"):
        errores["costo_semilla"] = "La semilla propia no lleva precio. Dejalo vacío o elegí «Comprada»."
    if datos.get("fecha_cosecha_estimada") and datos.get("fecha_siembra") \
            and datos["fecha_cosecha_estimada"] < datos["fecha_siembra"]:
        errores["fecha_cosecha_estimada"] = "Debe ser posterior a la siembra."
    return errores


Modulo(
    "siembras", "Siembras", "Siembra", Siembra, genero="a", icono="siembra",
    campos=imputacion(campana=True, cultivo=True) + [
        c_fecha("fecha_siembra", "Fecha de siembra"),
        Campo("superficie", "Superficie sembrada (ha)", "decimal", requerido=True),
        Campo("variedad", "Variedad", maxlen=60, placeholder="Ej: Spunta"),
        Campo("distancia_surcos", "Distancia entre surcos (m)", "decimal", maximo=Decimal("5"),
              ayuda="Ej: 0,75 para papa; 0,52 o 0,70 para maíz."),
        Campo("origen_semilla", "Origen de la semilla", "choice", opciones=op.ORIGENES_SEMILLA, seccion="Semilla",
              defecto="comprada",
              ayuda="Propia: la guardaron ustedes de la cosecha (no lleva precio). Comprada: lleva precio."),
        Campo("insumo_id", "Semilla del inventario", "select", opciones=lambda: ops.insumos("semilla"),
              mostrar="insumo.nombre", seccion="Semilla",
              ayuda="Si la semilla sale del galpón, elegila: se descuenta del stock (la comprada calcula su costo sola)."),
        Campo("cantidad_semilla", "Cantidad de semilla", "decimal", seccion="Semilla"),
        Campo("unidad_semilla_id", "Unidad", "select", opciones=ops.unidades, mostrar="unidad_semilla.abreviatura",
              seccion="Semilla"),
        Campo("proveedor_id", "Proveedor de semilla", "select", opciones=ops.proveedores, mostrar="proveedor.razon_social",
              seccion="Semilla"),
        Campo("costo_semilla", "Precio de la semilla comprada ($)", "money", seccion="Semilla",
              ayuda="Sólo semilla comprada directo (no del inventario). La semilla propia no lleva precio."),
        c_responsable(),
        Campo("fecha_cosecha_estimada", "Cosecha estimada", "date", seccion="Estimaciones"),
        Campo("rendimiento_estimado", "Rendimiento esperado por ha", "decimal", seccion="Estimaciones",
              ayuda="En la unidad del cultivo (ej. 30 t/ha)."),
        Campo("estado", "Estado", "choice", requerido=True, opciones=ESTADOS_SIEMBRA, defecto="en_curso"),
        c_obs(),
    ],
    columnas=[C("fecha_siembra", "Fecha", "fecha")] + COLS_IMPUTACION + [
        C("variedad", "Variedad", movil=False), C("superficie", "Ha", "num"),
        C(lambda s: {"propia": "Propia", "comprada": "Comprada"}.get(s.origen_semilla, "—"), "Semilla", movil=False),
        C("costo_semilla", "Semilla $", "moneda", movil=False),
        C("fecha_cosecha_estimada", "Cosecha est.", "fecha", movil=False), C("estado", "Estado", "estado")],
    filtros=["finca", "lote", "campana", "cultivo", "fecha", "estado", "q"], buscar_en=["variedad"],
    estados=ESTADOS_SIEMBRA, campo_fecha="fecha_siembra", totales=["superficie", "costo_semilla"],
    orden=lambda: Siembra.fecha_siembra.desc(), validar=_validar_siembra,
    guardar=op.guardar_siembra, eliminar=op.eliminar_siembra, origen_gasto="siembra",
    descripcion=lambda s: f"{s.cultivo.nombre} · {s.finca.nombre} · {s.superficie} ha",
    acciones_detalle=lambda s: [("Registrar cosecha", url_for("crud.nuevo", key="cosechas", siembra_id=s.id), "btn")]
    + ([("Ver en el mapa", url_for("mapa.index", lote=s.lote_id, campana=s.campana_id), "btn")] if s.lote_id else []),
)


# ================================================================ ACTIVIDADES
Modulo(
    "actividades", "Actividades del cultivo", "Actividad", ActividadCultivo, genero="a", icono="actividad",
    campos=imputacion() + [
        Campo("tipo", "Etapa / actividad", "choice", requerido=True, opciones=TIPOS_ACTIVIDAD),
        c_fecha(),
        Campo("estado", "Estado", "choice", requerido=True, opciones=ESTADOS_ACTIVIDAD, defecto="realizada",
              ayuda="Las pendientes aparecen en alertas, calendario y tablero de la finca."),
        Campo("descripcion", "Descripción", maxlen=200, ancho="completo"),
        c_responsable(),
        Campo("costo", "Costo adicional ($)", "money",
              ayuda="Servicios contratados u otros costos. No repitas insumos ya cargados en Fertilizantes/"
                    "Agroquímicos ni mano de obra cargada en Trabajos."),
        Campo("categoria_gasto_id", "Categoría del costo", "select", opciones=ops.categorias_gasto,
              mostrar="categoria_gasto.nombre", ayuda="Si la dejás vacía se elige según la etapa."),
        c_obs(),
    ],
    columnas=[C("fecha", "Fecha", "fecha"), C("tipo", "Actividad", "choice")] + COLS_IMPUTACION + [
        C("responsable.nombre", "Responsable", movil=False), C("costo", "Costo", "moneda"),
        C("estado", "Estado", "estado")],
    filtros=["finca", "lote", "campana", "cultivo", "fecha", "tipo", "estado", "responsable"],
    tipos=TIPOS_ACTIVIDAD, estados=ESTADOS_ACTIVIDAD, buscar_primero=True, totales=["costo"],
    orden=lambda: ActividadCultivo.fecha.desc(), guardar=op.guardar_actividad, eliminar=op.eliminar_actividad,
    origen_gasto="actividad", descripcion=lambda a: f"{dict(TIPOS_ACTIVIDAD).get(a.tipo)} · {a.finca.nombre}",
)


# ================================================================ RIEGO
Modulo(
    "riegos", "Riego", "Riego", Riego, icono="riego",
    campos=imputacion() + [
        c_fecha(),
        Campo("horas", "Horas de riego", "decimal", requerido=True),
        Campo("sistema", "Sistema", "choice", requerido=True, opciones=SISTEMAS_RIEGO, defecto="goteo"),
        Campo("consumo", "Consumo", "decimal"),
        Campo("unidad_consumo", "Unidad de consumo", "choice",
              opciones=[("m3", "m³ de agua"), ("kwh", "kWh"), ("litros", "Litros de combustible"), ("turno", "Turnos")]),
        Campo("costo", "Costo estimado ($)", "money"),
        c_responsable(), c_obs(),
    ],
    columnas=[C("fecha", "Fecha", "fecha")] + COLS_IMPUTACION + [
        C("sistema", "Sistema", "choice"), C("horas", "Horas", "num"), C("consumo", "Consumo", "num", movil=False),
        C("costo", "Costo", "moneda")],
    filtros=["finca", "lote", "campana", "cultivo", "fecha"], totales=["horas", "costo"],
    orden=lambda: Riego.fecha.desc(), guardar=op.guardar_riego, eliminar=op.eliminar_riego, origen_gasto="riego",
    descripcion=lambda r: f"{r.finca.nombre} · {r.horas} h",
)


# ================================================================ INSUMOS
def _guardar_insumo(i, nuevo, anterior):
    if i.propia and i.categoria != "semilla":
        raise ErrorNegocio("Sólo una semilla puede marcarse como «propia».")
    inventario.inventario_de(i)
    extra = getattr(i, "_extra", {})
    if nuevo and extra.get("stock_inicial"):
        inventario.registrar(i, "entrada", extra["stock_inicial"], HOY(),
                             precio_unitario=0 if i.propia else (extra.get("costo_inicial") or 0),
                             origen="manual", observaciones="Stock inicial")


def _stock(i):
    return f"{numero(i.stock)} {i.unidad.abreviatura}"


Modulo(
    "insumos", "Insumos", "Insumo", Insumo, icono="insumo", finca_attr=None,
    campos=[
        Campo("nombre", "Producto", requerido=True, maxlen=100),
        Campo("categoria", "Categoría", "choice", requerido=True, opciones=CATEGORIAS_INSUMO),
        Campo("tipo", "Tipo", maxlen=40, opciones=[(t, t) for t in TIPOS_INSUMO_SUGERIDOS],
              placeholder="Ej: Urea, NPK, Herbicida…"),
        Campo("unidad_id", "Unidad", "select", requerido=True, opciones=ops.unidades, mostrar="unidad.nombre"),
        Campo("principio_activo", "Principio activo / composición", maxlen=120),
        Campo("propia", "Semilla propia (la guardamos de nuestras cosechas, sin costo)", "bool", defecto=False,
              ayuda="Sólo para semillas. Ej: «Semilla de papa propia». Su stock entra desde las cosechas y no tiene precio."),
        Campo("stock_minimo", "Stock mínimo (alerta)", "decimal", defecto="0"),
        Campo("proveedor_id", "Proveedor habitual", "select", opciones=ops.proveedores,
              mostrar="proveedor.razon_social"),
        Campo("estado", "Estado", "choice", requerido=True, opciones=ESTADOS_ACTIVO, defecto="activo"),
        Campo("stock_inicial", "Stock inicial", "decimal", virtual=True, solo_crear=True, seccion="Stock inicial",
              ayuda="Lo que hay hoy en el galpón (opcional)."),
        Campo("costo_inicial", "Costo unitario del stock inicial ($)", "money", virtual=True, solo_crear=True,
              seccion="Stock inicial"),
        c_obs(),
    ],
    columnas=[C(lambda i: i.nombre + (" (propia)" if i.propia else ""), "Producto"), C("categoria", "Categoría", "choice"),
              C("tipo", "Tipo", movil=False),
              C(_stock, "Stock"), C("costo_promedio", "Costo prom.", "moneda", movil=False),
              C(lambda i: i.stock * i.costo_promedio, "Valor stock", "moneda", movil=False),
              C(lambda i: "bajo" if i.stock_minimo and i.stock < i.stock_minimo else "ok", "Alerta", "estado")],
    filtros=["q", "tipo", "estado"], buscar_en=["nombre", "tipo", "principio_activo"], tipos=CATEGORIAS_INSUMO,
    tipo_attr="categoria", estados=ESTADOS_ACTIVO, filtro_fijo=["categoria"], buscar_primero=False,
    orden=lambda: Insumo.nombre, guardar=_guardar_insumo, descripcion=lambda i: i.nombre,
    enlaces=[("Registrar compra", "compras.nuevo"), ("Movimientos de stock", "crud.listar:movimientos"),
             ("Stock actual", "inventario.stock")],
    detalle_extra=lambda i: [
        kpis("Stock", [("Stock actual", _stock(i)), ("Costo promedio", moneda(i.costo_promedio, 2)),
                       ("Valor del stock", moneda(i.stock * i.costo_promedio))]),
        tabla("Últimos movimientos", ["Fecha", "Tipo", "Cantidad", "Precio", "Origen"],
              [[ffecha(m.fecha), m.tipo, numero(m.cantidad), moneda(m.precio_unitario, 2), m.origen]
               for m in db.session.scalars(select(MovimientoInventario).where(MovimientoInventario.insumo_id == i.id)
                                           .order_by(MovimientoInventario.fecha.desc(),
                                                     MovimientoInventario.id.desc()).limit(25)).unique()],
              enlace=("Ver todos", url_for("crud.listar", key="movimientos", insumo=i.id, buscar=1)))],
)


# ================================================================ MOVIMIENTOS DE INVENTARIO
def _editable_mov(m):
    if m.origen != "manual":
        return False, "Este movimiento lo generó una compra, siembra o aplicación: modificá ese registro."
    return True, None


Modulo(
    "movimientos", "Movimientos de inventario", "Movimiento", MovimientoInventario, icono="stock",
    campos=[
        Campo("insumo_id", "Insumo", "select", requerido=True, opciones=ops.insumos, mostrar="insumo.nombre"),
        Campo("tipo", "Tipo de movimiento", "choice", requerido=True, opciones=TIPOS_MOVIMIENTO, defecto="salida"),
        c_fecha(),
        Campo("cantidad", "Cantidad", "decimal", requerido=True, minimo=Decimal("-999999999"),
              ayuda="En ajustes usá números negativos para descontar."),
        Campo("precio_unitario", "Precio unitario ($)", "money",
              ayuda="Sólo en entradas. En salidas se usa el costo promedio."),
        Campo("proveedor_id", "Proveedor", "select", opciones=ops.proveedores, mostrar="proveedor.razon_social"),
    ] + [c_finca(False), c_lote(), c_campana(), c_cultivo()] + [c_obs()],
    columnas=[C("fecha", "Fecha", "fecha"), C("insumo.nombre", "Insumo"), C("tipo", "Tipo", "choice"),
              C("cantidad", "Cantidad", "num"), C("precio_unitario", "Precio", "moneda", movil=False),
              C("finca.nombre", "Finca", movil=False), C("origen", "Origen", movil=False)],
    filtros=["insumo", "finca", "fecha", "tipo"], tipos=TIPOS_MOVIMIENTO, buscar_primero=True,
    orden=lambda: (MovimientoInventario.fecha.desc(), MovimientoInventario.id.desc()),
    guardar=op.guardar_movimiento, eliminar=op.eliminar_movimiento, editable=_editable_mov,
    origen_gasto="movimiento", usuario_attr="responsable_id",
    descripcion=lambda m: f"{m.tipo} de {m.insumo.nombre} ({m.cantidad})",
    ayuda="Las compras, siembras y aplicaciones generan sus movimientos solas. Aquí se cargan consumos sueltos "
          "(ej. repuestos usados en una finca) y ajustes de inventario.",
)


# ================================================================ APLICACIONES
Modulo(
    "aplicaciones_fertilizantes", "Fertilizantes · aplicaciones", "Aplicación de fertilizante",
    AplicacionFertilizante, genero="a", icono="fertilizante",
    campos=imputacion(cultivo=True) + [
        Campo("insumo_id", "Fertilizante", "select", requerido=True, opciones=lambda: ops.insumos("fertilizante"),
              mostrar="insumo.nombre"),
        c_fecha(),
        Campo("superficie", "Superficie aplicada (ha)", "decimal"),
        Campo("cantidad", "Cantidad aplicada", "decimal", requerido=True,
              ayuda="En la unidad del producto. Se descuenta del stock y se calcula el costo."),
        c_responsable(), c_obs(),
    ],
    columnas=[C("fecha", "Fecha", "fecha")] + COLS_IMPUTACION + [
        C("insumo.nombre", "Producto"), C("cantidad", "Cantidad", "num"),
        C("dosis_ha", "Dosis/ha", "num", movil=False), C("costo_total", "Costo", "moneda")],
    filtros=["finca", "lote", "campana", "cultivo", "insumo", "fecha"], totales=["costo_total"],
    orden=lambda: AplicacionFertilizante.fecha.desc(),
    guardar=op.guardar_aplicacion_fertilizante, eliminar=op.eliminar_aplicacion_fertilizante,
    origen_gasto="aplicacion_fertilizante",
    descripcion=lambda a: f"{a.insumo.nombre} en {a.finca.nombre} ({a.cantidad})",
    enlaces=[("Productos fertilizantes", "crud.listar:insumos?categoria=fertilizante"),
             ("Registrar compra", "compras.nuevo")],
)


def _validar_agro(datos, obj):
    if not datos.get("cantidad"):
        if datos.get("dosis") and datos.get("superficie"):
            datos["cantidad"] = (datos["dosis"] * datos["superficie"]).quantize(Decimal("0.001"))
        else:
            return {"cantidad": "Indicá la cantidad total o la dosis y la superficie."}
    return {}


Modulo(
    "aplicaciones_agroquimicos", "Agroquímicos · aplicaciones", "Aplicación de agroquímico",
    AplicacionAgroquimico, genero="a", icono="agroquimico",
    campos=imputacion(cultivo=True) + [
        Campo("insumo_id", "Producto", "select", requerido=True, opciones=lambda: ops.insumos("agroquimico"),
              mostrar="insumo.nombre"),
        c_fecha(),
        Campo("motivo", "Motivo / plaga objetivo", maxlen=150, placeholder="Ej: Tizón tardío"),
        Campo("superficie", "Superficie (ha)", "decimal"),
        Campo("dosis", "Dosis por ha", "decimal"),
        Campo("unidad_dosis", "Unidad de dosis", "choice",
              opciones=[("l/ha", "l/ha"), ("cc/ha", "cc/ha"), ("kg/ha", "kg/ha"), ("g/ha", "g/ha")]),
        Campo("cantidad", "Cantidad total aplicada", "decimal",
              ayuda="Si la dejás vacía se calcula dosis × superficie (en la unidad del producto)."),
        c_responsable(), c_obs(),
    ],
    columnas=[C("fecha", "Fecha", "fecha")] + COLS_IMPUTACION + [
        C("insumo.nombre", "Producto"), C("insumo.tipo", "Tipo", movil=False), C("motivo", "Motivo", movil=False),
        C("cantidad", "Cantidad", "num"), C("costo_total", "Costo", "moneda")],
    filtros=["finca", "lote", "campana", "cultivo", "insumo", "fecha"], totales=["costo_total"],
    orden=lambda: AplicacionAgroquimico.fecha.desc(), validar=_validar_agro,
    guardar=op.guardar_aplicacion_agroquimico, eliminar=op.eliminar_aplicacion_agroquimico,
    origen_gasto="aplicacion_agroquimico",
    descripcion=lambda a: f"{a.insumo.nombre} en {a.finca.nombre} ({a.cantidad})",
    enlaces=[("Productos agroquímicos", "crud.listar:insumos?categoria=agroquimico"),
             ("Registrar compra", "compras.nuevo")],
)


# ================================================================ MAQUINARIA
def _detalle_maquina(m):
    usos = db.session.scalars(select(UsoMaquinaria).where(UsoMaquinaria.maquina_id == m.id)
                              .order_by(UsoMaquinaria.fecha.desc()).limit(20)).unique().all()
    litros = db.session.scalar(select(func.coalesce(func.sum(CargaCombustible.litros), 0)).where(
        CargaCombustible.maquina_id == m.id)) or 0
    gasto_comb = db.session.scalar(select(func.coalesce(func.sum(CargaCombustible.total), 0)).where(
        CargaCombustible.maquina_id == m.id)) or 0
    faltan = m.horas_para_mantenimiento
    return [
        kpis("Resumen", [("Horas de uso", numero(m.horas_uso, 1)),
                         ("Próximo service", f"en {numero(faltan, 0)} h" if faltan is not None else "—"),
                         ("Combustible cargado", f"{numero(litros, 0)} l"), ("Gasto combustible", moneda(gasto_comb))]),
        tabla("Últimos usos", ["Fecha", "Finca", "Trabajo", "Horas", "Operador", "Costo"],
              [[ffecha(u.fecha), u.finca.nombre, u.trabajo_realizado, numero(u.horas),
                str(u.operador) if u.operador else "—", moneda(u.costo_total)] for u in usos],
              enlace=("Ver todos", url_for("crud.listar", key="uso_maquinaria", maquina=m.id, buscar=1))),
    ]


Modulo(
    "maquinaria", "Maquinaria", "Máquina", Maquina, genero="a", icono="tractor",
    campos=[
        Campo("nombre", "Nombre", requerido=True, maxlen=80, placeholder="Ej: Tractor John Deere 5090"),
        Campo("tipo", "Tipo", "choice", requerido=True, opciones=TIPOS_MAQUINA),
        Campo("marca", "Marca", maxlen=50), Campo("modelo", "Modelo", maxlen=50),
        Campo("anio", "Año", "int", minimo=1950, maximo=2100),
        Campo("identificacion", "Patente / identificación", maxlen=30),
        Campo("horas_uso", "Horas de uso (horómetro)", "decimal", defecto="0"),
        Campo("estado", "Estado", "choice", requerido=True, opciones=ESTADOS_MAQUINA, defecto="operativa"),
        Campo("responsable_id", "Responsable", "select", opciones=ops.empleados, mostrar="responsable"),
        Campo("finca_id", "Finca base", "select", opciones=ops.fincas, mostrar="finca.nombre"),
        Campo("costo_hora", "Costo por hora a imputar ($)", "money", defecto="0",
              ayuda="Amortización o alquiler por hora que se carga al cultivo en cada uso. 0 = no imputar."),
        Campo("intervalo_mantenimiento_horas", "Service cada (horas)", "int", seccion="Mantenimiento"),
        Campo("ultimo_mantenimiento_horas", "Horas en el último service", "decimal", seccion="Mantenimiento"),
        Campo("proximo_mantenimiento_fecha", "Próximo mantenimiento (fecha)", "date", seccion="Mantenimiento"),
        c_obs(),
    ],
    columnas=[C("nombre", "Máquina"), C("tipo", "Tipo", "choice"), C("identificacion", "Patente", movil=False),
              C("horas_uso", "Horas", "num"), C("finca.nombre", "Finca", movil=False), C("estado", "Estado", "estado")],
    filtros=["q", "tipo", "estado", "finca"], buscar_en=["nombre", "marca", "modelo", "identificacion"],
    tipos=TIPOS_MAQUINA, estados=ESTADOS_MAQUINA, orden=lambda: Maquina.nombre,
    detalle_extra=_detalle_maquina, entidad_documento="maquina", descripcion=lambda m: m.nombre,
    acciones_detalle=lambda m: [("Registrar uso", url_for("crud.nuevo", key="uso_maquinaria", maquina_id=m.id), "btn"),
                                ("Cargar combustible", url_for("crud.nuevo", key="combustibles", maquina_id=m.id), "btn")],
)

Modulo(
    "uso_maquinaria", "Uso de maquinaria", "Uso de maquinaria", UsoMaquinaria, icono="tractor",
    campos=[
        Campo("maquina_id", "Máquina", "select", requerido=True, opciones=ops.maquinas, mostrar="maquina.nombre",
              autocompleta=True),
    ] + imputacion() + [
        c_fecha(),
        Campo("horas", "Horas trabajadas", "decimal", requerido=True),
        Campo("operador_id", "Operador", "select", opciones=ops.empleados, mostrar="operador"),
        Campo("trabajo_realizado", "Trabajo realizado", requerido=True, maxlen=150,
              opciones=[(t, t) for t in TRABAJOS_MAQUINA]),
        Campo("combustible_litros", "Combustible usado (litros)", "decimal", defecto="0", seccion="Costos"),
        Campo("costo_combustible", "Costo del combustible ($)", "money", defecto="0", seccion="Costos",
              ayuda="Dejalo en 0 si la carga ya se registró en Combustible (para no contarla dos veces)."),
        Campo("costo_mantenimiento", "Costo de mantenimiento ($)", "money", defecto="0", seccion="Costos"),
        Campo("costo_hora", "Costo por hora ($)", "money", defecto="0", seccion="Costos",
              ayuda="Se completa con el de la máquina."),
        c_obs(),
    ],
    columnas=[C("fecha", "Fecha", "fecha"), C("maquina.nombre", "Máquina")] + COLS_IMPUTACION + [
        C("trabajo_realizado", "Trabajo"), C("horas", "Horas", "num"), C("operador", "Operador", movil=False),
        C("combustible_litros", "Litros", "num", movil=False), C("costo_total", "Costo", "moneda")],
    filtros=["maquina", "finca", "lote", "campana", "cultivo", "fecha"], buscar_primero=True,
    totales=["horas", "combustible_litros", "costo_total"], orden=lambda: UsoMaquinaria.fecha.desc(),
    guardar=op.guardar_uso_maquinaria, eliminar=op.eliminar_uso_maquinaria, origen_gasto="uso_maquinaria",
    descripcion=lambda u: f"{u.maquina.nombre} · {u.trabajo_realizado} · {u.horas} h",
)

Modulo(
    "combustibles", "Combustible", "Carga de combustible", CargaCombustible, genero="a", icono="combustible",
    campos=[
        c_fecha(),
        Campo("tipo_combustible", "Combustible", "choice", requerido=True, opciones=TIPOS_COMBUSTIBLE,
              defecto="gasoil"),
        Campo("litros", "Litros", "decimal", requerido=True),
        Campo("precio_litro", "Precio por litro ($)", "money", requerido=True),
        Campo("maquina_id", "Vehículo / máquina", "select", opciones=ops.maquinas, mostrar="maquina.nombre"),
        c_finca(False), c_campana(), c_cultivo(),
        Campo("proveedor_id", "Proveedor", "select", opciones=ops.proveedores, mostrar="proveedor.razon_social"),
        Campo("metodo_pago", "Forma de pago", "choice", requerido=True, opciones=METODOS_PAGO, defecto="efectivo"),
        Campo("vencimiento", "Vencimiento (si es a pagar)", "date"),
        Campo("imputar_gasto", "Imputar como gasto de combustible", "bool", defecto=True,
              ayuda="Desmarcalo si el costo del combustible lo cargás en cada uso de maquinaria."),
        c_responsable(), c_obs(),
    ],
    columnas=[C("fecha", "Fecha", "fecha"), C("tipo_combustible", "Tipo", "choice"),
              C("maquina.nombre", "Máquina"), C("finca.nombre", "Finca"), C("litros", "Litros", "num"),
              C("precio_litro", "$/l", "moneda", movil=False), C("total", "Total", "moneda"),
              C("proveedor.razon_social", "Proveedor", movil=False)],
    filtros=["finca", "maquina", "campana", "cultivo", "fecha", "proveedor"], totales=["litros", "total"],
    orden=lambda: CargaCombustible.fecha.desc(), guardar=op.guardar_combustible, eliminar=op.eliminar_combustible,
    origen_gasto="combustible", descripcion=lambda c: f"{c.litros} l de {c.tipo_combustible}",
    enlaces=[("Reporte de combustible", "reportes.ver:combustible")],
)


# ================================================================ EMPLEADOS
def _saldo_empleado(e):
    devengado = db.session.scalar(select(func.coalesce(func.sum(Trabajo.total), 0)).where(
        Trabajo.empleado_id == e.id)) or 0
    costo_pagos = db.session.scalar(select(func.coalesce(func.sum(PagoEmpleado.monto), 0)).where(
        PagoEmpleado.empleado_id == e.id, PagoEmpleado.imputar_costo.is_(True))) or 0
    pagado = db.session.scalar(select(func.coalesce(func.sum(PagoEmpleado.monto), 0)).where(
        PagoEmpleado.empleado_id == e.id)) or 0
    return dec(devengado) + dec(costo_pagos), dec(pagado)


def _detalle_empleado(e):
    devengado, pagado = _saldo_empleado(e)
    trabajos = db.session.scalars(select(Trabajo).where(Trabajo.empleado_id == e.id)
                                  .order_by(Trabajo.fecha.desc()).limit(15)).unique().all()
    pagos = db.session.scalars(select(PagoEmpleado).where(PagoEmpleado.empleado_id == e.id)
                               .order_by(PagoEmpleado.fecha.desc()).limit(15)).unique().all()
    return [
        kpis("Cuenta del empleado", [("Trabajado (devengado)", moneda(devengado)), ("Pagado", moneda(pagado)),
                                     ("Saldo a pagar", moneda(devengado - pagado))]),
        tabla("Últimos trabajos", ["Fecha", "Trabajo", "Finca", "Detalle", "Total"],
              [[ffecha(t.fecha), t.tipo_trabajo, t.finca.nombre, _detalle_trabajo(t), moneda(t.total)] for t in trabajos],
              enlace=("Ver todos", url_for("crud.listar", key="trabajos", empleado=e.id, buscar=1))),
        tabla("Últimos pagos", ["Fecha", "Concepto", "Período", "Método", "Monto"],
              [[ffecha(p.fecha), p.concepto, p.periodo or "—", p.metodo_pago, moneda(p.monto)] for p in pagos],
              enlace=("Ver todos", url_for("crud.listar", key="pagos_empleados", empleado=e.id, buscar=1))),
    ]


def _validar_empleado(datos, obj):
    if datos.get("usuario_id"):
        stmt = select(Empleado).where(Empleado.usuario_id == datos["usuario_id"])
        if obj is not None and obj.id:
            stmt = stmt.where(Empleado.id != obj.id)
        if db.session.scalar(stmt):
            return {"usuario_id": "Ese usuario ya está vinculado a otro empleado."}
    return {}


def _filtro_tipo_empleado(stmt, valor, modelo):
    return stmt.join(Empleado, Empleado.id == modelo.empleado_id).where(Empleado.tipo == valor)


FILTRO_TIPO_EMPLEADO = {"nombre": "tipo_empleado", "etiqueta": "Tipo de trabajador", "opciones": TIPOS_EMPLEADO,
                        "aplicar": _filtro_tipo_empleado}

Modulo(
    "empleados", "Empleados", "Empleado", Empleado, icono="personas",
    campos=[
        Campo("nombre", "Nombre", requerido=True, maxlen=60), Campo("apellido", "Apellido", requerido=True, maxlen=60),
        Campo("dni", "DNI", maxlen=15), Campo("telefono", "Teléfono", "tel", maxlen=30),
        Campo("tipo", "Tipo de trabajador", "choice", requerido=True, opciones=TIPOS_EMPLEADO),
        Campo("puesto", "Puesto", maxlen=60), Campo("fecha_ingreso", "Fecha de ingreso", "date"),
        Campo("finca_id", "Finca asignada", "select", opciones=ops.fincas, mostrar="finca.nombre",
              defecto=ops.finca_unica_id),
        Campo("modalidad_pago", "Forma de pago habitual", "choice", opciones=MODALIDADES_PAGO),
        Campo("tarifa", "Tarifa habitual ($)", "money", ayuda="Por jornal, hora o unidad. Se sugiere al cargar trabajos."),
        Campo("estado", "Estado", "choice", requerido=True, opciones=ESTADOS_ACTIVO, defecto="activo"),
        Campo("usuario_id", "Usuario del sistema (opcional)", "select", opciones=ops.usuarios, mostrar="usuario.nombre",
              ayuda="Si el trabajador tiene usuario, vinculalo para que vea sus trabajos y pagos."),
        c_obs(),
    ],
    columnas=[C("nombre_completo", "Empleado"), C("tipo", "Tipo", "choice"), C("dni", "DNI", movil=False),
              C("telefono", "Teléfono", movil=False), C("finca.nombre", "Finca"), C("estado", "Estado", "estado")],
    filtros=["q", "finca", "tipo", "estado"], buscar_en=["nombre", "apellido", "dni"], tipos=TIPOS_EMPLEADO,
    estados=ESTADOS_ACTIVO, buscar_primero=True, orden=lambda: (Empleado.apellido, Empleado.nombre),
    validar=_validar_empleado, detalle_extra=_detalle_empleado, entidad_documento="empleado",
    descripcion=lambda e: e.nombre_completo,
    acciones_detalle=lambda e: [("Registrar trabajo", url_for("crud.nuevo", key="trabajos", empleado_id=e.id), "btn"),
                                ("Registrar pago", url_for("crud.nuevo", key="pagos_empleados", empleado_id=e.id), "btn")],
)


# ================================================================ TRABAJOS
def _detalle_trabajo(t):
    if t.modalidad == "hora":
        return f"{numero(t.horas)} h × {moneda(t.precio_unitario)}"
    if t.modalidad == "jornal":
        return f"{numero(t.jornales)} jornales × {moneda(t.precio_unitario)}"
    if t.modalidad == "unidad":
        return f"{numero(t.cantidad)} u × {moneda(t.precio_unitario, 2)}"
    return "Monto fijo"


Modulo(
    "trabajos", "Trabajos y mano de obra", "Trabajo", Trabajo, icono="trabajo",
    campos=[
        c_fecha(),
        Campo("empleado_id", "Trabajador", "select", requerido=True, opciones=ops.empleados, mostrar="empleado",
              autocompleta=True),
        Campo("tipo_trabajo", "Tipo de trabajo", requerido=True, maxlen=40, opciones=[(t, t) for t in TIPOS_TRABAJO]),
    ] + imputacion() + [
        Campo("modalidad", "Forma de pago", "choice", requerido=True, opciones=MODALIDADES_PAGO, defecto="jornal"),
        Campo("jornales", "Jornales", "decimal"),
        Campo("horas", "Horas", "decimal"),
        Campo("cantidad", "Unidades (bolsas, cajones…)", "decimal"),
        Campo("precio_unitario", "Precio por jornal / hora / unidad ($)", "money", requerido=True,
              ayuda="Con 'Monto fijo' es el total a pagar."),
        c_obs(),
    ],
    columnas=[C("fecha", "Fecha", "fecha"), C("empleado", "Trabajador"), C("tipo_trabajo", "Trabajo")]
    + COLS_IMPUTACION + [C(_detalle_trabajo, "Detalle", movil=False), C("total", "Total", "moneda")],
    filtros=["finca", "lote", "campana", "cultivo", "empleado", "fecha", "q"], buscar_en=["tipo_trabajo"],
    filtros_custom=[FILTRO_TIPO_EMPLEADO], buscar_primero=True, totales=["total", "jornales", "horas"],
    orden=lambda: Trabajo.fecha.desc(), guardar=op.guardar_trabajo, eliminar=op.eliminar_trabajo,
    origen_gasto="trabajo", descripcion=lambda t: f"{t.tipo_trabajo} · {t.empleado.nombre_completo} · $ {t.total}",
)

Modulo(
    "pagos_empleados", "Pagos a empleados", "Pago", PagoEmpleado, icono="pago",
    campos=[
        Campo("empleado_id", "Empleado", "select", requerido=True, opciones=ops.empleados, mostrar="empleado"),
        c_fecha(),
        Campo("concepto", "Concepto", requerido=True, maxlen=100, opciones=[(c, c) for c in CONCEPTOS_PAGO]),
        Campo("periodo", "Período", maxlen=20, placeholder="Ej: 2026-09 o 1ª quincena sep"),
        Campo("monto", "Monto ($)", "money", requerido=True),
        Campo("metodo_pago", "Método de pago", "choice", requerido=True,
              opciones=[m for m in METODOS_PAGO if m[0] != "cuenta_corriente"], defecto="efectivo"),
        c_finca(False), c_campana(), c_cultivo(),
        Campo("imputar_costo", "Imputar como costo de mano de obra", "bool", defecto=False,
              ayuda="Marcalo sólo si este pago NO corresponde a trabajos ya cargados (ej. sueldo fijo)."),
        c_obs(),
    ],
    columnas=[C("fecha", "Fecha", "fecha"), C("empleado", "Empleado"), C("concepto", "Concepto"),
              C("periodo", "Período", movil=False), C("finca.nombre", "Finca", movil=False),
              C("metodo_pago", "Método", "choice", movil=False), C("monto", "Monto", "moneda")],
    filtros=["empleado", "finca", "campana", "cultivo", "fecha"], filtros_custom=[FILTRO_TIPO_EMPLEADO],
    buscar_primero=True, totales=["monto"], orden=lambda: PagoEmpleado.fecha.desc(), usuario_attr="usuario_id",
    guardar=op.guardar_pago_empleado, eliminar=op.eliminar_pago_empleado, origen_gasto="pago_empleado",
    descripcion=lambda p: f"{p.concepto} a {p.empleado.nombre_completo} por $ {p.monto}",
)


# ================================================================ COSECHAS
Modulo(
    "cosechas", "Cosechas", "Cosecha", Cosecha, genero="a", icono="cosecha",
    campos=[
        Campo("siembra_id", "Siembra", "select", opciones=ops.siembras_en_curso, mostrar="siembra", autocompleta=True,
              ayuda="Elegí la siembra y se completan finca, lote, campaña, cultivo y hectáreas."),
    ] + imputacion(campana=True, cultivo=True) + [
        c_fecha(),
        Campo("superficie", "Superficie cosechada (ha)", "decimal"),
        Campo("cantidad", "Cantidad cosechada", "decimal", requerido=True,
              ayuda="En la unidad del cultivo (se ve entre paréntesis al lado del cultivo)."),
        Campo("merma", "Merma / descarte", "decimal", defecto="0"),
        Campo("semilla_guardada", "Guardado para semilla propia", "decimal", defecto="0", seccion="Semilla propia",
              ayuda="En la unidad del cultivo. Entra al stock de la semilla propia (sin costo) y no se cuenta para vender."),
        Campo("insumo_semilla_id", "Guardar como", "select", opciones=ops.semillas_propias, seccion="Semilla propia",
              mostrar="insumo_semilla.nombre",
              ayuda="Ej: «Semilla de papa propia». Si no existe, crealo en Insumos marcando «Semilla propia»."),
        Campo("calidad", "Calidad", "choice", opciones=CALIDADES),
        c_responsable(), c_obs(),
    ],
    columnas=[C("fecha", "Fecha", "fecha")] + COLS_IMPUTACION + [
        C("superficie", "Ha", "num", movil=False),
        C(lambda c: f"{numero(c.cantidad)} {c.unidad.abreviatura}", "Cosechado"),
        C("merma", "Merma", "num", movil=False),
        C(lambda c: numero(c.semilla_guardada) if c.semilla_guardada else "—", "P/ semilla", movil=False),
        C(lambda c: f"{numero(c.comercializable)} {c.unidad.abreviatura}", "Comercializable"),
        C(lambda c: f"{numero(c.rendimiento)} {c.unidad.abreviatura}/ha" if c.rendimiento else "—", "Rinde",
          movil=False)],
    filtros=["finca", "lote", "campana", "cultivo", "fecha"], buscar_primero=True,
    orden=lambda: Cosecha.fecha.desc(), guardar=op.guardar_cosecha, eliminar=op.eliminar_cosecha,
    preparar=op.preparar_cosecha,
    descripcion=lambda c: f"{c.cultivo.nombre} · {c.finca.nombre} · {c.cantidad} {c.unidad.abreviatura}",
    enlaces=[("Producción", "reportes.ver:produccion_cultivo")],
)


# ================================================================ INGRESOS / COBROS
def _ventas_con_saldo():
    stmt = consulta(Venta).order_by(Venta.fecha.desc())
    ids = fincas_permitidas()
    if ids is not None:
        stmt = stmt.where(Venta.finca_id.in_(ids or [-1]))
    salida = []
    for v in db.session.scalars(stmt.limit(500)).unique():
        if v.saldo > 0:
            salida.append((v.id, f"#{v.id} · {v.cliente.nombre} · {v.fecha:%d/%m/%Y} · saldo $ {v.saldo:,.0f}"
                           .replace(",", "."), None, {"monto": str(v.saldo)}))
    return salida


def _opciones_venta_ingreso():
    return _ventas_con_saldo()


Modulo(
    "ingresos", "Cobros e ingresos", "Ingreso", Ingreso, icono="ingreso",
    campos=[
        Campo("venta_id", "Venta que se cobra", "select", opciones=_opciones_venta_ingreso, mostrar="venta",
              autocompleta=True, ayuda="Dejalo vacío para otros ingresos (alquileres, servicios, subsidios…)."),
        c_fecha(),
        Campo("concepto", "Concepto", requerido=True, maxlen=120, defecto="Cobro de venta"),
        Campo("monto", "Monto ($)", "money", requerido=True),
        Campo("metodo_pago", "Medio de cobro", "choice", requerido=True,
              opciones=[m for m in METODOS_PAGO if m[0] != "cuenta_corriente"], defecto="transferencia"),
        Campo("estado", "Estado", "choice", requerido=True, opciones=ESTADOS_INGRESO, defecto="acreditado"),
        c_finca(False), c_campana(), c_cultivo(), c_obs(),
    ],
    columnas=[C("fecha", "Fecha", "fecha"), C("concepto", "Concepto"),
              C(lambda i: i.cliente.nombre if i.cliente else "—", "Cliente"), C("finca.nombre", "Finca", movil=False),
              C("metodo_pago", "Medio", "choice", movil=False), C("estado", "Estado", "estado"),
              C("monto", "Monto", "moneda")],
    filtros=["finca", "campana", "cultivo", "cliente", "fecha", "estado"], estados=ESTADOS_INGRESO,
    buscar_primero=True, totales=["monto"], orden=lambda: Ingreso.fecha.desc(), usuario_attr="usuario_id",
    guardar=op.guardar_ingreso, eliminar=op.eliminar_ingreso,
    descripcion=lambda i: f"{i.concepto} por $ {i.monto}",
)


# ================================================================ CLIENTES
def _detalle_cliente(c):
    ventas = db.session.scalars(select(Venta).where(Venta.cliente_id == c.id).order_by(Venta.fecha.desc())
                                .limit(30)).unique().all()
    total = db.session.scalar(select(func.coalesce(func.sum(Venta.total), 0)).where(Venta.cliente_id == c.id)) or 0
    todas = db.session.scalars(select(Venta).where(Venta.cliente_id == c.id)).unique().all()
    saldo = sum((v.saldo for v in todas), Decimal("0"))
    return [
        kpis("Resumen", [("Total comprado", moneda(total)), ("Cantidad de compras", str(len(todas))),
                         ("Saldo a cobrar", moneda(saldo))]),
        tabla("Historial de compras", ["Fecha", "Finca", "Productos", "Total", "Estado"],
              [[ffecha(v.fecha), v.finca.nombre,
                ", ".join(f"{d.cultivo.nombre} {numero(d.cantidad)} {d.unidad.abreviatura}" for d in v.detalles),
                moneda(v.total), v.estado_pago] for v in ventas]),
    ]


Modulo(
    "clientes", "Clientes / compradores", "Cliente", Cliente, icono="cliente", finca_attr=None,
    campos=[
        Campo("nombre", "Nombre / razón social", requerido=True, maxlen=120),
        Campo("cuit", "CUIT", "cuit"), Campo("dni", "DNI", maxlen=15),
        Campo("telefono", "Teléfono", "tel", maxlen=30), Campo("email", "Email", "email"),
        Campo("direccion", "Dirección", maxlen=150), Campo("localidad", "Localidad", maxlen=80),
        Campo("tipo", "Tipo de cliente", "choice", requerido=True, opciones=TIPOS_CLIENTE, defecto="mayorista"),
        Campo("estado", "Estado", "choice", requerido=True, opciones=ESTADOS_ACTIVO, defecto="activo"),
        c_obs(),
    ],
    columnas=[C("nombre", "Cliente"), C("cuit", "CUIT", movil=False), C("telefono", "Teléfono"),
              C("localidad", "Localidad", movil=False), C("tipo", "Tipo", "choice"), C("estado", "Estado", "estado")],
    filtros=["q", "tipo", "estado"], buscar_en=["nombre", "cuit", "dni", "localidad"], tipos=TIPOS_CLIENTE,
    estados=ESTADOS_ACTIVO, buscar_primero=True, orden=lambda: Cliente.nombre, detalle_extra=_detalle_cliente,
    entidad_documento="cliente", descripcion=lambda c: c.nombre,
    acciones_detalle=lambda c: [("Nueva venta", url_for("ventas.nuevo", cliente_id=c.id), "btn")],
)


# ================================================================ PROVEEDORES
def _detalle_proveedor(p):
    cuentas_ = db.session.scalars(select(CuentaPagar).where(CuentaPagar.proveedor_id == p.id)
                                  .order_by(CuentaPagar.vencimiento)).unique().all()
    deuda = sum((c.pendiente for c in cuentas_), Decimal("0"))
    gastado = db.session.scalar(select(func.coalesce(func.sum(Gasto.monto), 0)).where(Gasto.proveedor_id == p.id)) or 0
    from ..models import Compra
    compras = db.session.scalar(select(func.coalesce(func.sum(Compra.total), 0)).where(Compra.proveedor_id == p.id)) or 0
    return [
        kpis("Resumen", [("Deuda actual", moneda(deuda)), ("Compras de insumos", moneda(compras)),
                         ("Gastos registrados", moneda(gastado))]),
        tabla("Cuentas pendientes", ["Comprobante", "Vence", "Importe", "Pendiente", "Estado"],
              [[c.comprobante or "—", ffecha(c.vencimiento), moneda(c.importe), moneda(c.pendiente), c.estado]
               for c in cuentas_ if c.pendiente > 0]),
    ]


Modulo(
    "proveedores", "Proveedores", "Proveedor", Proveedor, icono="proveedor", finca_attr=None,
    campos=[
        Campo("razon_social", "Razón social", requerido=True, maxlen=120),
        Campo("cuit", "CUIT", "cuit"), Campo("telefono", "Teléfono", "tel", maxlen=30),
        Campo("email", "Email", "email"), Campo("direccion", "Dirección", maxlen=150),
        Campo("contacto", "Persona de contacto", maxlen=80),
        Campo("tipo", "Rubro", "choice", requerido=True, opciones=TIPOS_PROVEEDOR, defecto="otro"),
        Campo("estado", "Estado", "choice", requerido=True, opciones=ESTADOS_ACTIVO, defecto="activo"),
        c_obs(),
    ],
    columnas=[C("razon_social", "Proveedor"), C("cuit", "CUIT", movil=False), C("telefono", "Teléfono"),
              C("contacto", "Contacto", movil=False), C("tipo", "Rubro", "choice"), C("estado", "Estado", "estado")],
    filtros=["q", "tipo", "estado"], buscar_en=["razon_social", "cuit", "contacto"], tipos=TIPOS_PROVEEDOR,
    estados=ESTADOS_ACTIVO, buscar_primero=True, orden=lambda: Proveedor.razon_social,
    detalle_extra=_detalle_proveedor, entidad_documento="proveedor", descripcion=lambda p: p.razon_social,
)


# ================================================================ GASTOS
def _editable_gasto(g):
    if g.origen != "manual":
        return False, (f"Este gasto se generó automáticamente desde «{g.origen.replace('_', ' ')}». "
                       "Para cambiarlo, modificá ese registro.")
    return True, None


def _validar_gasto(datos, obj):
    if datos.get("metodo_pago") == "cuenta_corriente" and not datos.get("proveedor_id"):
        return {"proveedor_id": "Para cuenta corriente elegí el proveedor."}
    return {}


Modulo(
    "gastos", "Gastos", "Gasto", Gasto, icono="gasto",
    campos=[
        c_fecha(),
        Campo("categoria_id", "Categoría", "select", requerido=True, opciones=ops.categorias_gasto,
              mostrar="categoria.nombre"),
        Campo("descripcion", "Descripción", requerido=True, maxlen=200, ancho="completo"),
        Campo("monto", "Monto ($)", "money", requerido=True),
        Campo("metodo_pago", "Forma de pago", "choice", requerido=True, opciones=METODOS_PAGO, defecto="efectivo"),
        Campo("proveedor_id", "Proveedor", "select", opciones=ops.proveedores, mostrar="proveedor.razon_social"),
        Campo("vencimiento", "Vencimiento (si es a pagar)", "date"),
        Campo("comprobante", "Factura / comprobante", maxlen=40),
    ] + [c_finca(False), c_lote(), c_campana(), c_cultivo()] + [c_obs()],
    columnas=[C("fecha", "Fecha", "fecha"), C("categoria.nombre", "Categoría"), C("descripcion", "Descripción"),
              C("finca.nombre", "Finca", movil=False), C("cultivo.nombre", "Cultivo", movil=False),
              C("campana.nombre", "Campaña", movil=False),
              C(lambda g: "Manual" if g.origen == "manual" else "Automático", "Origen", movil=False),
              C("monto", "Monto", "moneda")],
    filtros=["finca", "lote", "campana", "cultivo", "categoria", "proveedor", "fecha", "q"],
    buscar_en=["descripcion", "comprobante"], buscar_primero=True, totales=["monto"],
    orden=lambda: (Gasto.fecha.desc(), Gasto.id.desc()), usuario_attr="usuario_id", validar=_validar_gasto,
    guardar=op.guardar_gasto, eliminar=op.eliminar_gasto, editable=_editable_gasto,
    descripcion=lambda g: f"{g.categoria.nombre}: {g.descripcion} por $ {g.monto}",
    ayuda="Los gastos de semillas, fertilizantes, agroquímicos, mano de obra, maquinaria, combustible y riego se "
          "generan solos al cargar esos registros. Aquí se cargan los demás (alquileres, impuestos, servicios…).",
)


# ================================================================ CUENTAS A PAGAR
def _filtro_estado_cuenta(stmt, valor, modelo):
    hoy = date.today()
    if valor == "pagado":
        return stmt.where(CuentaPagar.pagado >= CuentaPagar.importe)
    pendiente = CuentaPagar.pagado < CuentaPagar.importe
    if valor == "vencido":
        return stmt.where(pendiente, CuentaPagar.vencimiento < hoy)
    if valor == "parcial":
        return stmt.where(pendiente, CuentaPagar.pagado > 0, CuentaPagar.vencimiento >= hoy)
    if valor == "pendiente":
        return stmt.where(pendiente, CuentaPagar.pagado == 0, CuentaPagar.vencimiento >= hoy)
    if valor == "no_pagado":
        return stmt.where(pendiente)
    return stmt


Modulo(
    "cuentas_pagar", "Cuentas a pagar", "Cuenta a pagar", CuentaPagar, genero="a", icono="factura",
    campos=[
        Campo("proveedor_id", "Proveedor", "select", requerido=True, opciones=ops.proveedores,
              mostrar="proveedor.razon_social"),
        Campo("comprobante", "Factura / comprobante", maxlen=40),
        Campo("descripcion", "Descripción", maxlen=200, ancho="completo"),
        c_fecha(), Campo("vencimiento", "Vencimiento", "date", requerido=True),
        Campo("importe", "Importe ($)", "money", requerido=True),
        c_finca(False), c_obs(),
    ],
    columnas=[C("proveedor.razon_social", "Proveedor"), C("comprobante", "Comprobante", movil=False),
              C("vencimiento", "Vence", "fecha"), C("importe", "Importe", "moneda", movil=False),
              C("pagado", "Pagado", "moneda", movil=False), C("pendiente", "Pendiente", "moneda"),
              C("estado", "Estado", "estado")],
    filtros=["proveedor", "finca", "fecha"], campo_fecha="vencimiento", totales=["importe", "pagado"],
    filtros_custom=[{"nombre": "estado_cuenta", "etiqueta": "Estado",
                     "opciones": [("no_pagado", "Todas las impagas")] + ESTADOS_CUENTA,
                     "aplicar": _filtro_estado_cuenta}],
    orden=lambda: CuentaPagar.vencimiento, guardar=op.guardar_cuenta_pagar, eliminar=op.eliminar_cuenta_pagar,
    descripcion=lambda c: f"{c.proveedor.razon_social} {c.comprobante or ''} por $ {c.importe}",
    acciones_detalle=lambda c: ([("Registrar pago", url_for("cuentas.pagar", cuenta_id=c.id), "btn btn-primario")]
                                if c.pendiente > 0 else []),
    detalle_extra=lambda c: [tabla("Pagos realizados", ["Fecha", "Método", "Monto", "Observaciones"],
                                   [[ffecha(p.fecha), p.metodo_pago, moneda(p.monto), p.observaciones or ""]
                                    for p in c.pagos])],
)


# ================================================================ TAREAS Y RECORDATORIOS
Modulo(
    "alertas", "Tareas y recordatorios", "Tarea", Alerta, genero="a", icono="campana_alerta",
    campos=[
        Campo("titulo", "Título", requerido=True, maxlen=150, ancho="completo"),
        Campo("tipo", "Tipo", "choice", requerido=True, opciones=TIPOS_ALERTA, defecto="tarea"),
        Campo("prioridad", "Prioridad", "choice", requerido=True, opciones=PRIORIDADES, defecto="media"),
        c_fecha(), c_finca(False),
        Campo("asignado_id", "Asignada a", "select", opciones=ops.usuarios, mostrar="asignado.nombre"),
        Campo("estado", "Estado", "choice", requerido=True, opciones=ESTADOS_ALERTA, defecto="pendiente"),
        Campo("descripcion", "Detalle", "textarea", ancho="completo"),
    ],
    columnas=[C("fecha", "Fecha", "fecha"), C("titulo", "Tarea"), C("tipo", "Tipo", "choice", movil=False),
              C("finca.nombre", "Finca", movil=False), C("asignado.nombre", "Asignada a", movil=False),
              C("prioridad", "Prioridad", "estado"), C("estado", "Estado", "estado")],
    filtros=["finca", "fecha", "estado", "tipo"], estados=ESTADOS_ALERTA, tipos=TIPOS_ALERTA,
    orden=lambda: Alerta.fecha, usuario_attr="usuario_id", descripcion=lambda a: a.titulo,
)
