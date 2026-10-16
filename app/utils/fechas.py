"""Utilidades de fechas y períodos."""
import calendar
from datetime import date, timedelta


def hoy():
    return date.today()


def inicio_mes(d=None):
    d = d or hoy()
    return d.replace(day=1)


def fin_mes(d=None):
    d = d or hoy()
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


def inicio_anio(anio=None):
    return date(anio or hoy().year, 1, 1)


def fin_anio(anio=None):
    return date(anio or hoy().year, 12, 31)


def parse_fecha(texto):
    if not texto:
        return None
    if isinstance(texto, date):
        return texto
    texto = str(texto).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            from datetime import datetime
            return datetime.strptime(texto, fmt).date()
        except ValueError:
            continue
    return None


def dentro_de(dias):
    return hoy() + timedelta(days=dias)
