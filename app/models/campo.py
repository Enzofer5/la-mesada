"""Estructura productiva: fincas, lotes, campañas, cultivos, unidades, siembras, actividades, riego, cosechas."""
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, Text, UniqueConstraint, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import Cantidad, Dinero, EmpresaMixin, Hectareas, ImputacionMixin, TimestampMixin


class UnidadMedida(EmpresaMixin, db.Model):
    """Unidades configurables. factor_base convierte a la unidad base de su tipo (kg para masa, litro para volumen)."""

    __tablename__ = "unidades_medida"
    __table_args__ = (UniqueConstraint("empresa_id", "nombre", name="uq_unidad_empresa_nombre"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(40), nullable=False)
    abreviatura: Mapped[str] = mapped_column(String(12), nullable=False)
    tipo: Mapped[str] = mapped_column(String(10), nullable=False, default="masa")
    factor_base: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=1)
    activa: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __str__(self):
        return self.abreviatura


class Finca(EmpresaMixin, TimestampMixin, db.Model):
    __tablename__ = "fincas"
    __table_args__ = (UniqueConstraint("empresa_id", "nombre", name="uq_finca_empresa_nombre"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)
    ubicacion: Mapped[str | None] = mapped_column(String(150))
    superficie_total: Mapped[Decimal] = mapped_column(Hectareas, nullable=False, default=0)
    superficie_cultivable: Mapped[Decimal] = mapped_column(Hectareas, nullable=False, default=0)
    tipo_suelo: Mapped[str | None] = mapped_column(String(60))
    observaciones: Mapped[str | None] = mapped_column(Text)
    responsable_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    estado: Mapped[str] = mapped_column(String(12), nullable=False, default="activa")

    responsable = relationship("Usuario", foreign_keys=[responsable_id])
    lotes = relationship("Lote", back_populates="finca", order_by="Lote.nombre")

    def __str__(self):
        return self.nombre


class Lote(EmpresaMixin, TimestampMixin, db.Model):
    __tablename__ = "lotes"
    __table_args__ = (UniqueConstraint("finca_id", "nombre", name="uq_lote_finca_nombre"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    finca_id: Mapped[int] = mapped_column(ForeignKey("fincas.id"), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(60), nullable=False)
    superficie: Mapped[Decimal] = mapped_column(Hectareas, nullable=False, default=0)
    tipo_suelo: Mapped[str | None] = mapped_column(String(60))
    observaciones: Mapped[str | None] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(String(12), nullable=False, default="activo")
    # Mapa: forma dibujada (circulo = pivote, rectangulo, poligono) y su geometría GeoJSON
    forma: Mapped[str | None] = mapped_column(String(12))
    geometria: Mapped[str | None] = mapped_column(Text)

    finca = relationship("Finca", back_populates="lotes")

    def __str__(self):
        return f"{self.nombre}"


class CaminoLote(EmpresaMixin, TimestampMixin, db.Model):
    """Camino interno de un lote (se descuenta de la superficie sembrable)."""

    __tablename__ = "caminos_lote"
    id: Mapped[int] = mapped_column(primary_key=True)
    lote_id: Mapped[int] = mapped_column(ForeignKey("lotes.id", ondelete="CASCADE"), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(60), nullable=False, default="Camino")
    ancho: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)  # metros
    longitud: Mapped[Decimal] = mapped_column(Numeric(10, 1), nullable=False, default=0)  # metros
    geometria: Mapped[str] = mapped_column(Text, nullable=False)  # GeoJSON LineString

    lote = relationship("Lote", backref="caminos")

    @property
    def superficie(self):
        return (self.longitud or 0) * (self.ancho or 0) / 10000


class Campana(EmpresaMixin, TimestampMixin, db.Model):
    __tablename__ = "campanas"
    __table_args__ = (UniqueConstraint("empresa_id", "nombre", name="uq_campana_empresa_nombre"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(40), nullable=False)
    fecha_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_fin: Mapped[date] = mapped_column(Date, nullable=False)
    estado: Mapped[str] = mapped_column(String(12), nullable=False, default="activa")
    observaciones: Mapped[str | None] = mapped_column(Text)

    def __str__(self):
        return self.nombre


class Cultivo(EmpresaMixin, TimestampMixin, db.Model):
    __tablename__ = "cultivos"
    __table_args__ = (UniqueConstraint("empresa_id", "nombre", name="uq_cultivo_empresa_nombre"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(60), nullable=False)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False, default="hortaliza")
    unidad_id: Mapped[int] = mapped_column(ForeignKey("unidades_medida.id"), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str | None] = mapped_column(String(7))
    estado: Mapped[str] = mapped_column(String(12), nullable=False, default="activo")

    unidad = relationship("UnidadMedida", lazy="joined")

    def __str__(self):
        return self.nombre


class Siembra(EmpresaMixin, ImputacionMixin, TimestampMixin, db.Model):
    __tablename__ = "siembras"
    _finca_obligatoria = True
    _campana_obligatoria = True
    _cultivo_obligatorio = True
    id: Mapped[int] = mapped_column(primary_key=True)
    fecha_siembra: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    superficie: Mapped[Decimal] = mapped_column(Hectareas, nullable=False)
    variedad: Mapped[str | None] = mapped_column(String(60))
    insumo_id: Mapped[int | None] = mapped_column(ForeignKey("insumos.id"))
    cantidad_semilla: Mapped[Decimal | None] = mapped_column(Cantidad)
    unidad_semilla_id: Mapped[int | None] = mapped_column(ForeignKey("unidades_medida.id"))
    proveedor_id: Mapped[int | None] = mapped_column(ForeignKey("proveedores.id"))
    costo_semilla: Mapped[Decimal] = mapped_column(Dinero, nullable=False, default=0)
    responsable_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    fecha_cosecha_estimada: Mapped[date | None] = mapped_column(Date, index=True)
    rendimiento_estimado: Mapped[Decimal | None] = mapped_column(Cantidad)
    estado: Mapped[str] = mapped_column(String(12), nullable=False, default="en_curso", index=True)
    observaciones: Mapped[str | None] = mapped_column(Text)
    # Sector del lote donde se sembró (ej. una franja del pivote), en GeoJSON. Vacío = todo el lote.
    geometria: Mapped[str | None] = mapped_column(Text)
    distancia_surcos: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))  # metros entre surcos (ej. 0,75)
    orientacion_surcos: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))  # grados desde el norte
    superficie_caminos: Mapped[Decimal | None] = mapped_column(Hectareas)  # ha ocupadas por caminos (descontadas)
    # "propia" = semilla guardada de cosechas propias (sin costo) · "comprada" = con precio (inventario o compra directa)
    origen_semilla: Mapped[str | None] = mapped_column(String(10))

    insumo = relationship("Insumo")
    unidad_semilla = relationship("UnidadMedida")
    proveedor = relationship("Proveedor")
    responsable = relationship("Usuario")

    def __str__(self):
        return f"{self.cultivo} · {self.finca} {('· ' + self.lote.nombre) if self.lote else ''} · {self.fecha_siembra:%d/%m/%Y}"

    @property
    def produccion_estimada(self):
        if self.rendimiento_estimado:
            return self.rendimiento_estimado * self.superficie
        return None


