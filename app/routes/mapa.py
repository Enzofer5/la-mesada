"""Mapa satelital de las fincas: dibujo de lotes (pivotes circulares, rectángulos, polígonos), división en
sectores con distintas semillas/variedades, y acceso directo a siembras y cosechas de cada sector."""
from datetime import date
from decimal import Decimal

from flask import Blueprint, abort, jsonify, render_template, request, url_for
from sqlalchemy import func, select

from ..extensions import db
from ..models import CaminoLote, Campana, Cosecha, Cultivo, Finca, Gasto, Insumo, Lote, Siembra, dec
from ..services import auditoria, geo
from ..services import opciones as ops
from ..services import operaciones as op
from ..services.tenant import consulta, empresa_id, finca_permitida, fincas_permitidas
from ..utils.fechas import parse_fecha
from ..utils.permisos import CREAR, EDITAR, ELIMINAR, puede, requiere_permiso
from ..utils.validacion import ErrorNegocio, parse_decimal

bp = Blueprint("mapa", __name__, url_prefix="/mapa")


def _error(mensaje, codigo=400):
    return jsonify({"ok": False, "error": mensaje}), codigo


@bp.route("/")
@requiere_permiso("lotes")
def index():
    activa = ops.campana_activa_id()
    campana = request.args.get("campana", type=int) or activa
    config = {
        "fincas": [{"id": o[0], "nombre": o[1]} for o in ops.fincas()],
        "campanas": [{"id": o[0], "nombre": o[1]} for o in ops.campanas()],
        "cultivos": [{"id": c.id, "nombre": c.nombre, "unidad": c.unidad.abreviatura}
                     for c in db.session.scalars(consulta(Cultivo).where(Cultivo.estado == "activo")
                                                 .order_by(Cultivo.nombre)).unique()],
        "semillas": [{"id": i.id, "nombre": f"{i.nombre} · stock {i.stock:.2f} {i.unidad.abreviatura}".replace(".", ","),
                      "propia": bool(i.propia), "base": i.nombre}
                     for i in db.session.scalars(consulta(Insumo).where(Insumo.categoria == "semilla",
                                                                        Insumo.estado == "activo")
                                                 .order_by(Insumo.nombre)).unique()],
        "campana": campana,
        "finca": request.args.get("finca", type=int),
        "lote": request.args.get("lote", type=int),
        "puedeEditar": puede("lotes", EDITAR),
        "puedeSembrar": puede("siembras", CREAR),
        "puedeCosechar": puede("cosechas", CREAR),
        "puedeEditarSiembra": puede("siembras", EDITAR),
        "puedeEliminarSiembra": puede("siembras", ELIMINAR),
        "hoy": date.today().isoformat(),
        "urls": {
            "datos": url_for("mapa.datos"),
            "guardarLote": url_for("mapa.guardar_lote"),
            "caminos": url_for("mapa.index") + "caminos",
            "sectores": url_for("mapa.crear_sectores"),
            "siembras": url_for("mapa.index") + "siembras",
        },
    }
    return render_template("mapa/index.html", config=config)


