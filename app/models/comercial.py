"""Clientes, ventas, detalle de ventas e ingresos (cobros)."""
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import Cantidad, Dinero, EmpresaMixin, ImputacionMixin, TimestampMixin


class Cliente(EmpresaMixin, TimestampMixin, db.Model):
    __tablename__ = "clientes"
    __table_args__ = (UniqueConstraint("empresa_id", "cuit", name="uq_cliente_empresa_cuit"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    cuit: Mapped[str | None] = mapped_column(String(13))
    dni: Mapped[str | None] = mapped_column(String(15))
    telefono: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(120))
    direccion: Mapped[str | None] = mapped_column(String(150))
    localidad: Mapped[str | None] = mapped_column(String(80))
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, default="mayorista")
    estado: Mapped[str] = mapped_column(String(12), nullable=False, default="activo")
    observaciones: Mapped[str | None] = mapped_column(Text)

    def __str__(self):
        return self.nombre


class Venta(EmpresaMixin, TimestampMixin, db.Model):
    __tablename__ = "ventas"
    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"), nullable=False, index=True)
    fecha: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    finca_id: Mapped[int] = mapped_column(ForeignKey("fincas.id"), nullable=False, index=True)
    campana_id: Mapped[int | None] = mapped_column(ForeignKey("campanas.id"), index=True)
    forma_pago: Mapped[str] = mapped_column(String(20), nullable=False, default="contado")
    fecha_vencimiento_cobro: Mapped[date | None] = mapped_column(Date, index=True)
    comprobante: Mapped[str | None] = mapped_column(String(40))
    transporte: Mapped[str | None] = mapped_column(String(120))
    costo_flete: Mapped[Decimal] = mapped_column(Dinero, nullable=False, default=0)
    flete_a_cargo: Mapped[str] = mapped_column(String(12), nullable=False, default="comprador")
    total: Mapped[Decimal] = mapped_column(Dinero, nullable=False, default=0)
    observaciones: Mapped[str | None] = mapped_column(Text)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))

    cliente = relationship("Cliente", lazy="joined")
    finca = relationship("Finca", lazy="joined")
    campana = relationship("Campana")
    usuario = relationship("Usuario")
    detalles = relationship("DetalleVenta", back_populates="venta", cascade="all, delete-orphan",
                            order_by="DetalleVenta.id")
    ingresos = relationship("Ingreso", back_populates="venta", order_by="Ingreso.fecha")

    @property
    def cobrado(self):
        return sum((i.monto for i in self.ingresos if i.estado != "rechazado"), Decimal("0"))

    @property
    def saldo(self):
        return (self.total or Decimal("0")) - self.cobrado

    @property
    def estado_pago(self):
        cobrado = self.cobrado
        if cobrado <= 0:
            return "pendiente"
        if cobrado < (self.total or 0):
            return "parcial"
        return "cobrada"

    def __str__(self):
        return f"Venta #{self.id} · {self.cliente} · {self.fecha:%d/%m/%Y}"


class DetalleVenta(EmpresaMixin, db.Model):
    __tablename__ = "detalle_ventas"
    id: Mapped[int] = mapped_column(primary_key=True)
    venta_id: Mapped[int] = mapped_column(ForeignKey("ventas.id", ondelete="CASCADE"), nullable=False, index=True)
    cultivo_id: Mapped[int] = mapped_column(ForeignKey("cultivos.id"), nullable=False, index=True)
    lote_id: Mapped[int | None] = mapped_column(ForeignKey("lotes.id"))
    calidad: Mapped[str | None] = mapped_column(String(20))
    cantidad: Mapped[Decimal] = mapped_column(Cantidad, nullable=False)
    unidad_id: Mapped[int] = mapped_column(ForeignKey("unidades_medida.id"), nullable=False)
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Dinero, nullable=False)

    venta = relationship("Venta", back_populates="detalles")
    cultivo = relationship("Cultivo", lazy="joined")
    lote = relationship("Lote")
    unidad = relationship("UnidadMedida", lazy="joined")


class Ingreso(EmpresaMixin, ImputacionMixin, TimestampMixin, db.Model):
    """Cobros de ventas y otros ingresos."""

    __tablename__ = "ingresos"
    id: Mapped[int] = mapped_column(primary_key=True)
    venta_id: Mapped[int | None] = mapped_column(ForeignKey("ventas.id"), index=True)
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("clientes.id"), index=True)
    fecha: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    concepto: Mapped[str] = mapped_column(String(120), nullable=False)
    monto: Mapped[Decimal] = mapped_column(Dinero, nullable=False)
    metodo_pago: Mapped[str] = mapped_column(String(20), nullable=False, default="efectivo")
    estado: Mapped[str] = mapped_column(String(12), nullable=False, default="acreditado")
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    observaciones: Mapped[str | None] = mapped_column(Text)

    venta = relationship("Venta", back_populates="ingresos")
    cliente = relationship("Cliente")
