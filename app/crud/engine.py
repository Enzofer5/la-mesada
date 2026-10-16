"""Controlador genérico ABM: listado con filtros, paginación, totales y exportación; alta; edición; detalle;
eliminación. Aplica en todos los módulos: empresa, fincas permitidas, permisos, validación, CSRF y auditoría."""
import json
from datetime import date
from decimal import Decimal

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Documento, Gasto, Lote
from ..services import auditoria, exportar
from ..services import opciones as ops
from ..services.tenant import consulta, empresa_id, fincas_permitidas, filtrar_fincas, obtener_o_404
from ..utils.fechas import parse_fecha
from ..utils.formato import fecha as ffecha, moneda, numero
from ..utils.permisos import CREAR, EDITAR, ELIMINAR, VER, puede
from ..utils.validacion import ErrorNegocio
from . import modulos as _declaraciones  # noqa: F401  (registra los módulos)
from .modulo import REGISTRO

bp = Blueprint("crud", __name__, url_prefix="/m")

# Filtros estándar: clave → (atributo del modelo, etiqueta, función de opciones)
FILTROS_SELECT = {
    "finca": ("finca_id", "Finca", lambda: ops.fincas(solo_activas=False)),
    "lote": ("lote_id", "Lote", ops.lotes),
    "campana": ("campana_id", "Campaña", ops.campanas),
    "cultivo": ("cultivo_id", "Cultivo", lambda: ops.cultivos(False)),
    "categoria": ("categoria_id", "Categoría", ops.categorias_gasto),
    "proveedor": ("proveedor_id", "Proveedor", ops.proveedores),
    "cliente": ("cliente_id", "Cliente", ops.clientes),
    "empleado": ("empleado_id", "Empleado", lambda: ops.empleados(False)),
    "maquina": ("maquina_id", "Máquina", ops.maquinas),
    "insumo": ("insumo_id", "Insumo", ops.insumos),
    "responsable": ("responsable_id", "Responsable", ops.usuarios),
}

# Al usar "Guardar y cargar otro" se conservan estos datos (carga rápida de varios registros iguales)
PRESERVAR = {"finca_id", "lote_id", "campana_id", "cultivo_id", "fecha", "tipo_trabajo", "modalidad",
             "precio_unitario", "jornales", "horas", "maquina_id", "categoria_id", "metodo_pago", "insumo_id",
             "tipo", "concepto", "periodo", "sistema"}


def obtener_modulo(key):
    modulo = REGISTRO.get(key)
    if modulo is None:
        abort(404)
    return modulo


def verificar(modulo, accion):
    if not puede(modulo.permiso, accion):
        abort(403)


def resolver_enlace(spec):
    """'endpoint', 'crud.listar:clave?query' o 'reportes.ver:tipo' → url."""
    if ":" not in spec:
        return url_for(spec)
    endpoint, resto = spec.split(":", 1)
    arg, _, query = resto.partition("?")
    if endpoint == "crud.listar":
        url = url_for(endpoint, key=arg)
    elif endpoint == "reportes.ver":
        url = url_for(endpoint, tipo=arg)
    else:
        url = url_for(endpoint)
    return url + ("?" + query if query else "")


# ------------------------------------------------------------------ helpers de valores
def ruta(obj, camino):
    actual = obj
    for parte in camino.split("."):
        if actual is None:
            return None
        actual = getattr(actual, parte, None)
    return actual


def etiqueta_estado(modulo, valor):
    for lista in (modulo.estados or [],):
        for v, etiqueta in lista:
            if v == valor:
                return etiqueta
    campo = modulo.campo("estado")
    if campo and campo.tipo == "choice":
        return campo.etiqueta_de(valor)
    return str(valor).replace("_", " ").capitalize() if valor is not None else "—"


def celda(modulo, columna, obj):
    valor = columna.obtener(obj)
    f = columna.formato
    if f == "num":
        return {"texto": numero(valor), "clase": "num"}
    if f == "moneda":
        return {"texto": moneda(valor), "clase": "num"}
    if f == "fecha":
        return {"texto": ffecha(valor), "clase": "fecha"}
    if f == "bool":
        return {"texto": "Sí" if valor else "No"}
    if f == "estado":
        return {"texto": etiqueta_estado(modulo, valor), "badge": str(valor)}
    if f == "choice" and isinstance(columna.valor, str):
        campo = modulo.campo(columna.valor)
        if campo:
            return {"texto": campo.etiqueta_de(valor)}
        if modulo.tipos and columna.valor == modulo.tipo_attr:
            return {"texto": dict(modulo.tipos).get(valor, valor)}
    return {"texto": "—" if valor is None or valor == "" else str(valor)}


