"""Categorías de gasto y gastos (fuente única de costos)."""
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import Dinero, EmpresaMixin, ImputacionMixin, TimestampMixin

# Categorías base (se crean para cada empresa; se pueden renombrar y agregar nuevas)
CATEGORIAS_BASE = [
    ("semillas", "Semillas"),
    ("fertilizantes", "Fertilizantes"),
    ("agroquimicos", "Agroquímicos"),
    ("combustible", "Combustible"),
    ("mano_obra", "Mano de obra"),
    ("maquinaria", "Maquinaria"),
    ("reparaciones", "Reparaciones"),
    ("riego", "Riego"),
    ("transporte", "Transporte"),
    ("alquileres", "Alquileres"),
    ("servicios", "Servicios"),
    ("impuestos", "Impuestos"),
    ("otros", "Otros"),
]

METODOS_PAGO = [
    ("efectivo", "Efectivo"),
    ("transferencia", "Transferencia"),
    ("cheque", "Cheque"),
    ("echeq", "E-cheq"),
    ("tarjeta", "Tarjeta"),
    ("cuenta_corriente", "Cuenta corriente (a pagar)"),
]


class CategoriaGasto(EmpresaMixin, db.Model):
    __tablename__ = "categorias_gasto"
    __table_args__ = (UniqueConstraint("empresa_id", "codigo", name="uq_categoria_empresa_codigo"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), nullable=False)
    nombre: Mapped[str] = mapped_column(String(60), nullable=False)
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __str__(self):
        return self.nombre


class Gasto(EmpresaMixin, ImputacionMixin, TimestampMixin, db.Model):
    __tablename__ = "gastos"
    __table_args__ = (
        Index("ix_gasto_origen", "origen", "origen_id"),
        Index("ix_gasto_empresa_fecha", "empresa_id", "fecha"),
        Index("ix_gasto_empresa_campana_cultivo", "empresa_id", "campana_id", "cultivo_id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categorias_gasto.id"), nullable=False, index=True)
    proveedor_id: Mapped[int | None] = mapped_column(ForeignKey("proveedores.id"), index=True)
    descripcion: Mapped[str] = mapped_column(String(200), nullable=False)
    monto: Mapped[Decimal] = mapped_column(Dinero, nullable=False)
    metodo_pago: Mapped[str] = mapped_column(String(20), nullable=False, default="efectivo")
    vencimiento: Mapped[date | None] = mapped_column(Date)
    comprobante: Mapped[str | None] = mapped_column(String(40))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    origen: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")
    origen_id: Mapped[int | None] = mapped_column(Integer)
    observaciones: Mapped[str | None] = mapped_column(Text)

    categoria = relationship("CategoriaGasto", lazy="joined")
    proveedor = relationship("Proveedor")
    usuario = relationship("Usuario")

    @property
    def es_automatico(self):
        return self.origen != "manual"