@bp.route("/datos.json")
@requiere_permiso("lotes")
def datos():
    campana = request.args.get("campana", type=int)
    ids = fincas_permitidas()
    stmt = consulta(Lote).where(Lote.estado == "activo").order_by(Lote.finca_id, Lote.nombre)
    if ids is not None:
        stmt = stmt.where(Lote.finca_id.in_(ids or [-1]))
    lotes = db.session.scalars(stmt).unique().all()
    lote_ids = [l.id for l in lotes] or [-1]

    stmt = select(Siembra).where(Siembra.empresa_id == empresa_id(), Siembra.lote_id.in_(lote_ids))
    if campana:
        stmt = stmt.where(Siembra.campana_id == campana)
    siembras = db.session.scalars(stmt.order_by(Siembra.fecha_siembra)).unique().all()

    def suma(modelo, columna, fecha_ok=True):
        q = (select(modelo.lote_id, func.sum(columna)).where(modelo.empresa_id == empresa_id(),
                                                             modelo.lote_id.in_(lote_ids)).group_by(modelo.lote_id))
        if campana:
            q = q.where(modelo.campana_id == campana)
        return {lid: dec(v) for lid, v in db.session.execute(q)}

    caminos_por_lote = {}
    for c in db.session.scalars(select(CaminoLote).where(CaminoLote.empresa_id == empresa_id(),
                                                         CaminoLote.lote_id.in_(lote_ids))).unique():
        caminos_por_lote.setdefault(c.lote_id, []).append({
            "id": c.id, "nombre": c.nombre, "ancho": float(c.ancho), "longitud": float(c.longitud),
            "superficie": float(c.superficie), "geometria": geo.leer(c.geometria)})
    gastos = suma(Gasto, Gasto.monto)
    cosechado = suma(Cosecha, Cosecha.cantidad - Cosecha.merma)

    salida_lotes = []
    for l in lotes:
        salida_lotes.append({
            "id": l.id, "finca_id": l.finca_id, "finca": l.finca.nombre, "nombre": l.nombre,
            "superficie": float(l.superficie), "forma": l.forma, "geometria": geo.leer(l.geometria),
            "tipo_suelo": l.tipo_suelo, "gastos": float(gastos.get(l.id, 0)),
            "caminos": caminos_por_lote.get(l.id, []),
            "superficie_util": float(l.superficie) - sum(c["superficie"] for c in caminos_por_lote.get(l.id, [])),
            "cosechado": float(cosechado.get(l.id, 0)),
            "url": url_for("crud.detalle", key="lotes", id=l.id),
        })
    salida_siembras = []
    for s in siembras:
        salida_siembras.append({
            "id": s.id, "lote_id": s.lote_id, "cultivo_id": s.cultivo_id, "cultivo": s.cultivo.nombre,
            "unidad": s.cultivo.unidad.abreviatura, "variedad": s.variedad or "Sin variedad",
            "semilla": s.insumo.nombre if s.insumo else None, "superficie": float(s.superficie),
            "origen_semilla": s.origen_semilla,
            "estado": s.estado, "fecha_siembra": s.fecha_siembra.isoformat(),
            "fecha_cosecha_estimada": s.fecha_cosecha_estimada.isoformat() if s.fecha_cosecha_estimada else None,
            "rendimiento_estimado": float(s.rendimiento_estimado) if s.rendimiento_estimado else None,
            "campana": s.campana.nombre, "geometria": geo.leer(s.geometria),
            "distancia_surcos": float(s.distancia_surcos) if s.distancia_surcos else None,
            "orientacion_surcos": float(s.orientacion_surcos) if s.orientacion_surcos is not None else None,
            "superficie_caminos": float(s.superficie_caminos) if s.superficie_caminos else 0,
            "cantidad_semilla": float(s.cantidad_semilla) if s.cantidad_semilla else None,
            "insumo_id": s.insumo_id, "costo_semilla": float(s.costo_semilla or 0),
            "observaciones": s.observaciones,
            "url": url_for("crud.detalle", key="siembras", id=s.id),
            "url_editar": url_for("crud.editar", key="siembras", id=s.id),
            "url_cosecha": url_for("crud.nuevo", key="cosechas", siembra_id=s.id),
            "url_aplicacion": url_for("crud.nuevo", key="aplicaciones_agroquimicos", finca_id=s.finca_id,
                                      lote_id=s.lote_id, cultivo_id=s.cultivo_id, campana_id=s.campana_id),
            "url_trabajo": url_for("crud.nuevo", key="trabajos", finca_id=s.finca_id, lote_id=s.lote_id,
                                   cultivo_id=s.cultivo_id, campana_id=s.campana_id),
        })
    return jsonify({"lotes": salida_lotes, "siembras": salida_siembras})


def _lote_editable(lote_id):
    lote = db.session.get(Lote, lote_id)
    if lote is None or lote.empresa_id != empresa_id():
        abort(404)
    if not finca_permitida(lote.finca_id, permitir_general=False):
        abort(403)
    return lote