def valor_exportable(columna, obj):
    valor = columna.obtener(obj)
    if columna.formato in ("num", "moneda"):
        return float(valor) if valor is not None else None
    if columna.formato == "fecha":
        return valor
    if columna.formato == "bool":
        return "Sí" if valor else "No"
    if isinstance(valor, (int, float, Decimal, date)) or valor is None:
        return valor
    return str(valor)


def mostrar_campo(campo, obj):
    if campo.mostrar:
        valor = ruta(obj, campo.mostrar)
        return str(valor) if valor is not None else "—"
    valor = getattr(obj, campo.nombre, None)
    if valor is None or valor == "":
        return "—"
    if campo.tipo == "bool":
        return "Sí" if valor else "No"
    if campo.tipo == "choice":
        return campo.etiqueta_de(valor)
    if campo.tipo == "money":
        return moneda(valor, 2)
    if campo.tipo in ("decimal", "int"):
        return numero(valor, "auto")
    if campo.tipo == "date":
        return ffecha(valor)
    return str(valor)


# ------------------------------------------------------------------ filtros
def query_base(modulo):
    stmt = consulta(modulo.modelo)
    if modulo.finca_attr:
        stmt = filtrar_fincas(stmt, getattr(modulo.modelo, modulo.finca_attr))
    for clave in modulo.filtro_fijo:
        valor = request.args.get(clave)
        if valor:
            stmt = stmt.where(getattr(modulo.modelo, clave) == valor)
    return stmt


def construir_filtros(modulo, args):
    """Devuelve (lista para la plantilla, función que aplica los filtros al SELECT, hay_filtro_activo)."""
    modelo = modulo.modelo
    ui, aplicadores, activo = [], [], False
    for clave in modulo.filtros:
        if clave in FILTROS_SELECT:
            attr, etiqueta, fn_ops = FILTROS_SELECT[clave]
            if not hasattr(modelo, attr):
                continue
            valor = args.get(clave, "")
            ui.append({"nombre": clave, "etiqueta": etiqueta, "tipo": "select", "valor": valor,
                       "opciones": [(o[0], o[1]) for o in fn_ops()],
                       "depende": "finca" if clave == "lote" else None,
                       "padres": {str(o[0]): o[2] for o in fn_ops()} if clave == "lote" else None})
            if valor.isdigit():
                activo = True
                aplicadores.append(lambda s, a=attr, v=int(valor): s.where(getattr(modelo, a) == v))
        elif clave == "fecha":
            desde, hasta = parse_fecha(args.get("desde")), parse_fecha(args.get("hasta"))
            ui.append({"nombre": "fecha", "etiqueta": "Fecha", "tipo": "rango",
                       "desde": args.get("desde", ""), "hasta": args.get("hasta", "")})
            col = getattr(modelo, modulo.campo_fecha)
            if desde:
                activo = True
                aplicadores.append(lambda s, c=col, d=desde: s.where(c >= d))
            if hasta:
                activo = True
                aplicadores.append(lambda s, c=col, h=hasta: s.where(c <= h))
        elif clave == "q":
            valor = args.get("q", "").strip()[:80]
            ui.append({"nombre": "q", "etiqueta": "Buscar", "tipo": "texto", "valor": valor})
            if valor and modulo.buscar_en:
                activo = True
                patron = f"%{valor}%"
                aplicadores.append(lambda s, p=patron: s.where(or_(*[getattr(modelo, c).ilike(p)
                                                                      for c in modulo.buscar_en])))
        elif clave == "estado" and modulo.estados:
            valor = args.get("estado", "")
            ui.append({"nombre": "estado", "etiqueta": "Estado", "tipo": "select", "valor": valor,
                       "opciones": modulo.estados})
            if valor:
                activo = True
                aplicadores.append(lambda s, v=valor: s.where(modelo.estado == v))
        elif clave == "tipo" and modulo.tipos:
            valor = args.get("tipo", "")
            ui.append({"nombre": "tipo", "etiqueta": "Tipo", "tipo": "select", "valor": valor,
                       "opciones": modulo.tipos})
            if valor:
                activo = True
                aplicadores.append(lambda s, v=valor: s.where(getattr(modelo, modulo.tipo_attr) == v))
    for fc in modulo.filtros_custom:
        valor = args.get(fc["nombre"], "")
        ui.append({"nombre": fc["nombre"], "etiqueta": fc["etiqueta"], "tipo": "select", "valor": valor,
                   "opciones": fc["opciones"]})
        if valor:
            activo = True
            aplicadores.append(lambda s, f=fc, v=valor: f["aplicar"](s, v, modelo))

    def aplicar(stmt):
        for a in aplicadores:
            stmt = a(stmt)
        return stmt

    return ui, aplicar, activo


