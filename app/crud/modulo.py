"""Clase Modulo: describe un ABM completo (campos, columnas, filtros, permisos y reglas de negocio)."""

REGISTRO = {}


class Modulo:
    def __init__(self, key, titulo, singular, modelo, campos, columnas, *, permiso=None, icono="list",
                 genero="o", filtros=(), buscar_en=(), orden=None, finca_attr="finca_id", buscar_primero=False,
                 totales=(), guardar=None, eliminar=None, validar=None, editable=None, descripcion=None,
                 detalle_extra=None, enlaces=None, filtro_fijo=(), estados=None, tipos=None, tipo_attr="tipo",
                 campo_fecha="fecha", usuario_attr=None, ayuda=None, origen_gasto=None, entidad_documento=None,
                 puede_crear=True, detalle_url=None, acciones_detalle=None, filtros_custom=None, preparar=None):
        self.key = key
        self.titulo = titulo
        self.singular = singular
        self.modelo = modelo
        self.campos = campos
        self.columnas = columnas
        self.permiso = permiso or key
        self.icono = icono
        self.genero = genero  # "o" → Nuevo, "a" → Nueva
        self.filtros = list(filtros)
        self.buscar_en = list(buscar_en)
        self.orden = orden
        self.finca_attr = finca_attr
        self.buscar_primero = buscar_primero
        self.totales = list(totales)
        self.guardar = guardar
        self.eliminar = eliminar
        self.validar = validar
        self.editable = editable
        self.descripcion = descripcion
        self.detalle_extra = detalle_extra
        self.enlaces = enlaces or []
        self.filtro_fijo = list(filtro_fijo)
        self.estados = estados
        self.tipos = tipos
        self.tipo_attr = tipo_attr
        self.campo_fecha = campo_fecha
        self.usuario_attr = usuario_attr
        self.ayuda = ayuda
        self.origen_gasto = origen_gasto
        self.entidad_documento = entidad_documento
        self.puede_crear = puede_crear
        self.detalle_url = detalle_url  # función(obj) → url si el detalle es una pantalla propia
        self.acciones_detalle = acciones_detalle  # función(obj) → [(texto, url, clase)]
        # filtros especiales: [{'nombre','etiqueta','opciones','aplicar': f(stmt, valor)}]
        self.filtros_custom = filtros_custom or []
        self.preparar = preparar  # función(obj) antes de grabar (completa columnas obligatorias calculadas)
        REGISTRO[key] = self

    @property
    def nuevo_texto(self):
        return f"Nuev{self.genero} {self.singular.lower()}"

    def campo(self, nombre):
        for c in self.campos:
            if c.nombre == nombre:
                return c
        return None

    def describir(self, obj):
        if self.descripcion:
            try:
                return self.descripcion(obj)
            except Exception:  # la descripción nunca debe romper un guardado
                pass
        return str(obj) if type(obj).__str__ is not object.__str__ else f"#{obj.id}"
