"""Modelos de datos. Se importan todos aquí para que SQLAlchemy registre las tablas."""
from .base import dec  # noqa: F401
from .core import Alerta, Documento, Empresa, HistorialActividad, Rol, Usuario, usuario_fincas  # noqa: F401
from .campo import (ActividadCultivo, Campana, CaminoLote, Cosecha, Cultivo, Finca, Lote, Riego, Siembra,  # noqa: F401
                    UnidadMedida)
from .insumos import (CATEGORIAS_INSUMO, AplicacionAgroquimico, AplicacionFertilizante, Insumo,  # noqa: F401
                      Inventario, MovimientoInventario)
from .maquinaria import CargaCombustible, Maquina, UsoMaquinaria  # noqa: F401
from .personal import MODALIDADES_PAGO, TIPOS_EMPLEADO, Empleado, PagoEmpleado, Trabajo  # noqa: F401
from .comercial import Cliente, DetalleVenta, Ingreso, Venta  # noqa: F401
from .compras import Compra, CuentaPagar, DetalleCompra, PagoProveedor, Proveedor  # noqa: F401
from .finanzas import CATEGORIAS_BASE, METODOS_PAGO, CategoriaGasto, Gasto  # noqa: F401