def ordenar(modulo, stmt):
    if modulo.orden:
        orden = modulo.orden()
        if not isinstance(orden, tuple):
            orden = (orden,)
        return stmt.order_by(*orden)
    return stmt.order_by(modulo.modelo.id.desc())


# ------------------------------------------------------------------ LISTADO
@bp.route("/<key>/")
def listar(key):
    modulo = obtener_modulo(key)
    verificar(modulo, VER)
    args = request.args
    filtros_ui, aplicar, filtro_activo = construir_filtros(modulo, args)
    buscar = (not modulo.buscar_primero) or filtro_activo or args.get("buscar") or args.get("exportar")
    stmt = ordenar(modulo, aplicar(query_base(modulo)))

    formato = args.get("exportar")
    if formato in ("csv", "xlsx", "pdf"):
        filas = db.session.scalars(stmt.limit(20000)).unique().all()
        encabezados = [c.etiqueta for c in modulo.columnas]
        if formato == "pdf":
            datos = [[celda(modulo, c, o)["texto"] for c in modulo.columnas] for o in filas]
        else:
            datos = [[valor_exportable(c, o) for c in modulo.columnas] for o in filas]
        auditoria.registrar(key, "exportar", f"Exportó {modulo.titulo} ({formato})")
        db.session.commit()
        return exportar.respuesta(formato, modulo.titulo, encabezados, datos,
                                  subtitulo=describir_filtros(filtros_ui))

    paginacion, filas, totales = None, [], []
    if buscar:
        pagina = args.get("pagina", 1, type=int)
        paginacion = db.paginate(stmt, page=max(pagina, 1), per_page=current_app.config["POR_PAGINA"],
                                 error_out=False)
        filas = [(obj, [celda(modulo, c, obj) for c in modulo.columnas]) for obj in paginacion.items]
        for attr in modulo.totales:
            col = getattr(modulo.modelo, attr)
            total = db.session.scalar(aplicar(query_base(modulo)).with_only_columns(func.sum(col)).order_by(None))
            campo = modulo.campo(attr)
            es_dinero = (campo and campo.tipo == "money") or attr in ("total", "costo_total", "monto", "importe",
                                                                       "pagado", "costo_semilla")
            etiqueta = campo.etiqueta if campo else next((c.etiqueta for c in modulo.columnas if c.valor == attr),
                                                         attr.replace("_", " ").capitalize())
            totales.append((etiqueta, moneda(total) if es_dinero else numero(total)))
    return render_template(
        "crud/list.html", modulo=modulo, filtros=filtros_ui, filas=filas, paginacion=paginacion, totales=totales,
        buscar=buscar, args=args, enlaces=[(t, resolver_enlace(s)) for t, s in modulo.enlaces],
        puede_crear=modulo.puede_crear and puede(modulo.permiso, CREAR),
        url_detalle=lambda o: modulo.detalle_url(o) if modulo.detalle_url else url_for("crud.detalle", key=key,
                                                                                        id=o.id),
    )


def describir_filtros(filtros_ui):
    partes = []
    for f in filtros_ui:
        if f["tipo"] == "rango":
            if f["desde"] or f["hasta"]:
                partes.append(f"Fecha: {f['desde'] or '…'} a {f['hasta'] or '…'}")
        elif f.get("valor"):
            etiqueta = dict((str(k), v) for k, v in f.get("opciones", [])).get(str(f["valor"]), f["valor"])
            partes.append(f"{f['etiqueta']}: {etiqueta}")
    return " · ".join(partes)


# ------------------------------------------------------------------ FORMULARIO
def campos_visibles(modulo, obj):
    return [c for c in modulo.campos if not (c.solo_crear and obj is not None)]


def preparar_campos(modulo, obj):
    salida = []
    for campo in campos_visibles(modulo, obj):
        opciones = campo.opciones() if campo.tipo in ("select", "choice") or campo._opciones else []
        salida.append({
            "c": campo,
            "opciones": opciones,
            "padres": json.dumps({str(o[0]): o[2] for o in opciones if o[2] is not None}) if campo.depende else None,
            "extras": json.dumps({str(o[0]): o[3] for o in opciones if o[3]}) if campo.autocompleta else None,
        })
    return salida


