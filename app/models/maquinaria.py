"""Maquinaria, uso de maquinaria y cargas de combustible."""
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import Cantidad, Dinero, EmpresaMixin, ImputacionMixin, TimestampMixin


class Maquina(EmpresaMixin, TimestampMixin, db.Model):
    __tablename__ = "maquinaria"
    __table_args__ = (UniqueConstraint("empresa_id", "identificacion", name="uq_maquina_identificacion"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    marca: Mapped[str | None] = mapped_column(String(50))
    modelo: Mapped[str | None] = mapped_column(String(50))
    anio: Mapped[int | None] = mapped_column(Integer)
    identificacion: Mapped[str | None] = mapped_column(String(30))
    horas_uso: Mapped[Decimal] = mapped_column(Numeric(10, 1), nullable=False, default=0)
    estado: Mapped[str] = mapped_column(String(15), nullable=False, default="operativa")
    responsable_id: Mapped[int | None] = mapped_column(ForeignKey("empleados.id"))
    finca_id: Mapped[int | None] = mapped_column(ForeignKey("fincas.id"))
    costo_hora: Mapped[Decimal] = mapped_column(Dinero, nullable=False, default=0)
    intervalo_mantenimiento_horas: Mapped[int | None] = mapped_column(Integer)
    ultimo_mantenimiento_horas: Mapped[Decimal | None] = mapped_column(Numeric(10, 1))
    proximo_mantenimiento_fecha: Mapped[date | None] = mapped_column(Date)
    observaciones: Mapped[str | None] = mapped_column(Text)

    responsable = relationship("Empleado", foreign_keys=[responsable_id])
    finca = relationship("Finca")

    def __str__(self):
        return f"{self.nombre}" + (f" ({self.identificacion})" if self.identificacion else "")

    @property
    def horas_para_mantenimiento(self):
        if not self.intervalo_mantenimiento_horas:
            return None
        base = self.ultimo_mantenimiento_horas or 0
        return (base + self.intervalo_mantenimiento_horas) - (self.horas_uso or 0)


class UsoMaquinaria(EmpresaMixin, ImputacionMixin, TimestampMixin, db.Model):
    __tablename__ = "uso_maquinaria"
    _finca_obligatoria = True
    id: Mapped[int] = mapped_column(primary_key=True)
    maquina_id: Mapped[int] = mapped_column(ForeignKey("maquinaria.id"), nullable=False, index=True)
    fecha: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    horas: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    operador_id: Mapped[int | None] = mapped_column(ForeignKey("empleados.id"))
    trabajo_realizado: Mapped[str] = mapped_column(String(150), nullable=False)
    combustible_litros: Mapped[Decimal] = mapped_column(Cantidad, nullable=False, default=0)
    costo_combustible: Mapped[Decimal] = mapped_column(Dinero, nullable=False, default=0)
    costo_mantenimiento: Mapped[Decimal] = mapped_column(Dinero, nullable=False, default=0)
    costo_hora: Mapped[Decimal] = mapped_column(Dinero, nullable=False, default=0)
    costo_total: Mapped[Decimal] = mapped_column(Dinero, nullable=False, default=0)
    observaciones: Mapped[str | None] = mapped_column(Text)

    maquina = relationship("Maquina")
    operador = relationship("Empleado")


class CargaCombustible(EmpresaMixin, ImputacionMixin, TimestampMixin, db.Model):
    __tablename__ = "combustibles"
    id: Mapped[int] = mapped_column(primary_key=True)
    fecha: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    tipo_combustible: Mapped[str] = mapped_column(String(20), nullable=False)
    litros: Mapped[Decimal] = mapped_column(Cantidad, nullable=False)
    precio_litro: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Dinero, nullable=False, default=0)
    maquina_id: Mapped[int | None] = mapped_column(ForeignKey("maquinaria.id"), index=True)
    responsable_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    proveedor_id: Mapped[int | None] = mapped_column(ForeignKey("proveedores.id"))
    metodo_pago: Mapped[str] = mapped_column(String(20), nullable=False, default="efectivo")
    vencimiento: Mapped[date | None] = mapped_column(Date)
    imputar_gasto: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    observaciones: Mapped[str | None] = mapped_column(Text)

    maquina = relationship("Maquina")
    responsable = relationship("Usuario")
    proveedor = relationship("Proveedor")
