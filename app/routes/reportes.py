"""Reportes con filtros y exportación a PDF, CSV y Excel."""
from datetime import date

from flask import Blueprint, abort, render_template, request, url_for
from sqlalchemy import select

from ..extensions import db
from ..models import Cultivo, Finca
from ..services import auditoria, exportar, filtros
from ..services import reportes as svc
from ..services.tenant import empresa_id
from ..utils.fechas import fin_mes, inicio_mes
from ..utils.formato import fecha as ffecha, moneda, numero, porcentaje
from ..utils.permisos import requiere_permiso
from .comun import opciones_filtros

bp = Blueprint("reportes", __name__, url_prefix="/reportes")


def _buscar_id(modelo, nombre):
    obj = db.session.scalar(select(modelo).where(modelo.empresa_id == empresa_id(), modelo.nombre == nombre))
    return obj.id if obj else None


def preguntas():
    """Las preguntas frecuentes del propietario, cada una con el reporte que la responde."""
    anio = date.today().year
    papa, cebolla = _buscar_id(Cultivo, "Papa"), _buscar_id(Cultivo, "Cebolla")
    finca1, finca2 = _buscar_id(Finca, "Finca 1"), _buscar_id(Finca, "Finca 2")

    def u(tipo, **kw):
        return url_for("reportes.ver", tipo=tipo, **{k: v for k, v in kw.items() if v})
    mes = {"desde": inicio_mes().isoformat(), "hasta": fin_mes().isoformat()}
    return [
        (f"¿Cuánto gastamos este año en la papa de la Finca 2?", u("gastos_categoria", anio=anio, cultivo=papa, finca=finca2)),
        ("¿Cuánto le pagamos a los cargadores este mes?", u("mano_obra_tipo", **mes)),
        ("¿Cuánto gastamos en fertilizantes?", u("gastos_categoria", anio=anio)),
        ("¿Cuánto produjo la Finca 1?", u("produccion_finca", finca=finca1, todo=1)),
        ("¿Cuánto nos dejó la cebolla?", u("rent_cultivo", cultivo=cebolla, todo=1)),
        ("¿Cuál de las fincas es más rentable?", u("rent_finca", todo=1)),
        ("¿Cuánto nos costó producir una hectárea de papa?", u("costo_produccion", cultivo=papa, todo=1)),
        ("¿Cuánto ganamos por tonelada?", u("rent_cultivo", todo=1)),
        ("¿Cuánto dinero gastamos en combustible?", u("combustible", anio=anio)),
        ("¿Cuánto le debemos a los proveedores?", u("cuentas_pagar", todo=1)),
        ("¿Cuánto tenemos que cobrar por ventas pendientes?", u("cuentas_cobrar", todo=1)),
    ]


@bp.route("/")
@requiere_permiso("reportes")
def index():
    return render_template("reportes/index.html", reportes=svc.REPORTES, preguntas=preguntas())


def _formatear(valor, formato):
    if valor is None or valor == "":
        return "—" if formato != "texto" else ""
    if formato == "moneda":
        return moneda(valor)
    if formato == "num":
        return numero(valor)
    if formato == "pct":
        return porcentaje(valor)
    if formato == "fecha":
        return ffecha(valor)
    return str(valor)


@bp.route("/<tipo>")
@requiere_permiso("reportes")
def ver(tipo):
    if tipo not in svc.POR_CLAVE:
        abort(404)
    titulo, funcion, grupo = svc.POR_CLAVE[tipo]
    f = filtros.leer(request.args, por_defecto_campana=True)
    resultado = funcion(f, request.args)
    descripcion = filtros.descripcion(f)
    formato = request.args.get("exportar")
    if formato in ("csv", "xlsx", "pdf"):
        auditoria.registrar("reportes", "exportar", f"Exportó el reporte {titulo} ({formato})")
        db.session.commit()
        return _exportar(formato, resultado, descripcion)
    tablas = []
    for t in resultado["tablas"]:
        tablas.append({**t, "filas_fmt": [[_formatear(v, fm) for v, fm in zip(fila, t["formatos"])] for fila in t["filas"]],
                       "totales_fmt": [_formatear(v, fm) for v, fm in zip(t["totales"], t["formatos"])]
                       if t.get("totales") else None})
    return render_template("reportes/ver.html", tipo=tipo, titulo=resultado["titulo"], grupo=grupo, tablas=tablas,
                           f=f, descripcion=descripcion, opciones=opciones_filtros(con_categoria=True),
                           usa_prorrateo=tipo in svc.USA_PRORRATEO, usa_categoria=tipo in svc.USA_CATEGORIA,
                           query=filtros.a_query(f), prorratear=request.args.get("prorratear") == "1")


def _exportar(formato, resultado, descripcion):
    tablas = resultado["tablas"]
    if len(tablas) == 1 or formato == "pdf" and len(tablas) == 1:
        t = tablas[0]
        filas = t["filas"] if formato != "pdf" else [[_formatear(v, fm) for v, fm in zip(fila, t["formatos"])]
                                                     for fila in t["filas"]]
        totales = t.get("totales")
        if totales and formato == "pdf":
            totales = [_formatear(v, fm) for v, fm in zip(totales, t["formatos"])]
        return exportar.respuesta(formato, resultado["titulo"], t["columnas"], filas,
                                  subtitulo=" · ".join(x for x in (descripcion, t.get("subtitulo")) if x),
                                  totales=totales)
    # Varias tablas: se exportan una debajo de la otra con su subtítulo
    ancho = max(len(t["columnas"]) for t in tablas)
    filas = []
    for t in tablas:
        filas.append([f"— {t['subtitulo'] or ''} —"] + [""] * (ancho - 1))
        filas.append(t["columnas"] + [""] * (ancho - len(t["columnas"])))
        for fila in t["filas"] + ([t["totales"]] if t.get("totales") else []):
            fila = [_formatear(v, fm) for v, fm in zip(fila, t["formatos"])] if formato == "pdf" else list(fila)
            filas.append(fila + [""] * (ancho - len(fila)))
        filas.append([""] * ancho)
    return exportar.respuesta(formato, resultado["titulo"], [""] * ancho, filas, subtitulo=descripcion)