def valores_iniciales(modulo, obj):
    valores = {}
    for campo in campos_visibles(modulo, obj):
        if obj is not None and not campo.virtual:
            valores[campo.nombre] = campo.a_texto(getattr(obj, campo.nombre, None))
        else:
            desde_url = request.args.get(campo.nombre)
            valores[campo.nombre] = desde_url if desde_url is not None else campo.a_texto(campo.valor_defecto())
    for clave in modulo.filtro_fijo:
        if obj is None and request.args.get(clave):
            valores[clave] = request.args.get(clave)
    if obj is None:  # ej. /m/cosechas/nuevo?siembra_id=5 completa finca, lote, campaña, cultivo y hectáreas
        for campo in modulo.campos:
            if campo.autocompleta and request.args.get(campo.nombre):
                extra = next((o[3] for o in campo.opciones() if str(o[0]) == request.args[campo.nombre]), None)
                for clave, valor in (extra or {}).items():
                    if clave in valores and clave not in request.args and valor not in (None, ""):
                        valores[clave] = str(valor)
    return valores


def leer_formulario(modulo, obj):
    datos, errores, crudos = {}, {}, {}
    for campo in campos_visibles(modulo, obj):
        if campo.solo_lectura:
            continue
        crudo = request.form.get(campo.nombre)
        crudos[campo.nombre] = crudo or ""
        valor, error = campo.parsear(crudo)
        if error == "Opción no válida." and obj is not None and not campo.virtual \
                and campo.a_texto(getattr(obj, campo.nombre, None)) == (crudo or "").strip():
            valor, error = getattr(obj, campo.nombre), None  # valor ya guardado (ej. finca hoy inactiva)
        if error:
            errores[campo.nombre] = error
        else:
            datos[campo.nombre] = valor
    # Reglas generales
    if datos.get("lote_id") and "finca_id" in datos:
        lote = db.session.get(Lote, datos["lote_id"])
        if lote and lote.finca_id != datos.get("finca_id"):
            errores["lote_id"] = "El lote no pertenece a la finca elegida."
    if modulo.finca_attr == "finca_id" and modulo.campo("finca_id") and fincas_permitidas() is not None \
            and not datos.get("finca_id") and "finca_id" not in errores:
        errores["finca_id"] = "Elegí la finca."
    if not errores and modulo.validar:
        errores.update(modulo.validar(datos, obj) or {})
    return datos, errores, crudos


def guardar(modulo, obj, nuevo):
    datos, errores, crudos = leer_formulario(modulo, obj)
    if errores:
        return None, errores, crudos
    anterior = {c.name: getattr(obj, c.name) for c in modulo.modelo.__table__.columns} if not nuevo else None
    try:
        if nuevo:
            obj = modulo.modelo(empresa_id=empresa_id())
            if modulo.usuario_attr:
                from flask_login import current_user
                setattr(obj, modulo.usuario_attr, current_user.id)
        extra = {}
        for nombre, valor in datos.items():
            campo = modulo.campo(nombre)
            if campo.virtual:
                extra[nombre] = valor
            else:
                setattr(obj, nombre, valor)
        obj._extra = extra
        for clave in modulo.filtro_fijo:
            if nuevo and request.args.get(clave) and hasattr(obj, clave) and getattr(obj, clave) is None:
                setattr(obj, clave, request.args.get(clave))
        if modulo.preparar:
            modulo.preparar(obj)
        if nuevo:
            db.session.add(obj)
        db.session.flush()
        if modulo.guardar:
            modulo.guardar(obj, nuevo, anterior)
            db.session.flush()
        articulo = "una" if modulo.genero == "a" else "un"
        accion = "crear" if nuevo else "editar"
        auditoria.registrar(modulo.key, accion,
                            auditoria.frase(accion, f"{articulo} {modulo.singular.lower()}: {modulo.describir(obj)}"),
                            obj.id)
        db.session.commit()
        return obj, {}, crudos
    except ErrorNegocio as e:
        db.session.rollback()
        return None, {"__general__": str(e)}, crudos
    except IntegrityError:
        db.session.rollback()
        return None, {"__general__": "Ya existe un registro con esos datos (nombre, CUIT, DNI o patente repetidos) "
                                     "o falta un dato relacionado."}, crudos


@bp.route("/<key>/nuevo", methods=["GET", "POST"])
def nuevo(key):
    modulo = obtener_modulo(key)
    verificar(modulo, CREAR)
    if not modulo.puede_crear:
        abort(404)
    if request.method == "POST":
        obj, errores, crudos = guardar(modulo, None, True)
        if not errores:
            flash(f"{modulo.singular} guardad{modulo.genero} correctamente.", "exito")
            if request.form.get("_accion") == "otro":
                conservar = {k: v for k, v in crudos.items() if k in PRESERVAR and v}
                conservar.update({k: request.args[k] for k in modulo.filtro_fijo if request.args.get(k)})
                return redirect(url_for("crud.nuevo", key=key, **conservar))
            if modulo.detalle_url:
                return redirect(url_for("crud.listar", key=key))
            return redirect(url_for("crud.detalle", key=key, id=obj.id))
        return render_template("crud/form.html", modulo=modulo, obj=None, campos=preparar_campos(modulo, None),
                               valores=crudos, errores=errores), 400
    return render_template("crud/form.html", modulo=modulo, obj=None, campos=preparar_campos(modulo, None),
                           valores=valores_iniciales(modulo, None), errores={})


