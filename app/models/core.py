"""Empresas, usuarios, roles, auditoría, alertas y documentos."""
import secrets
from datetime import date, datetime

from flask_login import UserMixin
from sqlalchemy import (Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, String, Table, Text,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db
from .base import EmpresaMixin, TimestampMixin


class Empresa(TimestampMixin, db.Model):
    """Cada explotación agrícola que usa el sistema (La Mesada es la primera)."""

    __tablename__ = "empresas"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    cuit: Mapped[str | None] = mapped_column(String(13))
    telefono: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(120))
    direccion: Mapped[str | None] = mapped_column(String(150))
    localidad: Mapped[str | None] = mapped_column(String(80))
    logo: Mapped[str | None] = mapped_column(String(255))
    datos_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    activa: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __str__(self):
        return self.nombre


class Rol(db.Model):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    nombre: Mapped[str] = mapped_column(String(50), nullable=False)

    def __str__(self):
        return self.nombre


usuario_fincas = Table(
    "usuario_fincas",
    db.metadata,
    Column("usuario_id", Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True),
    Column("finca_id", Integer, ForeignKey("fincas.id", ondelete="CASCADE"), primary_key=True),
)


class Usuario(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresas.id"), index=True)
    rol_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ultimo_acceso: Mapped[datetime | None] = mapped_column(DateTime)
    intentos_fallidos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(DateTime)
    token_sesion: Mapped[str] = mapped_column(String(32), nullable=False, default=lambda: secrets.token_hex(16))

    rol = relationship("Rol", lazy="joined")
    empresa = relationship("Empresa", lazy="joined")
    fincas = relationship("Finca", secondary=usuario_fincas, lazy="selectin", order_by="Finca.nombre")

    def set_password(self, clave):
        self.password_hash = generate_password_hash(clave)
        self.token_sesion = secrets.token_hex(16)  # cierra otras sesiones abiertas

    def check_password(self, clave):
        return check_password_hash(self.password_hash, clave)

    def get_id(self):
        return f"{self.id}:{self.token_sesion}"

    @property
    def is_active(self):
        return self.activo and (self.empresa is None or self.empresa.activa)

    @property
    def rol_codigo(self):
        return self.rol.codigo if self.rol else None

    def __str__(self):
        return self.nombre


class HistorialActividad(db.Model):
    __tablename__ = "historial_actividades"
    __table_args__ = (Index("ix_historial_empresa_fecha", "empresa_id", "fecha_hora"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresas.id"))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), index=True)
    fecha_hora: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    modulo: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    accion: Mapped[str] = mapped_column(String(20), nullable=False)
    registro_id: Mapped[int | None] = mapped_column(Integer)
    descripcion: Mapped[str] = mapped_column(String(255), nullable=False)
    ip: Mapped[str | None] = mapped_column(String(45))

    usuario = relationship("Usuario")


class Alerta(EmpresaMixin, TimestampMixin, db.Model):
    """Tareas y recordatorios cargados a mano (las alertas automáticas se calculan)."""

    __tablename__ = "alertas"
    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(150), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, default="tarea")
    prioridad: Mapped[str] = mapped_column(String(10), nullable=False, default="media")
    fecha: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    finca_id: Mapped[int | None] = mapped_column(ForeignKey("fincas.id"), index=True)
    asignado_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    estado: Mapped[str] = mapped_column(String(12), nullable=False, default="pendiente")
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))

    finca = relationship("Finca")
    asignado = relationship("Usuario", foreign_keys=[asignado_id])


class Documento(EmpresaMixin, TimestampMixin, db.Model):
    __tablename__ = "documentos"
    __table_args__ = (Index("ix_documentos_entidad", "empresa_id", "entidad", "entidad_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    entidad: Mapped[str] = mapped_column(String(20), nullable=False)
    entidad_id: Mapped[int | None] = mapped_column(Integer)
    tipo_documento: Mapped[str] = mapped_column(String(30), nullable=False)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    archivo: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    nombre_original: Mapped[str] = mapped_column(String(255), nullable=False)
    mime: Mapped[str | None] = mapped_column(String(100))
    tamanio: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_vencimiento: Mapped[date | None] = mapped_column(Date, index=True)
    finca_id: Mapped[int | None] = mapped_column(ForeignKey("fincas.id"))
    observaciones: Mapped[str | None] = mapped_column(Text)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))

    usuario = relationship("Usuario")
    finca = relationship("Finca")
