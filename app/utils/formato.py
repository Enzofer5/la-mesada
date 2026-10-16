"""Formatos argentinos para mostrar números, dinero y fechas (filtros Jinja)."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

MESES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre",
         "Octubre", "Noviembre", "Diciembre"]
MESES_CORTOS = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def _num_es(valor, decimales):
    texto = f"{valor:,.{decimales}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def numero(valor, decimales=2):
    if valor is None or valor == "":
        return "—"
    try:
        valor = Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return str(valor)
    if decimales == "auto":
        decimales = 0 if valor == valor.to_integral_value() else 2
    return _num_es(valor, decimales)


def moneda(valor, decimales=0):
    if valor is None or valor == "":
        return "—"
    try:
        valor = Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return str(valor)
    signo = "-" if valor < 0 else ""
    return f"{signo}$ {_num_es(abs(valor), decimales)}"


def porcentaje(valor, decimales=1):
    if valor is None:
        return "—"
    return f"{_num_es(Decimal(str(valor)) * 100, decimales)} %"


def fecha(valor, formato="%d/%m/%Y"):
    if not valor:
        return "—"
    if isinstance(valor, str):
        try:
            valor = date.fromisoformat(valor)
        except ValueError:
            return valor
    return valor.strftime(formato)


def fecha_hora(valor):
    if not valor:
        return "—"
    return valor.strftime("%d/%m/%Y %H:%M") if isinstance(valor, datetime) else fecha(valor)


def registrar_filtros(app):
    app.jinja_env.filters["num"] = numero
    app.jinja_env.filters["moneda"] = moneda
    app.jinja_env.filters["pct"] = porcentaje
    app.jinja_env.filters["fecha"] = fecha
    app.jinja_env.filters["fecha_hora"] = fecha_hora