@bp.route("/<key>/<int:id>/editar", methods=["GET", "POST"])
def editar(key, id):
    modulo = obtener_modulo(key)
    verificar(modulo, EDITAR)
    obj = obtener_o_404(modulo.modelo, id, modulo.finca_attr)
    if modulo.editable:
        ok, mensaje = modulo.editable(obj)
        if not ok:
            flash(mensaje, "aviso")
            return redirect(url_for("crud.detalle", key=key, id=id))
    if request.method == "POST":
        guardado, errores, crudos = guardar(modulo, obj, False)
        if not errores:
            flash("Cambios guardados.", "exito")
            if modulo.detalle_url:
                return redirect(modulo.detalle_url(guardado))
            return redirect(url_for("crud.detalle", key=key, id=id))
        obj = obtener_o_404(modulo.modelo, id, modulo.finca_attr)
        return render_template("crud/form.html", modulo=modulo, obj=obj, campos=preparar_campos(modulo, obj),
                               valores=crudos, errores=errores), 400
    return render_template("crud/form.html", modulo=modulo, obj=obj, campos=preparar_campos(modulo, obj),
                           valores=valores_iniciales(modulo, obj), errores={})


# ------------------------------------------------------------------ DETALLE
@bp.route("/<key>/<int:id>")
def detalle(key, id):
    modulo = obtener_modulo(key)
    verificar(modulo, VER)
    obj = obtener_o_404(modulo.modelo, id, modulo.finca_attr)
    datos = [(c.etiqueta, mostrar_campo(c, obj), c.tipo) for c in modulo.campos if not c.virtual]
    secciones = modulo.detalle_extra(obj) if modulo.detalle_extra else []
    gastos = []
    if modulo.origen_gasto:
        gastos = db.session.scalars(select(Gasto).where(Gasto.empresa_id == empresa_id(),
                                                        Gasto.origen == modulo.origen_gasto,
                                                        Gasto.origen_id == obj.id)).unique().all()
    documentos = []
    if modulo.entidad_documento:
        documentos = db.session.scalars(select(Documento).where(
            Documento.empresa_id == empresa_id(), Documento.entidad == modulo.entidad_documento,
            Documento.entidad_id == obj.id).order_by(Documento.fecha.desc())).unique().all()
    editable, motivo = (modulo.editable(obj) if modulo.editable else (True, None))
    return render_template(
        "crud/detail.html", modulo=modulo, obj=obj, datos=datos, secciones=secciones, gastos=gastos,
        documentos=documentos, editable=editable, motivo=motivo,
        acciones=modulo.acciones_detalle(obj) if modulo.acciones_detalle else [],
        puede_editar=puede(modulo.permiso, EDITAR) and editable,
        puede_eliminar=puede(modulo.permiso, ELIMINAR),
    )


# ------------------------------------------------------------------ ELIMINAR
@bp.route("/<key>/<int:id>/eliminar", methods=["POST"])
def eliminar(key, id):
    modulo = obtener_modulo(key)
    verificar(modulo, ELIMINAR)
    obj = obtener_o_404(modulo.modelo, id, modulo.finca_attr)
    descripcion = modulo.describir(obj)
    try:
        if modulo.eliminar:
            modulo.eliminar(obj)
        if obj in db.session:
            db.session.delete(obj)
        db.session.flush()
        articulo = "una" if modulo.genero == "a" else "un"
        auditoria.registrar(key, "eliminar",
                            auditoria.frase("eliminar", f"{articulo} {modulo.singular.lower()}: {descripcion}"), id)
        db.session.commit()
        flash(f"{modulo.singular} eliminad{modulo.genero}.", "exito")
        return redirect(url_for("crud.listar", key=key))
    except ErrorNegocio as e:
        db.session.rollback()
        flash(str(e), "error")
    except IntegrityError:
        db.session.rollback()
        flash("No se puede eliminar porque tiene registros asociados. Podés marcarlo como inactivo.", "error")
    if modulo.detalle_url:
        return redirect(url_for("crud.listar", key=key))
    return redirect(url_for("crud.detalle", key=key, id=id))
