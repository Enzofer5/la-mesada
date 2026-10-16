"""Definición declarativa de campos de formulario, columnas y módulos para el motor CRUD."""
from datetime import date
from decimal import Decimal

from ..utils.fechas import parse_fecha
from ..utils.validacion import cuit_valido, email_valido, normalizar_cuit, parse_decimal

TIPOS_NUMERICOS = {"int", "decimal", "money"}


class Campo:
    """Un campo del formulario.

    tipo: text | textarea | email | tel | int | decimal | money | date | select | choice | bool | cuit
    opciones: para select (lista o función que devuelve [(valor, etiqueta, padre, extra)]) y choice
              (lista de (valor, etiqueta)).
    depende: nombre del campo del que depende (filtra opciones en el navegador, ej. lote depende de finca).
    autocompleta: al elegir una opción, completa otros campos con los datos de 'extra'.
    """

    def __init__(self, nombre, etiqueta, tipo="text", requerido=False, opciones=None, ayuda=None, minimo=None,
                 maximo=None, maxlen=None, depende=None, defecto=None, ancho="medio", placeholder=None,
                 autocompleta=False, mostrar=None, solo_lectura=False, seccion=None, paso=None, virtual=False,
                 solo_crear=False):
        self.nombre = nombre
        self.etiqueta = etiqueta
        self.tipo = tipo
        self.requerido = requerido
        self._opciones = opciones
        self.ayuda = ayuda
        self.minimo = minimo
        self.maximo = maximo
        self.maxlen = maxlen or (255 if tipo in ("text", "email", "tel") else None)
        self.depende = depende
        self.defecto = defecto
        self.ancho = ancho
        self.placeholder = placeholder
        self.autocompleta = autocompleta
        self.mostrar = mostrar
        self.solo_lectura = solo_lectura
        self.seccion = seccion
        self.virtual = virtual  # no es columna del modelo: se pasa a la regla de negocio en obj._extra
        self.solo_crear = solo_crear  # sólo se muestra al crear
        self.paso = paso or ("1" if tipo == "int" else "any")
        if tipo in ("decimal", "money") and minimo is None:
            self.minimo = 0

    # --------------------------------------------------------------- opciones
    def opciones(self):
        ops = self._opciones() if callable(self._opciones) else (self._opciones or [])
        salida = []
        for op in ops:
            op = tuple(op)
            salida.append(op + (None,) * (4 - len(op)))
        return salida

    def etiqueta_de(self, valor):
        for op in self.opciones():
            if str(op[0]) == str(valor):
                return op[1]
        return valor

    def valor_defecto(self):
        return self.defecto() if callable(self.defecto) else self.defecto

    # --------------------------------------------------------------- conversión
    def a_texto(self, valor):
        """Valor del modelo → texto para el input."""
        if valor is None:
            return ""
        if self.tipo == "bool":
            return "1" if valor else ""
        if isinstance(valor, date):
            return valor.isoformat()
        if isinstance(valor, Decimal):
            texto = format(valor.normalize(), "f")
            return texto
        return str(valor)

    def parsear(self, crudo):
        """Texto del formulario → (valor, error)."""
        if self.tipo == "bool":
            return (crudo in ("1", "on", "true", "si")), None
        texto = (crudo or "").strip()
        if texto == "":
            if self.requerido:
                return None, "Este dato es obligatorio."
            return None, None
        if self.maxlen and len(texto) > self.maxlen:
            return None, f"Máximo {self.maxlen} caracteres."
        try:
            if self.tipo == "int":
                valor = int(texto)
            elif self.tipo in ("decimal", "money"):
                valor = parse_decimal(texto)
            elif self.tipo == "date":
                valor = parse_fecha(texto)
                if valor is None:
                    return None, "Fecha inválida."
                if not (date(1990, 1, 1) <= valor <= date(2100, 12, 31)):
                    return None, "Fecha fuera de rango."
            elif self.tipo == "select":
                valor = int(texto)
                if valor not in {op[0] for op in self.opciones()}:
                    return None, "Opción no válida."
            elif self.tipo == "choice":
                valor = texto
                if valor not in {str(op[0]) for op in self.opciones()}:
                    return None, "Opción no válida."
            elif self.tipo == "email":
                valor = texto.lower()
                if not email_valido(valor):
                    return None, "Email inválido."
            elif self.tipo == "cuit":
                if not cuit_valido(texto):
                    return None, "CUIT/CUIL inválido (11 dígitos)."
                valor = normalizar_cuit(texto)
            else:
                valor = texto
        except (ValueError, TypeError):
            return None, "Valor inválido."
        if self.tipo in TIPOS_NUMERICOS:
            if self.minimo is not None and valor < self.minimo:
                return None, f"Debe ser mayor o igual a {self.minimo}."
            if self.maximo is not None and valor > self.maximo:
                return None, f"Debe ser menor o igual a {self.maximo}."
        return valor, None


class Columna:
    """Columna de un listado. valor: ruta de atributos ('finca.nombre') o función(obj)."""

    def __init__(self, valor, etiqueta, formato=None, clase=None, movil=True):
        self.valor = valor
        self.etiqueta = etiqueta
        self.formato = formato  # None | num | moneda | fecha | bool | estado | choice:<dict>
        self.clase = clase
        self.movil = movil

    def obtener(self, obj):
        if callable(self.valor):
            return self.valor(obj)
        actual = obj
        for parte in self.valor.split("."):
            if actual is None:
                return None
            actual = getattr(actual, parte, None)
        return actual


def C(*args, **kwargs):
    return Columna(*args, **kwargs)


ESTADOS_ACTIVO = [("activo", "Activo"), ("inactivo", "Inactivo")]
ESTADOS_ACTIVA = [("activa", "Activa"), ("inactiva", "Inactiva")]
