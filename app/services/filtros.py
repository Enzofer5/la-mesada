"""Lectura de filtros de análisis (finca, cultivo, campaña, año, rango de fechas, categoría) desde la URL."""
from datetime import date

from ..extensions import db
from ..models import Campana, CategoriaGasto, Cultivo, Finca, Lote
from ..utils.fechas import parse_fecha
from .opciones import campana_activa
from .tenant import empresa_id, finca_permitida


def _id(args, clave, modelo):
    valor = args.get(clave, "")
    if not str(valor).isdigit():
        return None
    obj = db.session.get(modelo, int(valor))
    if obj is None or obj.empresa_id != empresa_id():
        return None
    return obj.id


def leer(args, por_defecto_campana=False):
    """Devuelve un dict de filtros validados. Con por_defecto_campana, si no hay filtros usa la campaña activa."""
    f = {
        "finca": _id(args, "finca", Finca),
        "lote": _id(args, "lote", Lote),
        "cultivo": _id(args, "cultivo", Cultivo),
        "campana": _id(args, "campana", Campana),
        "categoria": _id(args, "categoria", CategoriaGasto),
        "desde": parse_fecha(args.get("desde")),
        "hasta": parse_fecha(args.get("hasta")),
        "anio": None,
    }
    if f["finca"] and not finca_permitida(f["finca"], permitir_general=False):
        f["finca"] = None
    anio = args.get("anio", "")
    if anio.isdigit() and 1990 <= int(anio) <= 2100:
        f["anio"] = int(anio)
        f["desde"] = f["desde"] or date(f["anio"], 1, 1)
        f["hasta"] = f["hasta"] or date(f["anio"], 12, 31)
    sin_filtros = not any(f[k] for k in ("finca", "lote", "cultivo", "campana", "desde", "hasta", "anio"))
    if por_defecto_campana and sin_filtros and "todo" not in args:
        activa = campana_activa()
        if activa:
            f["campana"] = activa.id
        else:
            f["anio"] = date.today().year
            f["desde"], f["hasta"] = date(f["anio"], 1, 1), date(f["anio"], 12, 31)
    return f


def descripcion(f):
    partes = []
    if f.get("campana"):
        partes.append(f"Campaña {db.session.get(Campana, f['campana']).nombre}")
    if f.get("finca"):
        partes.append(db.session.get(Finca, f["finca"]).nombre)
    if f.get("lote"):
        partes.append(f"Lote {db.session.get(Lote, f['lote']).nombre}")
    if f.get("cultivo"):
        partes.append(db.session.get(Cultivo, f["cultivo"]).nombre)
    if f.get("categoria"):
        partes.append(db.session.get(CategoriaGasto, f["categoria"]).nombre)
    if f.get("desde") or f.get("hasta"):
        d = f["desde"].strftime("%d/%m/%Y") if f.get("desde") else "…"
        h = f["hasta"].strftime("%d/%m/%Y") if f.get("hasta") else "…"
        partes.append(f"{d} al {h}")
    return " · ".join(partes) or "Todos los datos"


def a_query(f):
    """Filtros → parámetros de URL (para links y exportaciones)."""
    salida = {}
    for clave in ("finca", "lote", "cultivo", "campana", "categoria", "anio"):
        if f.get(clave):
            salida[clave] = f[clave]
    if f.get("desde") and not f.get("anio"):
        salida["desde"] = f["desde"].isoformat()
    if f.get("hasta") and not f.get("anio"):
        salida["hasta"] = f["hasta"].isoformat()
    if not salida:
        salida["todo"] = 1
    return salida