@bp.route("/lotes", methods=["POST"])
@requiere_permiso("lotes", EDITAR)
def guardar_lote():
    datos = request.get_json(silent=True) or {}
    try:
        feature = geo.validar(datos.get("geometria"), {"circulo", "rectangulo", "poligono"})
        hectareas = geo.hectareas(feature)
        avisos = []
        if datos.get("lote_id"):
            lote = _lote_editable(int(datos["lote_id"]))
            nuevo = False
        else:
            if not puede("lotes", CREAR):
                abort(403)
            finca_id = int(datos.get("finca_id") or 0)
            finca = db.session.get(Finca, finca_id)
            if finca is None or finca.empresa_id != empresa_id() or not finca_permitida(finca_id, False):
                raise ErrorNegocio("Elegí la finca del lote.")
            nombre = (datos.get("nombre") or "").strip()[:60]
            if not nombre:
                raise ErrorNegocio("Escribí el nombre del lote (ej. Pivote 1).")
            if db.session.scalar(select(Lote).where(Lote.finca_id == finca_id, Lote.nombre == nombre)):
                raise ErrorNegocio(f"Ya existe un lote llamado «{nombre}» en {finca.nombre}.")
            lote = Lote(empresa_id=empresa_id(), finca_id=finca_id, nombre=nombre, estado="activo",
                        tipo_suelo=finca.tipo_suelo)
            db.session.add(lote)
            nuevo = True
        lote.forma = feature["properties"]["forma"]
        lote.geometria = geo.a_texto(feature)
        lote.superficie = hectareas
        db.session.flush()
        ocupado = db.session.scalar(select(func.coalesce(func.sum(Lote.superficie), 0)).where(
            Lote.finca_id == lote.finca_id, Lote.estado == "activo")) or 0
        if dec(ocupado) > dec(lote.finca.superficie_total):
            avisos.append(f"Los lotes de {lote.finca.nombre} suman {dec(ocupado):.2f} ha y la finca figura con "
                          f"{lote.finca.superficie_total} ha. Revisá la superficie total de la finca.")
        auditoria.registrar("lotes", "crear" if nuevo else "editar", auditoria.frase(
            "crear" if nuevo else "editar", f"en el mapa el lote {lote.nombre} ({lote.finca.nombre}, {hectareas} ha)"),
            lote.id)
        db.session.commit()
        return jsonify({"ok": True, "lote_id": lote.id, "superficie": float(hectareas), "avisos": avisos})
    except ErrorNegocio as e:
        db.session.rollback()
        return _error(str(e))


@bp.route("/lotes/<int:lote_id>/quitar", methods=["POST"])
@requiere_permiso("lotes", EDITAR)
def quitar_forma(lote_id):
    lote = _lote_editable(lote_id)
    lote.geometria = None
    lote.forma = None
    auditoria.registrar("lotes", "editar", auditoria.frase("editar", f"el mapa: quitó la forma del lote {lote.nombre}"),
                        lote.id)
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/caminos", methods=["POST"])
@requiere_permiso("lotes", EDITAR)
def crear_camino():
    """Camino interno del lote: una línea con su ancho en metros (se descuenta de la superficie sembrable)."""
    datos = request.get_json(silent=True) or {}
    try:
        lote = _lote_editable(int(datos.get("lote_id") or 0))
        feature = geo.validar_linea(datos.get("geometria"))
        try:
            ancho = parse_decimal(str(datos.get("ancho") or ""))
        except ValueError:
            ancho = None
        if not ancho or not (Decimal("0.5") <= ancho <= Decimal("50")):
            raise ErrorNegocio("Indicá el ancho del camino en metros (entre 0,5 y 50).")
        nombre = (str(datos.get("nombre") or "").strip() or "Camino")[:60]
        camino = CaminoLote(empresa_id=empresa_id(), lote_id=lote.id, nombre=nombre, ancho=ancho,
                            longitud=Decimal(str(round(geo.longitud_m(feature), 1))), geometria=geo.a_texto(feature))
        db.session.add(camino)
        db.session.flush()
        auditoria.registrar("lotes", "crear", auditoria.frase(
            "crear", f"el camino «{nombre}» en {lote.nombre} ({camino.longitud} m × {ancho} m)"), lote.id)
        db.session.commit()
        return jsonify({"ok": True, "id": camino.id, "longitud": float(camino.longitud),
                        "superficie": float(camino.superficie)})
    except ErrorNegocio as e:
        db.session.rollback()
        return _error(str(e))


@bp.route("/caminos/<int:camino_id>/eliminar", methods=["POST"])
@requiere_permiso("lotes", EDITAR)
def eliminar_camino(camino_id):
    camino = db.session.get(CaminoLote, camino_id)
    if camino is None or camino.empresa_id != empresa_id():
        abort(404)
    _lote_editable(camino.lote_id)
    auditoria.registrar("lotes", "eliminar", auditoria.frase("eliminar", f"el camino «{camino.nombre}»"),
                        camino.lote_id)
    db.session.delete(camino)
    db.session.commit()
    return jsonify({"ok": True})


