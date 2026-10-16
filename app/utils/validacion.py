"""Validaciones reutilizables."""
import re
from decimal import Decimal, InvalidOperation

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ErrorNegocio(Exception):
    """Error de regla de negocio que se muestra al usuario (ej. stock insuficiente)."""


def parse_decimal(texto):
    """Acepta 1234.5, 1234,5 y 1.234,5 (formato argentino). Devuelve Decimal o None. Lanza ValueError."""
    if texto is None:
        return None
    texto = str(texto).strip().replace("$", "").replace(" ", "")
    if texto == "":
        return None
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif texto.count(".") > 1:  # 1.000.000 → separador de miles
        texto = texto.replace(".", "")
    try:
        valor = Decimal(texto)
    except InvalidOperation:
        raise ValueError("Número inválido")
    if not valor.is_finite():
        raise ValueError("Número inválido")
    return valor


def cuit_valido(cuit):
    """Valida CUIT/CUIL argentino (11 dígitos con dígito verificador)."""
    digitos = re.sub(r"\D", "", cuit or "")
    if len(digitos) != 11:
        return False
    pesos = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    suma = sum(int(d) * p for d, p in zip(digitos[:10], pesos))
    resto = 11 - (suma % 11)
    verificador = 0 if resto == 11 else 9 if resto == 10 else resto
    return verificador == int(digitos[10])


def normalizar_cuit(cuit):
    digitos = re.sub(r"\D", "", cuit or "")
    if len(digitos) == 11:
        return f"{digitos[:2]}-{digitos[2:10]}-{digitos[10]}"
    return cuit


def email_valido(email):
    return bool(EMAIL_RE.match(email or ""))


def clave_segura(clave):
    """Mínimo 8 caracteres, con letras y números."""
    if not clave or len(clave) < 8:
        return False
    return bool(re.search(r"[A-Za-z]", clave)) and bool(re.search(r"\d", clave))