class ActividadCultivo(EmpresaMixin, ImputacionMixin, TimestampMixin, db.Model):
    """Etapas del cultivo: preparación, fertilización, control de malezas, mantenimiento, etc."""

    __tablename__ = "actividades_cultivo"
    _finca_obligatoria = True
    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    estado: Mapped[str] = mapped_column(String(12), nullable=False, default="realizada")
    descripcion: Mapped[str | None] = mapped_column(String(200))
    responsable_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    costo: Mapped[Decimal] = mapped_column(Dinero, nullable=False, default=0)
    categoria_gasto_id: Mapped[int | None] = mapped_column(ForeignKey("categorias_gasto.id"))
    observaciones: Mapped[str | None] = mapped_column(Text)

    responsable = relationship("Usuario")
    categoria_gasto = relationship("CategoriaGasto")


class Riego(EmpresaMixin, ImputacionMixin, TimestampMixin, db.Model):
    __tablename__ = "riegos"
    _finca_obligatoria = True
    id: Mapped[int] = mapped_column(primary_key=True)
    fecha: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    horas: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=0)
    sistema: Mapped[str] = mapped_column(String(20), nullable=False)
    consumo: Mapped[Decimal | None] = mapped_column(Cantidad)
    unidad_consumo: Mapped[str | None] = mapped_column(String(15))
    costo: Mapped[Decimal] = mapped_column(Dinero, nullable=False, default=0)
    responsable_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    observaciones: Mapped[str | None] = mapped_column(Text)

    responsable = relationship("Usuario")


class Cosecha(EmpresaMixin, ImputacionMixin, TimestampMixin, db.Model):
    __tablename__ = "cosechas"
    _finca_obligatoria = True
    _campana_obligatoria = True
    _cultivo_obligatorio = True
    id: Mapped[int] = mapped_column(primary_key=True)
    siembra_id: Mapped[int | None] = mapped_column(ForeignKey("siembras.id"), index=True)
    fecha: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    superficie: Mapped[Decimal] = mapped_column(Hectareas, nullable=False, default=0)
    cantidad: Mapped[Decimal] = mapped_column(Cantidad, nullable=False)
    unidad_id: Mapped[int] = mapped_column(ForeignKey("unidades_medida.id"), nullable=False)
    calidad: Mapped[str | None] = mapped_column(String(20))
    merma: Mapped[Decimal] = mapped_column(Cantidad, nullable=False, default=0)
    # Parte de la cosecha que se guarda como semilla propia (en la unidad del cultivo): entra al stock de la semilla
    # propia elegida (sin costo) y no cuenta como comercializable.
    semilla_guardada: Mapped[Decimal | None] = mapped_column(Cantidad, default=0)
    insumo_semilla_id: Mapped[int | None] = mapped_column(ForeignKey("insumos.id"))
    responsable_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    observaciones: Mapped[str | None] = mapped_column(Text)

    siembra = relationship("Siembra")
    unidad = relationship("UnidadMedida")
    responsable = relationship("Usuario")
    insumo_semilla = relationship("Insumo")

    @property
    def comercializable(self):
        return (self.cantidad or 0) - (self.merma or 0) - (self.semilla_guardada or 0)

    @property
    def rendimiento(self):
        if self.superficie and self.superficie > 0:
            return (self.cantidad or 0) / self.superficie
        return None
