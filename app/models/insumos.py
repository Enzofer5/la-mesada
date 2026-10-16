"""Insumos (semillas, fertilizantes, agroquímicos, repuestos, combustible, otros), stock y aplicaciones."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import Cantidad, Dinero, EmpresaMixin, Hectareas, ImputacionMixin, TimestampMixin

CATEGORIAS_INSUMO = [
    ("semilla", "Semilla"),
    ("fertilizante", "Fertilizante"),
    ("agroquimico", "Agroquímico"),
    ("repuesto", "Repuesto"),
    ("combustible", "Combustible"),
    ("otro", "Otro insumo"),
]


class Insumo(EmpresaMixin, TimestampMixin, db.Model):
    __tablename__ = "insumos"
    __table_args__ = (UniqueConstraint("empresa_id", "nombre", name="uq_insumo_empresa_nombre"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    categoria: Mapped[str] = mapped_column(String(15), nullable=False, index=True)
    tipo: Mapped[str | None] = mapped_column(String(40))
    unidad_id: Mapped[int] = mapped_column(ForeignKey("unidades_medida.id"), nullable=False)
    principio_activo: Mapped[str | None] = mapped_column(String(120))
    stock_minimo: Mapped[Decimal] = mapped_column(Cantidad, nullable=False, default=0)
    proveedor_id: Mapped[int | None] = mapped_column(ForeignKey("proveedores.id"))
    observaciones: Mapped[str | None] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(String(12), nullable=False, default="activo")
    # Semilla propia: se produce en la explotación (se guarda de la cosecha). Su stock no tiene costo.
    propia: Mapped[bool | None] = mapped_column(Boolean, default=False)

    unidad = relationship("UnidadMedida", lazy="joined")
    proveedor = relationship("Proveedor")
    inventario = relationship("Inventario", uselist=False, back_populates="insumo", lazy="joined")

    def __str__(self):
        return self.nombre

    @property
    def stock(self):
        return self.inventario.cantidad if self.inventario else Decimal("0")

    @property
    def costo_promedio(self):
        return self.inventario.costo_promedio if self.inventario else Decimal("0")


class Inventario(EmpresaMixin, db.Model):
    """Stock actual y costo promedio ponderado de cada insumo (se recalcula desde los movimientos)."""

    __tablename__ = "inventario"
    id: Mapped[int] = mapped_column(primary_key=True)
    insumo_id: Mapped[int] = mapped_column(ForeignKey("insumos.id", ondelete="CASCADE"), nullable=False, unique=True)
    cantidad: Mapped[Decimal] = mapped_column(Cantidad, nullable=False, default=0)
    costo_promedio: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=0)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    insumo = relationship("Insumo", back_populates="inventario")


class MovimientoInventario(EmpresaMixin, ImputacionMixin, TimestampMixin, db.Model):
    __tablename__ = "movimientos_inventario"
    __table_args__ = (
        Index("ix_mov_origen", "origen", "origen_id"),
        Index("ix_mov_insumo_fecha", "insumo_id", "fecha"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    insumo_id: Mapped[int] = mapped_column(ForeignKey("insumos.id"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)  # entrada | salida | ajuste
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    cantidad: Mapped[Decimal] = mapped_column(Cantidad, nullable=False)
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=0)
    proveedor_id: Mapped[int | None] = mapped_column(ForeignKey("proveedores.id"))
    responsable_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    origen: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")
    origen_id: Mapped[int | None] = mapped_column(Integer)
    observaciones: Mapped[str | None] = mapped_column(Text)

    insumo = relationship("Insumo")
    proveedor = relationship("Proveedor")
    responsable = relationship("Usuario")

    @property
    def total(self):
        return (self.cantidad or 0) * (self.precio_unitario or 0)


class AplicacionFertilizante(EmpresaMixin, ImputacionMixin, TimestampMixin, db.Model):
    __tablename__ = "aplicaciones_fertilizantes"
    _finca_obligatoria = True
    id: Mapped[int] = mapped_column(primary_key=True)
    insumo_id: Mapped[int] = mapped_column(ForeignKey("insumos.id"), nullable=False, index=True)
    fecha: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    superficie: Mapped[Decimal | None] = mapped_column(Hectareas)
    cantidad: Mapped[Decimal] = mapped_column(Cantidad, nullable=False)
    costo_unitario: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=0)
    costo_total: Mapped[Decimal] = mapped_column(Dinero, nullable=False, default=0)
    responsable_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    observaciones: Mapped[str | None] = mapped_column(Text)

    insumo = relationship("Insumo")
    responsable = relationship("Usuario")

    @property
    def dosis_ha(self):
        if self.superficie and self.superficie > 0:
            return self.cantidad / self.superficie
        return None


class AplicacionAgroquimico(EmpresaMixin, ImputacionMixin, TimestampMixin, db.Model):
    __tablename__ = "aplicaciones_agroquimicos"
    _finca_obligatoria = True
    id: Mapped[int] = mapped_column(primary_key=True)
    insumo_id: Mapped[int] = mapped_column(ForeignKey("insumos.id"), nullable=False, index=True)
    fecha: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    superficie: Mapped[Decimal | None] = mapped_column(Hectareas)
    dosis: Mapped[Decimal | None] = mapped_column(Cantidad)
    unidad_dosis: Mapped[str | None] = mapped_column(String(15))
    cantidad: Mapped[Decimal] = mapped_column(Cantidad, nullable=False)
    motivo: Mapped[str | None] = mapped_column(String(150))
    costo_unitario: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=0)
    costo_total: Mapped[Decimal] = mapped_column(Dinero, nullable=False, default=0)
    responsable_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    observaciones: Mapped[str | None] = mapped_column(Text)

    insumo = relationship("Insumo")
    responsable = relationship("Usuario")