def _semilla(datos, semillas_validas, prefijo=""):
    """Lee origen (propia/comprada), semilla del inventario, cantidad y precio de un sector."""
    origen = datos.get("origen_semilla") if datos.get("origen_semilla") in ("propia", "comprada") else None
    insumo_id = datos.get("insumo_id")
    insumo_id = int(insumo_id) if insumo_id not in (None, "", 0, "0") else None
    if insumo_id and insumo_id not in semillas_validas:
        raise ErrorNegocio(f"{prefijo}semilla no válida.")
    if origen == "propia" and str(datos.get("costo_semilla") or "").strip() not in ("", "0"):
        raise ErrorNegocio(f"{prefijo}la semilla propia no lleva precio.")
    try:
        cantidad = parse_decimal(str(datos.get("cantidad_semilla") or ""))
        costo = parse_decimal(str(datos.get("costo_semilla") or "")) or Decimal("0")
    except ValueError:
        raise ErrorNegocio(f"{prefijo}revisá los números.")
    if insumo_id and not cantidad:
        raise ErrorNegocio(f"{prefijo}indicá cuánta semilla sale del inventario.")
    return insumo_id, cantidad, (Decimal("0") if origen == "propia" else costo), origen


def _siembra_editable(siembra_id):
    s = db.session.get(Siembra, siembra_id)
    if s is None or s.empresa_id != empresa_id():
        abort(404)
    if not finca_permitida(s.finca_id, permitir_general=False):
        abort(403)
    return s


def _descripcion(s):
    return f"{s.cultivo.nombre} {s.variedad or ''} en {s.lote.nombre if s.lote else s.finca.nombre}".replace("  ", " ")


@bp.route("/siembras/<int:siembra_id>/sembrar", methods=["POST"])
@requiere_permiso("siembras", EDITAR)
def sembrar(siembra_id):
    """Un sector marcado como pendiente se siembra (otro día): se registra la fecha real y la semilla usada."""
    s = _siembra_editable(siembra_id)
    datos = request.get_json(silent=True) or {}
    try:
        if s.estado != "planificada":
            raise ErrorNegocio("Este sector ya figura como sembrado.")
        fecha = parse_fecha(datos.get("fecha_siembra"))
        if not fecha:
            raise ErrorNegocio("Indicá la fecha en que se sembró.")
        if fecha > date.today():
            raise ErrorNegocio("La fecha de siembra no puede ser futura. Si todavía no se sembró, dejalo pendiente.")
        if s.fecha_cosecha_estimada and s.fecha_cosecha_estimada < fecha:
            raise ErrorNegocio("La cosecha estimada quedó antes de la siembra: corregila en «Editar datos».")
        insumo_id, cantidad, costo, origen = _semilla(datos, {o[0] for o in ops.insumos("semilla")})
        variedad = str(datos.get("variedad") or "").strip()[:60]
        if variedad:
            s.variedad = variedad
        s.fecha_siembra = fecha
        s.insumo_id, s.cantidad_semilla = insumo_id, cantidad
        s.costo_semilla = 0 if insumo_id else costo
        s.origen_semilla = origen
        s.estado = "en_curso"
        db.session.flush()
        op.guardar_siembra(s, False, None)
        auditoria.registrar("siembras", "editar", auditoria.frase(
            "editar", f"la siembra {_descripcion(s)}: marcada como sembrada el {fecha:%d/%m/%Y}"), s.id)
        db.session.commit()
        return jsonify({"ok": True, "costo": float(s.costo_semilla or 0)})
    except ErrorNegocio as e:
        db.session.rollback()
        return _error(str(e))


@bp.route("/siembras/<int:siembra_id>/pendiente", methods=["POST"])
@requiere_permiso("siembras", EDITAR)
def volver_a_pendiente(siembra_id):
    """Deshacer: el sector vuelve a «pendiente de siembra» (devuelve la semilla al stock y quita el costo)."""
    s = _siembra_editable(siembra_id)
    datos = request.get_json(silent=True) or {}
    try:
        if s.estado != "en_curso":
            raise ErrorNegocio("Sólo un sector sembrado (en curso) puede volver a pendiente.")
        if db.session.scalar(select(func.count(Cosecha.id)).where(Cosecha.siembra_id == s.id)):
            raise ErrorNegocio("El sector tiene cosechas registradas.")
        fecha = parse_fecha(datos.get("fecha_siembra"))
        if fecha:
            s.fecha_siembra = fecha
        s.estado = "planificada"
        s.costo_semilla = 0
        op.guardar_siembra(s, False, None)
        auditoria.registrar("siembras", "editar", auditoria.frase(
            "editar", f"la siembra {_descripcion(s)}: vuelve a pendiente de siembra"), s.id)
        db.session.commit()
        return jsonify({"ok": True})
    except ErrorNegocio as e:
        db.session.rollback()
        return _error(str(e))


