"""Empleados, trabajos (mano de obra) y pagos a empleados."""
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import Cantidad, Dinero, EmpresaMixin, ImputacionMixin, TimestampMixin

TIPOS_EMPLEADO = [
    ("cargador", "Cargador"),
    ("tractorista", "Tractorista"),
    ("peon", "Peón"),
    ("encargado", "Encargado"),
    ("cosechador", "Cosechador"),
    ("administrativo", "Administrativo"),
    ("otro", "Otro"),
]

MODALIDADES_PAGO = [
    ("jornal", "Por jornal"),
    ("hora", "Por hora"),
    ("unidad", "Por unidad / destajo"),
    ("monto_fijo", "Monto fijo"),
]


class Empleado(EmpresaMixin, TimestampMixin, db.Model):
    __tablename__ = "empleados"
    __table_args__ = (UniqueConstraint("empresa_id", "dni", name="uq_empleado_empresa_dni"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(60), nullable=False)
    apellido: Mapped[str] = mapped_column(String(60), nullable=False)
    dni: Mapped[str | None] = mapped_column(String(15))
    telefono: Mapped[str | None] = mapped_column(String(30))
    puesto: Mapped[str | None] = mapped_column(String(60))
    fecha_ingreso: Mapped[date | None] = mapped_column(Date)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    estado: Mapped[str] = mapped_column(String(12), nullable=False, default="activo")
    finca_id: Mapped[int | None] = mapped_column(ForeignKey("fincas.id"), index=True)
    modalidad_pago: Mapped[str | None] = mapped_column(String(15))
    tarifa: Mapped[Decimal | None] = mapped_column(Dinero)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), unique=True)
    observaciones: Mapped[str | None] = mapped_column(Text)

    finca = relationship("Finca")
    usuario = relationship("Usuario")

    @property
    def nombre_completo(self):
        return f"{self.apellido}, {self.nombre}"

    def __str__(self):
        return self.nombre_completo


class Trabajo(EmpresaMixin, ImputacionMixin, TimestampMixin, db.Model):
    """Mano de obra devengada (genera el costo de mano de obra)."""

    __tablename__ = "trabajos"
    _finca_obligatoria = True
    id: Mapped[int] = mapped_column(primary_key=True)
    fecha: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    empleado_id: Mapped[int] = mapped_column(ForeignKey("empleados.id"), nullable=False, index=True)
    tipo_trabajo: Mapped[str] = mapped_column(String(40), nullable=False)
    modalidad: Mapped[str] = mapped_column(String(15), nullable=False, default="jornal")
    horas: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    jornales: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    cantidad: Mapped[Decimal | None] = mapped_column(Cantidad)
    precio_unitario: Mapped[Decimal] = mapped_column(Dinero, nullable=False, default=0)
    total: Mapped[Decimal] = mapped_column(Dinero, nullable=False, default=0)
    observaciones: Mapped[str | None] = mapped_column(Text)

    empleado = relationship("Empleado", lazy="joined")


class PagoEmpleado(EmpresaMixin, ImputacionMixin, TimestampMixin, db.Model):
    __tablename__ = "pagos_empleados"
    id: Mapped[int] = mapped_column(primary_key=True)
    empleado_id: Mapped[int] = mapped_column(ForeignKey("empleados.id"), nullable=False, index=True)
    fecha: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    concepto: Mapped[str] = mapped_column(String(100), nullable=False)
    periodo: Mapped[str | None] = mapped_column(String(20))
    monto: Mapped[Decimal] = mapped_column(Dinero, nullable=False)
    metodo_pago: Mapped[str] = mapped_column(String(20), nullable=False, default="efectivo")
    imputar_costo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    observaciones: Mapped[str | None] = mapped_column(Text)

    empleado = relationship("Empleado", lazy="joined")
