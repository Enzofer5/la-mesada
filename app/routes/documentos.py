"""Documentos (facturas, remitos, comprobantes, documentación de vehículos y empleados)."""
import os
import uuid
from datetime import date

from flask import (Blueprint, abort, current_app, flash, redirect, render_template, request, send_from_directory,
                   url_for)
from flask_login import current_user
from sqlalchemy import or_, select
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import Cliente, Compra, Documento, Empleado, Finca, Maquina, Proveedor, Venta
from ..services import auditoria
from ..services.tenant import consulta, empresa_id, fincas_permitidas, obtener_o_404
from ..utils.fechas import parse_fecha
from ..utils.permisos import CREAR, ELIMINAR, puede, requiere_permiso

bp = Blueprint("documentos", __name__, url_prefix="/documentos")

ENTIDADES = {
    "finca": ("Fincas", Finca, lambda o: o.nombre, "id"),
    "empleado": ("Empleados", Empleado, lambda o: o.nombre_completo, "finca_id"),
    "maquina": ("Maquinaria", Maquina, lambda o: o.nombre, "finca_id"),
    "proveedor": ("Proveedores", Proveedor, lambda o: o.razon_social, None),
    "cliente": ("Clientes", Cliente, lambda o: o.nombre, None),
    "compra": ("Compras", Compra, lambda o: f"Compra #{o.id} · {o.proveedor.razon_social}", "finca_id"),
    "venta": ("Ventas", Venta, lambda o: f"Venta #{o.id} · {o.cliente.nombre}", "finca_id"),
    "otro": ("General", None, None, None),
}
TIPOS_DOC = [("factura", "Factura"), ("remito", "Remito"), ("comprobante", "Comprobante de pago"),
             ("doc_vehiculo", "Documentación de vehículo"), ("doc_empleado", "Documentación de empleado"),
             ("contrato", "Contrato"), ("analisis", "Análisis de suelo / agua"), ("otro", "Otro")]


def _referencias():
    grupos = []
    ids = fincas_permitidas()
    for clave, (titulo, modelo, etiqueta, finca_attr) in ENTIDADES.items():
        if modelo is None:
            continue
        stmt = consulta(modelo)
        if finca_attr and ids is not None:
            col = getattr(modelo, finca_attr)
            stmt = stmt.where(or_(col.in_(ids or [-1]), col.is_(None)) if finca_attr != "id" else col.in_(ids or [-1]))
        objetos = db.session.scalars(stmt.order_by(modelo.id.desc()).limit(300)).unique().all()
        grupos.append((titulo, [(f"{clave}:{o.id}", etiqueta(o)) for o in objetos]))
    return grupos


def _finca_de(entidad, obj):
    if obj is None:
        return None
    if entidad == "finca":
        return obj.id
    return getattr(obj, "finca_id", None)


def _visible(doc):
    ids = fincas_permitidas()
    return ids is None or doc.finca_id is None or doc.finca_id in ids


@bp.route("/")
@requiere_permiso("documentos")
def listar():
    stmt = consulta(Documento).order_by(Documento.fecha.desc(), Documento.id.desc())
    entidad = request.args.get("entidad")
    if entidad in ENTIDADES:
        stmt = stmt.where(Documento.entidad == entidad)
        if request.args.get("entidad_id", "").isdigit():
            stmt = stmt.where(Documento.entidad_id == int(request.args["entidad_id"]))
    if request.args.get("tipo") in dict(TIPOS_DOC):
        stmt = stmt.where(Documento.tipo_documento == request.args["tipo"])
    q = (request.args.get("q") or "").strip()[:60]
    if q:
        stmt = stmt.where(or_(Documento.nombre.ilike(f"%{q}%"), Documento.nombre_original.ilike(f"%{q}%")))
    ids = fincas_permitidas()
    if ids is not None:
        stmt = stmt.where(or_(Documento.finca_id.in_(ids or [-1]), Documento.finca_id.is_(None)))
    paginacion = db.paginate(stmt, page=max(request.args.get("pagina", 1, type=int), 1),
                             per_page=current_app.config["POR_PAGINA"], error_out=False)
    return render_template("documentos/list.html", paginacion=paginacion, entidades=ENTIDADES, tipos=dict(TIPOS_DOC),
                           args=request.args, puede_subir=puede("documentos", CREAR),
                           puede_eliminar=puede("documentos", ELIMINAR), hoy=date.today())


