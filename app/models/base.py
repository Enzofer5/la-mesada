"""Mixins comunes a los modelos."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

# Tipos numéricos estándar del sistema
Dinero = Numeric(14, 2)
Cantidad = Numeric(14, 3)
Hectareas = Numeric(10, 2)


class TimestampMixin:
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )


class EmpresaMixin:
    """Toda tabla de negocio pertenece a una empresa (multi-empresa)."""

    @declared_attr
    def empresa_id(cls) -> Mapped[int]:
        return mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)


class ImputacionMixin:
    """Asociación de un registro a Finca + Lote + Campaña + Cultivo.

    Cada clase decide qué partes son obligatorias con los atributos _finca_obligatoria, etc.
    """

    _finca_obligatoria = False
    _campana_obligatoria = False
    _cultivo_obligatorio = False

    @declared_attr
    def finca_id(cls) -> Mapped[int]:
        return mapped_column(ForeignKey("fincas.id"), nullable=not cls._finca_obligatoria, index=True)

    @declared_attr
    def lote_id(cls) -> Mapped[int]:
        return mapped_column(ForeignKey("lotes.id"), nullable=True, index=True)

    @declared_attr
    def campana_id(cls) -> Mapped[int]:
        return mapped_column(ForeignKey("campanas.id"), nullable=not cls._campana_obligatoria, index=True)

    @declared_attr
    def cultivo_id(cls) -> Mapped[int]:
        return mapped_column(ForeignKey("cultivos.id"), nullable=not cls._cultivo_obligatorio, index=True)

    @declared_attr
    def finca(cls):
        return relationship("Finca", foreign_keys=[cls.finca_id], lazy="joined")

    @declared_attr
    def lote(cls):
        return relationship("Lote", foreign_keys=[cls.lote_id])

    @declared_attr
    def campana(cls):
        return relationship("Campana", foreign_keys=[cls.campana_id])

    @declared_attr
    def cultivo(cls):
        return relationship("Cultivo", foreign_keys=[cls.cultivo_id], lazy="joined")

    def imputacion(self):
        return {
            "finca_id": self.finca_id,
            "lote_id": self.lote_id,
            "campana_id": self.campana_id,
            "cultivo_id": self.cultivo_id,
        }


def dec(valor, defecto="0"):
    """Convierte a Decimal de forma segura."""
    if valor is None or valor == "":
        return Decimal(defecto)
    if isinstance(valor, Decimal):
        return valor
    return Decimal(str(valor))
