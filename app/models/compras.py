"""Proveedores, compras, cuentas a pagar y pagos a proveedores."""
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import Cantidad, Dinero, EmpresaMixin, TimestampMixin


class Proveedor(EmpresaMixin, TimestampMixin, db.Model):
    __tablename__ = "proveedores"
    __table_args__ = (UniqueConstraint("empresa_id", "cuit", name="uq_proveedor_empresa_cuit"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    razon_social: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    cuit: Mapped[str | None] = mapped_column(String(13))
    telefono: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(120))
    direccion: Mapped[str | None] = mapped_column(String(150))
    contacto: Mapped[str | None] = mapped_column(String(80))
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, default="otro")
    estado: Mapped[str] = mapped_column(String(12), nullable=False, default="activo")
    observaciones: Mapped[str | None] = mapped_column(Text)

    def __str__(self):
        return self.razon_social


class Compra(EmpresaMixin, TimestampMixin, db.Model):
    __tablename__ = "compras"
    id: Mapped[int] = mapped_column(primary_key=True)
    proveedor_id: Mapped[int] = mapped_column(ForeignKey("proveedores.id"), nullable=False, index=True)
    fecha: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    comprobante: Mapped[str | None] = mapped_column(String(40))
    finca_id: Mapped[int | None] = mapped_column(ForeignKey("fincas.id"), index=True)
    condicion: Mapped[str] = mapped_column(String(20), nullable=False, default="contado")
    vencimiento: Mapped[date | None] = mapped_column(Date)
    total: Mapped[Decimal] = mapped_column(Dinero, nullable=False, default=0)
    observaciones: Mapped[str | None] = mapped_column(Text)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))

    proveedor = relationship("Proveedor", lazy="joined")
    finca = relationship("Finca")
    usuario = relationship("Usuario")
    detalles = relationship("DetalleCompra", back_populates="compra", cascade="all, delete-orphan",
                            order_by="DetalleCompra.id")

    def __str__(self):
        return f"Compra #{self.id} · {self.proveedor} · {self.fecha:%d/%m/%Y}"


class DetalleCompra(EmpresaMixin, db.Model):
    __tablename__ = "detalle_compras"
    id: Mapped[int] = mapped_column(primary_key=True)
    compra_id: Mapped[int] = mapped_column(ForeignKey("compras.id", ondelete="CASCADE"), nullable=False, index=True)
    insumo_id: Mapped[int] = mapped_column(ForeignKey("insumos.id"), nullable=False, index=True)
    cantidad: Mapped[Decimal] = mapped_column(Cantidad, nullable=False)
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Dinero, nullable=False)

    compra = relationship("Compra", back_populates="detalles")
    insumo = relationship("Insumo", lazy="joined")


class CuentaPagar(EmpresaMixin, TimestampMixin, db.Model):
    __tablename__ = "cuentas_pagar"
    __table_args__ = (Index("ix_cuenta_origen", "origen", "origen_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    proveedor_id: Mapped[int] = mapped_column(ForeignKey("proveedores.id"), nullable=False, index=True)
    comprobante: Mapped[str | None] = mapped_column(String(40))
    descripcion: Mapped[str | None] = mapped_column(String(200))
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    vencimiento: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    importe: Mapped[Decimal] = mapped_column(Dinero, nullable=False)
    pagado: Mapped[Decimal] = mapped_column(Dinero, nullable=False, default=0)
    finca_id: Mapped[int | None] = mapped_column(ForeignKey("fincas.id"))
    origen: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")
    origen_id: Mapped[int | None] = mapped_column(Integer)
    observaciones: Mapped[str | None] = mapped_column(Text)

    proveedor = relationship("Proveedor", lazy="joined")
    finca = relationship("Finca")
    pagos = relationship("PagoProveedor", back_populates="cuenta", order_by="PagoProveedor.fecha")

    @property
    def pendiente(self):
        return (self.importe or Decimal("0")) - (self.pagado or Decimal("0"))

    @property
    def estado(self):
        if self.pendiente <= 0:
            return "pagado"
        if self.vencimiento and self.vencimiento < date.today():
            return "vencido"
        if (self.pagado or 0) > 0:
            return "parcial"
        return "pendiente"

    def __str__(self):
        return f"{self.proveedor} · {self.comprobante or 'sin comprobante'}"


class PagoProveedor(EmpresaMixin, TimestampMixin, db.Model):
    __tablename__ = "pagos_proveedores"
    id: Mapped[int] = mapped_column(primary_key=True)
    cuenta_id: Mapped[int] = mapped_column(ForeignKey("cuentas_pagar.id"), nullable=False, index=True)
    fecha: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    monto: Mapped[Decimal] = mapped_column(Dinero, nullable=False)
    metodo_pago: Mapped[str] = mapped_column(String(20), nullable=False, default="transferencia")
    observaciones: Mapped[str | None] = mapped_column(Text)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))

    cuenta = relationship("CuentaPagar", back_populates="pagos")