@bp.route("/siembras/<int:siembra_id>/forma", methods=["POST"])
@requiere_permiso("siembras", EDITAR)
def cambiar_forma(siembra_id):
    """Ajustar el dibujo de un sector ya cargado: se recalculan las hectáreas (menos caminos)."""
    s = _siembra_editable(siembra_id)
    datos = request.get_json(silent=True) or {}
    try:
        if not s.lote_id:
            raise ErrorNegocio("La siembra no está asociada a un lote.")
        feature = geo.validar(datos.get("geometria"), {"sector", "circulo", "rectangulo", "poligono"})
        anterior = geo.leer(s.geometria)
        if anterior:  # conserva ancho/ángulo de la franja original como referencia
            for k in ("angulo",):
                if k in anterior.get("properties", {}) and k not in feature["properties"]:
                    feature["properties"][k] = anterior["properties"][k]
        feature["properties"].pop("ancho", None)
        bruta = geo.hectareas(feature)
        if bruta > dec(s.lote.superficie) * Decimal("1.03") + Decimal("0.05"):
            raise ErrorNegocio(f"El sector ({bruta} ha) es más grande que el lote ({s.lote.superficie} ha).")
        caminos = [(geo.leer(c.geometria), c.ancho) for c in db.session.scalars(
            select(CaminoLote).where(CaminoLote.lote_id == s.lote_id)).unique()]
        en_caminos = (Decimal(str(geo.superficie_caminos_m2(feature, caminos))) / 10000).quantize(Decimal("0.01"))
        previa = s.superficie
        s.geometria = geo.a_texto(feature)
        s.superficie = max(bruta - en_caminos, Decimal("0.01"))
        s.superficie_caminos = en_caminos
        op.guardar_siembra(s, False, None)
        otras = db.session.scalar(select(func.coalesce(func.sum(Siembra.superficie), 0)).where(
            Siembra.lote_id == s.lote_id, Siembra.campana_id == s.campana_id,
            Siembra.estado.in_(["en_curso", "planificada"]))) or 0
        avisos = []
        if dec(otras) > dec(s.lote.superficie) * Decimal("1.03"):
            avisos.append(f"Las siembras de {s.lote.nombre} en esta campaña suman {dec(otras):.2f} ha y el lote tiene "
                          f"{s.lote.superficie} ha: revisá si los sectores se superponen.")
        auditoria.registrar("siembras", "editar", auditoria.frase(
            "editar", f"en el mapa la forma de la siembra {_descripcion(s)} ({previa} → {s.superficie} ha)"), s.id)
        db.session.commit()
        return jsonify({"ok": True, "superficie": float(s.superficie), "caminos": float(en_caminos), "avisos": avisos})
    except ErrorNegocio as e:
        db.session.rollback()
        return _error(str(e))


@bp.route("/siembras/<int:siembra_id>/eliminar", methods=["POST"])
@requiere_permiso("siembras", ELIMINAR)
def eliminar_siembra(siembra_id):
    s = _siembra_editable(siembra_id)
    try:
        descripcion = _descripcion(s)
        op.eliminar_siembra(s)
        db.session.delete(s)
        db.session.flush()
        auditoria.registrar("siembras", "eliminar", auditoria.frase("eliminar", f"el sector {descripcion}"), siembra_id)
        db.session.commit()
        return jsonify({"ok": True})
    except ErrorNegocio as e:
        db.session.rollback()
        return _error(str(e))


