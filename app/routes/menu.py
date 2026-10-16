"""Menú lateral: se arma según los permisos de cada rol."""
from flask import url_for

from ..utils.permisos import puede


def _m(key, **kw):
    return url_for("crud.listar", key=key, **kw)


def menu_para(usuario):
    rol = usuario.rol_codigo
    if rol == "superadmin":
        return [("Administración", [("Empresas", "empresa", url_for("admin.empresas"), True)])]
    if rol == "trabajador":
        return [("Mi trabajo", [
            ("Mi panel", "inicio", url_for("trabajador.panel"), True),
            ("Calendario", "calendario", url_for("calendario.index"), True),
        ])]
    grupos = [
        ("Inicio", [
            ("Dashboard", "inicio", url_for("dashboard.index"), puede("dashboard")),
            ("Alertas", "alerta", url_for("alertas.index"), True),
            ("Calendario", "calendario", url_for("calendario.index"), puede("calendario")),
        ]),
        ("Campo", [
            ("Mapa", "mapa", url_for("mapa.index"), puede("lotes")),
            ("Fincas", "finca", _m("fincas"), puede("fincas")),
            ("Lotes", "lotes", _m("lotes"), puede("lotes")),
            ("Campañas", "campana", _m("campanas"), puede("campanas")),
            ("Cultivos", "cultivo", _m("cultivos"), puede("cultivos")),
            ("Siembras", "siembra", _m("siembras"), puede("siembras")),
            ("Actividades", "actividad", _m("actividades"), puede("actividades")),
            ("Riego", "riego", _m("riegos"), puede("riegos")),
            ("Cosechas", "cosecha", _m("cosechas"), puede("cosechas")),
        ]),
        ("Insumos", [
            ("Insumos y stock", "insumo", url_for("inventario.stock"), puede("inventario")),
            ("Fertilizantes", "fertilizante", _m("aplicaciones_fertilizantes"), puede("aplicaciones_fertilizantes")),
            ("Agroquímicos", "agroquimico", _m("aplicaciones_agroquimicos"), puede("aplicaciones_agroquimicos")),
            ("Compras", "compra", url_for("compras.listar"), puede("compras")),
        ]),
        ("Maquinaria", [
            ("Maquinaria", "tractor", _m("maquinaria"), puede("maquinaria")),
            ("Uso de maquinaria", "horas", _m("uso_maquinaria"), puede("uso_maquinaria")),
            ("Combustible", "combustible", _m("combustibles"), puede("combustibles")),
        ]),
        ("Personal", [
            ("Empleados", "personas", _m("empleados"), puede("empleados")),
            ("Trabajos", "trabajo", _m("trabajos"), puede("trabajos")),
            ("Pagos", "pago", _m("pagos_empleados"), puede("pagos_empleados")),
        ]),
        ("Comercial", [
            ("Ventas", "venta", url_for("ventas.listar"), puede("ventas")),
            ("Cobros e ingresos", "ingreso", _m("ingresos"), puede("ingresos")),
            ("Clientes", "cliente", _m("clientes"), puede("clientes")),
        ]),
        ("Finanzas", [
            ("Caja / Finanzas", "caja", url_for("finanzas.index"), puede("finanzas")),
            ("Gastos", "gasto", _m("gastos"), puede("gastos")),
            ("Cuentas a pagar", "factura", _m("cuentas_pagar"), puede("cuentas_pagar")),
            ("Proveedores", "proveedor", _m("proveedores"), puede("proveedores")),
            ("Rentabilidad", "rentabilidad", url_for("rentabilidad.index"), puede("rentabilidad")),
        ]),
        ("Análisis", [
            ("Reportes", "reporte", url_for("reportes.index"), puede("reportes")),
            ("Documentos", "documento", url_for("documentos.listar"), puede("documentos")),
            ("Tareas", "tarea", _m("alertas"), puede("alertas")),
        ]),
        ("Sistema", [
            ("Configuración", "config", url_for("configuracion.index"), True),
        ]),
    ]
    salida = []
    for titulo, items in grupos:
        visibles = [i for i in items if i[3]]
        if visibles:
            salida.append((titulo, visibles))
    return salida


ACCESOS_RAPIDOS = [
    ("Gasto", "gasto", "gastos"),
    ("Trabajo", "trabajo", "trabajos"),
    ("Siembra", "siembra", "siembras"),
    ("Aplicación", "fertilizante", "aplicaciones_fertilizantes"),
    ("Cosecha", "cosecha", "cosechas"),
    ("Combustible", "combustible", "combustibles"),
]