@bp.route("/subir", methods=["GET", "POST"])
@requiere_permiso("documentos", CREAR)
def subir():
    referencias = _referencias()
    validas = {v for _, items in referencias for v, _ in items}
    preseleccion = ""
    if request.args.get("entidad") in ENTIDADES and request.args.get("entidad_id"):
        preseleccion = f"{request.args['entidad']}:{request.args['entidad_id']}"
    errores = {}
    if request.method == "POST":
        archivo = request.files.get("archivo")
        referencia = request.form.get("referencia", "")
        nombre = (request.form.get("nombre") or "").strip()[:150]
        tipo = request.form.get("tipo_documento")
        if not archivo or not archivo.filename:
            errores["archivo"] = "Elegí un archivo."
        else:
            extension = archivo.filename.rsplit(".", 1)[-1].lower() if "." in archivo.filename else ""
            if extension not in current_app.config["EXTENSIONES_PERMITIDAS"]:
                errores["archivo"] = "Tipo de archivo no permitido (PDF, imágenes, Word, Excel, CSV o TXT)."
        if referencia and referencia not in validas:
            errores["referencia"] = "Referencia no válida."
        if tipo not in dict(TIPOS_DOC):
            errores["tipo_documento"] = "Elegí el tipo de documento."
        if not errores:
            entidad, entidad_id = ("otro", None)
            obj = None
            if referencia:
                entidad, id_txt = referencia.split(":", 1)
                entidad_id = int(id_txt)
                obj = obtener_o_404(ENTIDADES[entidad][1], entidad_id, None)
            carpeta = os.path.join(current_app.config["UPLOAD_FOLDER"], str(empresa_id()))
            os.makedirs(carpeta, exist_ok=True)
            guardado = f"{uuid.uuid4().hex}.{extension}"
            ruta = os.path.join(carpeta, guardado)
            archivo.save(ruta)
            doc = Documento(empresa_id=empresa_id(), entidad=entidad, entidad_id=entidad_id, tipo_documento=tipo,
                            nombre=nombre or secure_filename(archivo.filename)[:150] or "Documento",
                            archivo=guardado, nombre_original=secure_filename(archivo.filename)[:255] or guardado,
                            mime=archivo.mimetype[:100] if archivo.mimetype else None, tamanio=os.path.getsize(ruta),
                            fecha=parse_fecha(request.form.get("fecha")) or date.today(),
                            fecha_vencimiento=parse_fecha(request.form.get("fecha_vencimiento")),
                            finca_id=_finca_de(entidad, obj),
                            observaciones=(request.form.get("observaciones") or "")[:2000] or None,
                            usuario_id=current_user.id)
            db.session.add(doc)
            db.session.flush()
            auditoria.registrar("documentos", "crear", auditoria.frase("crear", f"un documento: {doc.nombre}"), doc.id)
            db.session.commit()
            flash("Documento guardado.", "exito")
            return redirect(url_for("documentos.listar", entidad=entidad if referencia else None,
                                    entidad_id=entidad_id))
    return render_template("documentos/form.html", referencias=referencias, tipos=TIPOS_DOC, errores=errores,
                           preseleccion=request.form.get("referencia", preseleccion), hoy=date.today(),
                           valores=request.form)


@bp.route("/<int:doc_id>/descargar")
@requiere_permiso("documentos")
def descargar(doc_id):
    doc = obtener_o_404(Documento, doc_id, None)
    if not _visible(doc):
        abort(403)
    carpeta = os.path.join(current_app.config["UPLOAD_FOLDER"], str(doc.empresa_id))
    return send_from_directory(carpeta, doc.archivo, as_attachment=request.args.get("ver") != "1",
                               download_name=doc.nombre_original)


@bp.route("/<int:doc_id>/eliminar", methods=["POST"])
@requiere_permiso("documentos", ELIMINAR)
def eliminar(doc_id):
    doc = obtener_o_404(Documento, doc_id, None)
    if not _visible(doc):
        abort(403)
    ruta = os.path.join(current_app.config["UPLOAD_FOLDER"], str(doc.empresa_id), doc.archivo)
    nombre = doc.nombre
    db.session.delete(doc)
    auditoria.registrar("documentos", "eliminar", auditoria.frase("eliminar", f"el documento {nombre}"), doc_id)
    db.session.commit()
    if os.path.exists(ruta):
        os.remove(ruta)
    flash("Documento eliminado.", "exito")
    return redirect(url_for("documentos.listar"))