@bp.route("/sectores", methods=["POST"])
@requiere_permiso("siembras", CREAR)
def crear_sectores():
    """Crea una siembra por cada sector (ej. un pivote dividido en 3 gajos con distintas variedades)."""
    datos = request.get_json(silent=True) or {}
    try:
        lote = _lote_editable(int(datos.get("lote_id") or 0))
        campana = db.session.get(Campana, int(datos.get("campana_id") or 0))
        cultivo = db.session.get(Cultivo, int(datos.get("cultivo_id") or 0))
        if not campana or campana.empresa_id != empresa_id():
            raise ErrorNegocio("Elegí la campaña.")
        if not cultivo or cultivo.empresa_id != empresa_id():
            raise ErrorNegocio("Elegí el cultivo.")
        fecha_general = parse_fecha(datos.get("fecha_siembra"))
        if not fecha_general:
            raise ErrorNegocio("Indicá la fecha de siembra.")
        cosecha_est = parse_fecha(datos.get("fecha_cosecha_estimada"))
        try:
            rinde = parse_decimal(str(datos.get("rendimiento_estimado") or ""))
        except ValueError:
            raise ErrorNegocio("Rendimiento esperado inválido.")
        sectores = datos.get("sectores") or []
        if not isinstance(sectores, list) or not 1 <= len(sectores) <= 24:
            raise ErrorNegocio("Indicá entre 1 y 24 sectores.")
        semillas_validas = {o[0] for o in ops.insumos("semilla")}
        try:
            surcos = parse_decimal(str(datos.get("distancia_surcos") or ""))
        except ValueError:
            raise ErrorNegocio("Distancia entre surcos inválida.")
        if surcos is not None and not (Decimal("0.05") <= surcos <= Decimal("5")):
            raise ErrorNegocio("La distancia entre surcos debe estar entre 0,05 y 5 metros.")
        orientacion_general = datos.get("orientacion")
        if not isinstance(orientacion_general, (int, float)) or not 0 <= orientacion_general < 360:
            orientacion_general = None
        caminos = [(geo.leer(c.geometria), c.ancho) for c in db.session.scalars(
            select(CaminoLote).where(CaminoLote.lote_id == lote.id)).unique()]
        creadas, total_ha, total_neta = [], Decimal("0"), Decimal("0")
        for n, sec in enumerate(sectores, start=1):
            feature = geo.validar(sec.get("geometria"), {"sector", "circulo", "rectangulo", "poligono"})
            bruta = geo.hectareas(feature)
            en_caminos = (Decimal(str(geo.superficie_caminos_m2(feature, caminos))) / 10000).quantize(Decimal("0.01"))
            ha = max(bruta - en_caminos, Decimal("0.01"))
            total_ha += bruta
            total_neta += ha
            orientacion = feature["properties"].get("angulo", orientacion_general)
            estado = "planificada" if sec.get("estado") == "planificada" else "en_curso"
            fecha = parse_fecha(sec.get("fecha_siembra")) if sec.get("fecha_siembra") else fecha_general
            if not fecha:
                raise ErrorNegocio(f"Sector {n}: fecha de siembra inválida.")
            if cosecha_est and cosecha_est < fecha:
                raise ErrorNegocio(f"Sector {n}: la cosecha estimada debe ser posterior a la siembra.")
            insumo_id, cantidad, costo, origen = _semilla(sec, semillas_validas, f"Sector {n}: ")
            siembra = Siembra(
                empresa_id=empresa_id(), finca_id=lote.finca_id, lote_id=lote.id, campana_id=campana.id,
                cultivo_id=cultivo.id, fecha_siembra=fecha, superficie=ha,
                variedad=(str(sec.get("variedad") or "").strip()[:60] or None), insumo_id=insumo_id,
                cantidad_semilla=cantidad, costo_semilla=costo if not insumo_id else 0, origen_semilla=origen,
                fecha_cosecha_estimada=cosecha_est, rendimiento_estimado=rinde, estado=estado,
                responsable_id=auditoria.usuario_actual().id, geometria=geo.a_texto(feature),
                distancia_surcos=surcos, orientacion_surcos=orientacion, superficie_caminos=en_caminos,
                observaciones=(f"Sector {n} de {len(sectores)} (cargado desde el mapa). Bruto {bruta} ha"
                               + (f", caminos {en_caminos} ha" if en_caminos else "")
                               + (f", ancho {feature['properties']['ancho']:.0f} m" if feature['properties'].get('ancho') else "")))
            db.session.add(siembra)
            db.session.flush()
            op.guardar_siembra(siembra, True, None)
            creadas.append(siembra.id)
        if total_ha > dec(lote.superficie) * Decimal("1.03") + Decimal("0.05"):
            raise ErrorNegocio(f"Los sectores suman {total_ha} ha y el lote tiene {lote.superficie} ha.")
        pendientes = sum(1 for sec in sectores if sec.get("estado") == "planificada")
        auditoria.registrar("siembras", "crear", auditoria.frase(
            "crear", f"{len(creadas)} siembra(s) por sectores en {lote.nombre} ({lote.finca.nombre}): {cultivo.nombre}, "
                     f"{total_ha} ha"), lote.id)
        db.session.commit()
        return jsonify({"ok": True, "siembras": creadas, "superficie": float(total_ha), "neta": float(total_neta),
                        "pendientes": pendientes})
    except ErrorNegocio as e:
        db.session.rollback()
        return _error(str(e))
