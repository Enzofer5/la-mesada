"""Alta de empresas y carga de datos iniciales / de demostración.

IMPORTANTE: todos los valores económicos de la demostración son FICTICIOS. Las observaciones llevan la marca
[DEMO] y la empresa queda marcada con datos_demo=True (la aplicación muestra un aviso).
"""
import math
import re
import unicodedata
from datetime import date, timedelta
from decimal import Decimal as D

from sqlalchemy import select

from ..extensions import db
from ..models import (ActividadCultivo, AplicacionAgroquimico, AplicacionFertilizante, Alerta, Campana, CaminoLote,
                      CargaCombustible, Cliente, Compra, Cosecha, CuentaPagar, Cultivo, Empleado, Empresa, Finca,
                      Ingreso, Insumo, Lote, Maquina, PagoEmpleado, Proveedor, Riego, Rol, Siembra, Trabajo,
                      UnidadMedida, UsoMaquinaria, Usuario, Venta, Gasto)
from ..utils.permisos import ROLES
from . import compras as svc_compras
from . import geo
from . import cuentas as svc_cuentas
from . import gastos_auto
from . import operaciones as op
from . import ventas as svc_ventas
from .tenant import usar_empresa

DEMO = "[DEMO] Dato ficticio de demostración."

UNIDADES_BASE = [
    ("Kilogramo", "kg", "masa", D("1")),
    ("Tonelada", "t", "masa", D("1000")),
    ("Quintal", "qq", "masa", D("100")),
    ("Bolsa 25 kg", "bolsa25", "masa", D("25")),
    ("Bolsa 50 kg", "bolsa50", "masa", D("50")),
    ("Cajón 20 kg", "cajón", "masa", D("20")),
    ("Litro", "l", "volumen", D("1")),
    ("Unidad", "u", "unidad", D("1")),
]


def crear_roles():
    existentes = set(db.session.scalars(select(Rol.codigo)).all())
    for codigo, nombre in ROLES:
        if codigo not in existentes:
            db.session.add(Rol(codigo=codigo, nombre=nombre))
    db.session.flush()


def rol(codigo):
    return db.session.scalar(select(Rol).where(Rol.codigo == codigo))


def slugify(texto):
    base = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", base).strip("-")[:50] or "empresa"


def crear_superadmin(email, clave, nombre="Administrador del sistema"):
    crear_roles()
    usuario = db.session.scalar(select(Usuario).where(Usuario.email == email.lower()))
    if usuario is None:
        usuario = Usuario(nombre=nombre, email=email.lower(), rol_id=rol("superadmin").id, empresa_id=None)
        db.session.add(usuario)
    usuario.set_password(clave)
    db.session.flush()
    return usuario


def crear_empresa(nombre, propietario_nombre, propietario_email, clave, logo=None, demo=False, **datos):
    """Crea una empresa lista para usar: categorías de gasto, unidades y su usuario propietario."""
    crear_roles()
    slug = slugify(nombre)
    base, n = slug, 2
    while db.session.scalar(select(Empresa).where(Empresa.slug == slug)):
        slug = f"{base}-{n}"
        n += 1
    empresa = Empresa(nombre=nombre, slug=slug, logo=logo, datos_demo=demo, **datos)
    db.session.add(empresa)
    db.session.flush()
    usar_empresa(empresa.id)
    gastos_auto.crear_categorias_base(empresa.id)
    for nombre_u, abrev, tipo, factor in UNIDADES_BASE:
        db.session.add(UnidadMedida(empresa_id=empresa.id, nombre=nombre_u, abreviatura=abrev, tipo=tipo,
                                    factor_base=factor))
    propietario = Usuario(empresa_id=empresa.id, rol_id=rol("propietario").id, nombre=propietario_nombre,
                          email=propietario_email.lower())
    propietario.set_password(clave)
    db.session.add(propietario)
    db.session.flush()
    return empresa, propietario


# ---------------------------------------------------------------------------------------------- demo
class _Ctx:
    def __init__(self, empresa):
        self.eid = empresa.id

    def add(self, _modelo, _hook=None, **kw):
        obj = _modelo(empresa_id=self.eid, **kw)
        db.session.add(obj)
        db.session.flush()
        if _hook:
            _hook(obj, True, None)
            db.session.flush()
        return obj


def cargar_demo(clave="LaMesada2026"):
    """Crea la empresa La Mesada con 4 fincas y dos campañas completas de datos ficticios."""
    empresa, padre = crear_empresa("La Mesada", "Roberto (Propietario)", "propietario@lamesada.com", clave,
                                   logo="img/logo_lamesada.png", demo=True, localidad="Valle de Tafí",
                                   telefono="(000) 000-0000")
    usar_empresa(empresa.id, padre)
    x = _Ctx(empresa)
    u = {x_.abreviatura: x_ for x_ in db.session.scalars(select(UnidadMedida).where(
        UnidadMedida.empresa_id == empresa.id)).unique()}

    # --- Usuarios: dos hijos encargados y un trabajador
    juan = Usuario(empresa_id=empresa.id, rol_id=rol("encargado").id, nombre="Juan (Encargado)",
                   email="juan@lamesada.com")
    pedro = Usuario(empresa_id=empresa.id, rol_id=rol("encargado").id, nombre="Pedro (Encargado)",
                    email="pedro@lamesada.com")
    carlos_u = Usuario(empresa_id=empresa.id, rol_id=rol("trabajador").id, nombre="Carlos (Trabajador)",
                       email="carlos@lamesada.com")
    for usr in (juan, pedro, carlos_u):
        usr.set_password(clave)
        db.session.add(usr)
    db.session.flush()

    # --- Fincas y lotes
    datos_fincas = [("Finca 1", "Paraje El Alto", 60, 52, juan, "Franco arenoso"),
                    ("Finca 2", "Ruta 307 km 45", 45, 40, juan, "Franco"),
                    ("Finca 3", "El Mollar", 80, 70, pedro, "Franco limoso"),
                    ("Finca 4", "La Ciénaga", 35, 30, pedro, "Arenoso")]
    fincas = []
    for nombre, ubic, tot, cult, resp, suelo in datos_fincas:
        fincas.append(x.add(Finca, nombre=nombre, ubicacion=ubic, superficie_total=D(tot), superficie_cultivable=D(cult),
                            tipo_suelo=suelo, responsable_id=resp.id, estado="activa", observaciones=DEMO))
    juan.fincas = fincas[:2]
    pedro.fincas = fincas[2:]
    f1, f2, f3, f4 = fincas
    lotes = {}
    # Lotes con su dibujo en el mapa (ubicación de ejemplo). Finca 3 riega con pivotes: lotes circulares.
    base = {f1: (-26.8600, -65.7200), f2: (-26.8680, -65.7200), f3: (-26.8820, -65.7180), f4: (-26.8660, -65.7000)}
    divisiones = {f1: [("A", "Lote A", 500, 400), ("B", "Lote B", 450, 400), ("C", "Lote C", 350, 400)],
                  f2: [("A", "Lote A", 550, 400), ("B", "Lote B", 450, 400)],
                  f3: [("A", "Pivote 1", 35, None), ("B", "Pivote 2", 35, None)],
                  f4: [("A", "Lote A", 450, 400), ("B", "Lote B", 300, 400)]}
    for finca, items in divisiones.items():
        lat, lng = base[finca]
        for letra, nombre, a_, b_ in items:
            if b_ is None:  # pivote de a_ hectáreas; los pivotes van uno al lado del otro
                forma = geo.circulo(lat - 0.0035, lng + 0.0035, a_)
                lng += 0.0078
            else:  # rectángulo de a_ x b_ metros; los lotes van contiguos hacia el este
                forma = geo.rectangulo(lat, lng, a_, b_)
                lng += (a_ + 20) / (111320 * math.cos(math.radians(lat)))
            lotes[(finca.nombre, letra)] = x.add(Lote, finca_id=finca.id, nombre=nombre, superficie=geo.hectareas(forma),
                                                 tipo_suelo=finca.tipo_suelo, estado="activo",
                                                 forma=forma["properties"]["forma"], geometria=geo.a_texto(forma))
    pivote_2 = geo.leer(lotes[("Finca 3", "B")].geometria)

    def L(finca, letra):
        return lotes[(finca.nombre, letra)].id

    # --- Campañas y cultivos
    c25 = x.add(Campana, nombre="2025/2026", fecha_inicio=date(2025, 7, 1), fecha_fin=date(2026, 6, 30),
                estado="cerrada")
    c26 = x.add(Campana, nombre="2026/2027", fecha_inicio=date(2026, 7, 1), fecha_fin=date(2027, 6, 30),
                estado="activa")
    papa = x.add(Cultivo, nombre="Papa", tipo="hortaliza", unidad_id=u["t"].id, estado="activo",
                 descripcion="Papa para consumo fresco.")
    cebolla = x.add(Cultivo, nombre="Cebolla", tipo="hortaliza", unidad_id=u["t"].id, estado="activo")
    maiz = x.add(Cultivo, nombre="Maíz", tipo="cereal", unidad_id=u["qq"].id, estado="activo")

    # --- Proveedores y clientes
    prov = {}
    for nombre, tipo in (("Semillas del Valle SRL", "semillas"), ("AgroInsumos Norte SA", "fertilizantes"),
                         ("Fitosanitarios Andinos SRL", "agroquimicos"), ("Estación de Servicio La Ruta", "combustible"),
                         ("Repuestos Agrícolas Tucumán", "repuestos")):
        prov[tipo] = x.add(Proveedor, razon_social=f"{nombre} [DEMO]", tipo=tipo, estado="activo",
                           telefono="(000) 000-0000", contacto="Contacto demo", observaciones=DEMO)
    cli = [x.add(Cliente, nombre=f"{n} [DEMO]", tipo=t, estado="activo", localidad=loc, observaciones=DEMO)
           for n, t, loc in (("Mercado Central Distribuidora", "mayorista", "Buenos Aires"),
                             ("Acopio San Miguel", "acopiador", "San Miguel de Tucumán"),
                             ("Frigorífico e Industria del Norte", "industria", "Salta"),
                             ("Verdulería Don José", "minorista", "Tafí del Valle"))]

    # --- Empleados
    tipos_emp = [("Carlos", "Gómez", "tractorista", f1, "hora", 6500), ("Miguel", "Rojas", "cargador", f1, "jornal", 32000),
                 ("Luis", "Díaz", "cargador", f2, "jornal", 32000), ("Ramón", "Pérez", "peon", f2, "jornal", 28000),
                 ("Hugo", "Quispe", "cosechador", f3, "unidad", 450), ("Ana", "Mamani", "cosechador", f3, "unidad", 450),
                 ("Jorge", "Vera", "tractorista", f3, "hora", 6500), ("Sergio", "Cruz", "cargador", f4, "jornal", 32000),
                 ("Marta", "López", "administrativo", None, "monto_fijo", 750000), ("Pablo", "Sosa", "peon", f4, "jornal", 28000)]
    emp = {}
    for i, (nom, ape, tipo, finca, mod, tarifa) in enumerate(tipos_emp):
        emp[nom] = x.add(Empleado, nombre=nom, apellido=ape, dni=f"3{i}000{i}00", tipo=tipo, estado="activo",
                         finca_id=finca.id if finca else None, modalidad_pago=mod, tarifa=D(tarifa),
                         fecha_ingreso=date(2020 + i % 5, 3, 1), puesto=tipo.capitalize(), observaciones=DEMO)
    emp["Carlos"].usuario_id = carlos_u.id

    # --- Maquinaria
    maq = {
        "tractor1": x.add(Maquina, nombre="Tractor John Deere 5090E", tipo="tractor", marca="John Deere", modelo="5090E",
                          anio=2018, identificacion="TR-001", horas_uso=D("3120"), estado="operativa",
                          responsable_id=emp["Carlos"].id, finca_id=f1.id, costo_hora=D("18000"),
                          intervalo_mantenimiento_horas=250, ultimo_mantenimiento_horas=D("2900")),
        "tractor2": x.add(Maquina, nombre="Tractor Massey Ferguson 4283", tipo="tractor", marca="Massey Ferguson",
                          anio=2015, identificacion="TR-002", horas_uso=D("5400"), estado="operativa",
                          responsable_id=emp["Jorge"].id, finca_id=f3.id, costo_hora=D("15000"),
                          intervalo_mantenimiento_horas=250, ultimo_mantenimiento_horas=D("5200")),
        "sembradora": x.add(Maquina, nombre="Sembradora de papa 2 surcos", tipo="sembradora", anio=2016,
                            identificacion="SEM-01", estado="operativa", costo_hora=D("6000")),
        "pulverizadora": x.add(Maquina, nombre="Pulverizadora de arrastre 2000 l", tipo="pulverizadora", anio=2019,
                               identificacion="PUL-01", estado="operativa", costo_hora=D("5000"),
                               proximo_mantenimiento_fecha=date(2026, 10, 3)),
        "camion": x.add(Maquina, nombre="Camión Mercedes-Benz 1114", tipo="camion", anio=2008, identificacion="AAA000",
                        estado="operativa", costo_hora=D("12000")),
    }

    # --- Insumos
    def insumo(nombre, cat, tipo, unidad, minimo):
        return x.add(Insumo, nombre=nombre, categoria=cat, tipo=tipo, unidad_id=u[unidad].id, stock_minimo=D(minimo),
                     estado="activo", observaciones=DEMO)
    ins = {
        "sem_papa": insumo("Semilla de papa Spunta", "semilla", "Semilla certificada", "kg", 2000),
        # La papa se siembra sobre todo con semilla propia (guardada de la cosecha anterior, sin costo)
        "sem_papa_propia": x.add(Insumo, nombre="Semilla de papa Spunta propia", categoria="semilla", tipo="Semilla propia",
                                 unidad_id=u["kg"].id, stock_minimo=D(0), estado="activo", propia=True,
                                 observaciones=DEMO + " Se guarda de nuestras cosechas."),
        "sem_cebolla": insumo("Semilla de cebolla Valcatorce", "semilla", "Semilla certificada", "kg", 5),
        "sem_maiz": insumo("Semilla de maíz híbrido", "semilla", "Semilla certificada", "kg", 50),
        "urea": insumo("Urea granulada 46%", "fertilizante", "Urea", "kg", 1500),
        "npk": insumo("NPK 15-15-15", "fertilizante", "NPK", "kg", 1000),
        "fosfato": insumo("Fosfato diamónico 18-46-0", "fertilizante", "Fosfato diamónico", "kg", 800),
        "glifo": insumo("Glifosato 48%", "agroquimico", "Herbicida", "l", 40),
        "mancozeb": insumo("Mancozeb 80%", "agroquimico", "Fungicida", "kg", 30),
        "ciper": insumo("Cipermetrina 25%", "agroquimico", "Insecticida", "l", 10),
        "filtro": insumo("Filtro de aceite tractor", "repuesto", "Filtro", "u", 2),
    }

    def compra(fecha, proveedor, renglones, condicion="contado", venc=None, comprobante=None):
        c = Compra(empresa_id=empresa.id, proveedor_id=proveedor.id, fecha=fecha, condicion=condicion,
                   vencimiento=venc, comprobante=comprobante, observaciones=DEMO, usuario_id=padre.id)
        svc_compras.guardar_compra(c, [{"insumo_id": i.id, "cantidad": D(q), "precio_unitario": D(p)}
                                       for i, q, p in renglones], True)
        return c

    # Compras campaña 2025/2026
    compra(date(2025, 7, 1), prov["semillas"], [(ins["sem_papa"], 60000, 650), (ins["sem_cebolla"], 30, 95000),
                                                 (ins["sem_maiz"], 700, 5200)], comprobante="A-0001-00001234")
    compra(date(2025, 7, 1), prov["fertilizantes"], [(ins["urea"], 18000, 820), (ins["npk"], 14000, 900),
                                                     (ins["fosfato"], 14000, 980)], comprobante="A-0003-00004567")
    compra(date(2025, 7, 1), prov["agroquimicos"], [(ins["glifo"], 350, 7800), (ins["mancozeb"], 250, 11500),
                                                    (ins["ciper"], 60, 14000)], comprobante="B-0002-00000789")
    compra(date(2025, 8, 5), prov["repuestos"], [(ins["filtro"], 8, 38000)], comprobante="B-0001-00000321")

    # Compras campaña 2026/2027 (una en cuenta corriente vencida y otra por vencer)
    compra(date(2026, 7, 1), prov["semillas"], [(ins["sem_papa"], 50000, 780), (ins["sem_cebolla"], 20, 110000),
                                                (ins["sem_maiz"], 800, 6100)], condicion="cuenta_corriente",
           venc=date(2026, 9, 20), comprobante="A-0001-00001890")
    compra(date(2026, 7, 2), prov["fertilizantes"], [(ins["urea"], 10000, 950), (ins["npk"], 6000, 1050),
                                                     (ins["fosfato"], 8000, 1120)], condicion="cuenta_corriente",
           venc=date(2026, 10, 4), comprobante="A-0003-00005120")
    compra(date(2026, 7, 1), prov["agroquimicos"], [(ins["glifo"], 150, 9100), (ins["mancozeb"], 120, 13200),
                                                     (ins["ciper"], 30, 16000)], comprobante="B-0002-00000950")

    # --- Siembras
    def siembra(finca, letra, camp, cultivo, fecha, ha, sem, kg, variedad, est, rinde, estado, sector=None):
        return x.add(Siembra, op.guardar_siembra, finca_id=finca.id, lote_id=L(finca, letra), campana_id=camp.id,
                     cultivo_id=cultivo.id, fecha_siembra=fecha, superficie=D(ha), variedad=variedad,
                     insumo_id=ins[sem].id, cantidad_semilla=D(kg), fecha_cosecha_estimada=est,
                     rendimiento_estimado=D(rinde), estado=estado, responsable_id=(juan if finca in (f1, f2) else pedro).id,
                     costo_semilla=0, origen_semilla="comprada", observaciones=DEMO,
                     geometria=geo.a_texto(sector) if sector else None)

    s_old = {
        "papa_f1": siembra(f1, "A", c25, papa, date(2025, 8, 10), 18, "sem_papa", 32000, "Spunta", date(2026, 1, 20), 30, "en_curso"),
        "ceb_f1": siembra(f1, "B", c25, cebolla, date(2025, 7, 25), 12, "sem_cebolla", 7, "Valcatorce", date(2026, 2, 15), 40, "en_curso"),
        "ceb_f2": siembra(f2, "A", c25, cebolla, date(2025, 7, 20), 20, "sem_cebolla", 11, "Valcatorce", date(2026, 2, 10), 40, "en_curso"),
        "maiz_f3": siembra(f3, "A", c25, maiz, date(2025, 11, 15), 35, "sem_maiz", 630, "Híbrido DK", date(2026, 4, 20), 85, "en_curso"),
        "papa_f4": siembra(f4, "A", c25, papa, date(2025, 9, 1), 16, "sem_papa", 26000, "Spunta", date(2026, 2, 1), 28, "en_curso"),
    }
    s_new = {
        "papa_f1": siembra(f1, "A", c26, papa, date(2026, 8, 15), 18, "sem_papa", 30000, "Spunta",
                           date.today() + timedelta(days=11), 32, "en_curso"),
        "ceb_f2": siembra(f2, "A", c26, cebolla, date(2026, 7, 25), 20, "sem_cebolla", 11, "Valcatorce", date(2027, 1, 15), 42, "en_curso"),
        "papa_f4": siembra(f4, "A", c26, papa, date(2026, 9, 5), 16, "sem_papa", 16000, "Spunta", date(2027, 1, 10), 30, "en_curso"),
    }
    # Pivote 2 de la Finca 3: camino interno este-oeste de 5 m y siembra en franjas verticales con medidas
    # (250 m de DK · 150 m de AX · el resto de DK, todavía pendiente de siembra), surcos a 52 cm. Los caminos se descuentan de cada franja.
    lng_c, lat_c = pivote_2["geometry"]["coordinates"]
    radio = pivote_2["properties"]["radio"]
    dlng = (radio + 30) / (111320 * math.cos(math.radians(lat_c)))
    camino = geo.linea([(lat_c, lng_c - dlng), (lat_c, lng_c + dlng)])
    x.add(CaminoLote, lote_id=L(f3, "B"), nombre="Camino central", ancho=D("5"),
          longitud=D(str(round(geo.longitud_m(camino), 1))), geometria=geo.a_texto(camino))
    for n, (sector, variedad) in enumerate(zip(geo.franjas(pivote_2, anchos_m=[250, 150], angulo=0),
                                               ["DK 72-10", "AX 7822", "DK 72-10"])):
        bruta = geo.hectareas(sector)
        en_camino = (D(str(geo.superficie_caminos_m2(sector, [(camino, 5)]))) / 10000).quantize(D("0.01"))
        hect = bruta - en_camino
        # Se siembra en días distintos: la franja 1 hace 9 días, la 2 hace 5 y la 3 queda pendiente (en 2 días)
        dia = date.today() + timedelta(days=(-9, -5, 2)[n])
        s_new[f"maiz_f3_{n + 1}"] = siembra(f3, "B", c26, maiz, dia, hect, "sem_maiz",
                                            (hect * 18).quantize(D("1")), variedad, date(2027, 3, 30), 90,
                                            "planificada" if n == 2 else "en_curso", sector=sector)
        s_new[f"maiz_f3_{n + 1}"].distancia_surcos = D("0.52")
        s_new[f"maiz_f3_{n + 1}"].orientacion_surcos = D("0")
        s_new[f"maiz_f3_{n + 1}"].superficie_caminos = en_camino

    def imp(s):
        return {"finca_id": s.finca_id, "lote_id": s.lote_id, "campana_id": s.campana_id, "cultivo_id": s.cultivo_id}

    # --- Aplicaciones, maquinaria, riego, trabajos por siembra
    def manejo(s, factor, base_fecha, cosechado=True):
        d = lambda n: base_fecha + timedelta(days=n)  # noqa: E731
        responsable = s.responsable_id
        hoy = date.today()

        def add(_modelo, _hook, **kw):  # no se cargan registros con fecha futura
            if kw["fecha"] <= hoy:
                x.add(_modelo, _hook, **kw)
        add(AplicacionFertilizante, op.guardar_aplicacion_fertilizante, insumo_id=ins["fosfato"].id, fecha=d(0),
              superficie=s.superficie, cantidad=s.superficie * 150 * factor, responsable_id=responsable, **imp(s))
        add(AplicacionFertilizante, op.guardar_aplicacion_fertilizante, insumo_id=ins["urea"].id, fecha=d(35),
              superficie=s.superficie, cantidad=s.superficie * 200 * factor, responsable_id=responsable, **imp(s))
        if cosechado:
            add(AplicacionFertilizante, op.guardar_aplicacion_fertilizante, insumo_id=ins["npk"].id, fecha=d(60),
                  superficie=s.superficie, cantidad=s.superficie * 150 * factor, responsable_id=responsable, **imp(s))
        add(AplicacionAgroquimico, op.guardar_aplicacion_agroquimico, insumo_id=ins["glifo"].id, fecha=d(-10),
              superficie=s.superficie, dosis=D("3"), unidad_dosis="l/ha", cantidad=s.superficie * 3,
              motivo="Control de malezas presiembra", responsable_id=responsable, **imp(s))
        if cosechado:
            add(AplicacionAgroquimico, op.guardar_aplicacion_agroquimico, insumo_id=ins["mancozeb"].id, fecha=d(50),
                  superficie=s.superficie, dosis=D("2"), unidad_dosis="kg/ha", cantidad=s.superficie * 2,
                  motivo="Prevención de tizón", responsable_id=responsable, **imp(s))
            add(AplicacionAgroquimico, op.guardar_aplicacion_agroquimico, insumo_id=ins["ciper"].id, fecha=d(70),
                  superficie=s.superficie, dosis=D("0.25"), unidad_dosis="l/ha", cantidad=s.superficie * D("0.25"),
                  motivo="Control de gusano", responsable_id=responsable, **imp(s))
        tractor = maq["tractor2"] if s.finca_id == f3.id else maq["tractor1"]
        operador = emp["Jorge"] if s.finca_id == f3.id else emp["Carlos"]
        horas = (s.superficie * D("1.5")).quantize(D("1"))
        add(UsoMaquinaria, op.guardar_uso_maquinaria, maquina_id=tractor.id, fecha=d(-15), horas=horas,
              operador_id=operador.id, trabajo_realizado="Preparación del terreno", combustible_litros=horas * 9,
              costo_combustible=0, costo_mantenimiento=D("0"), costo_hora=tractor.costo_hora, **imp(s))
        add(UsoMaquinaria, op.guardar_uso_maquinaria, maquina_id=maq["sembradora"].id, fecha=d(-1),
              horas=(horas / 2).quantize(D("1")), operador_id=operador.id, trabajo_realizado="Siembra",
              costo_combustible=0, costo_mantenimiento=D("0"), costo_hora=maq["sembradora"].costo_hora, **imp(s))
        add(CargaCombustible, op.guardar_combustible, fecha=d(-15), tipo_combustible="gasoil", litros=horas * 10,
              precio_litro=D("1350") if base_fecha.year == 2025 else D("1480"), maquina_id=tractor.id,
              proveedor_id=prov["combustible"].id, metodo_pago="efectivo", imputar_gasto=True,
              responsable_id=responsable, finca_id=s.finca_id, campana_id=s.campana_id, cultivo_id=s.cultivo_id)
        for n in range(0, 100 if cosechado else 30, 12):
            add(Riego, op.guardar_riego, fecha=d(n + 5), horas=D("10"), sistema="goteo" if s.cultivo_id != maiz.id else "gravedad",
                  consumo=D("400"), unidad_consumo="m3", costo=(s.superficie * 4200).quantize(D("1")),
                  responsable_id=responsable, **imp(s))
        peones = [emp["Ramón"], emp["Pablo"]] if s.finca_id in (f2.id, f4.id) else [emp["Ramón"]]
        for k, p in enumerate(peones):
            add(Trabajo, op.guardar_trabajo, fecha=d(20 + k), empleado_id=p.id, tipo_trabajo="Carpida / limpieza",
                  modalidad="jornal", jornales=(s.superficie / 2).quantize(D("1")), precio_unitario=p.tarifa, **imp(s))
        add(Trabajo, op.guardar_trabajo, fecha=d(-15), empleado_id=operador.id, tipo_trabajo="Trabajo con tractor",
              modalidad="hora", horas=horas, precio_unitario=operador.tarifa, **imp(s))
        add(ActividadCultivo, op.guardar_actividad, tipo="preparacion", fecha=d(-16), estado="realizada",
              descripcion="Arada y rastreada", responsable_id=responsable, costo=0, **imp(s))

    manejo(s_old["papa_f1"], 1, date(2025, 8, 10))
    manejo(s_old["ceb_f1"], D("0.8"), date(2025, 7, 25))
    manejo(s_old["ceb_f2"], D("0.8"), date(2025, 7, 20))
    manejo(s_old["maiz_f3"], D("0.7"), date(2025, 11, 15))
    manejo(s_old["papa_f4"], 1, date(2025, 9, 1))
    manejo(s_new["papa_f1"], 1, date(2026, 8, 15), cosechado=False)
    manejo(s_new["ceb_f2"], D("0.8"), date(2026, 7, 25), cosechado=False)
    manejo(s_new["papa_f4"], 1, date(2026, 9, 5), cosechado=False)

    # --- Cosechas campaña 2025/2026 (con mano de obra de cosecha y carga)
    def cosecha(s, fecha, cantidad, merma, calidad="primera", guardada=0):
        c = x.add(Cosecha, op.guardar_cosecha, siembra_id=s.id, fecha=fecha, superficie=s.superficie,
                  cantidad=D(cantidad), merma=D(merma), calidad=calidad, responsable_id=s.responsable_id,
                  semilla_guardada=D(guardada), insumo_semilla_id=ins["sem_papa_propia"].id if guardada else None,
                  unidad_id=s.cultivo.unidad_id, observaciones=DEMO, **imp(s))
        toneladas = D(cantidad) * s.cultivo.unidad.factor_base / 1000
        cargador = {f1.id: emp["Miguel"], f2.id: emp["Luis"], f3.id: emp["Sergio"], f4.id: emp["Sergio"]}[s.finca_id]
        x.add(Trabajo, op.guardar_trabajo, fecha=fecha, empleado_id=cargador.id, tipo_trabajo="Carga de bolsas",
              modalidad="jornal", jornales=(toneladas / 25).quantize(D("1")) + 2, precio_unitario=cargador.tarifa,
              **imp(s))
        for cosechador in (emp["Hugo"], emp["Ana"]):  # a destajo: por bolsa de 50 kg
            x.add(Trabajo, op.guardar_trabajo, fecha=fecha, empleado_id=cosechador.id, tipo_trabajo="Cosecha",
                  modalidad="unidad", cantidad=(toneladas * 10).quantize(D("1")), precio_unitario=cosechador.tarifa,
                  **imp(s))
        x.add(UsoMaquinaria, op.guardar_uso_maquinaria, maquina_id=maq["camion"].id, fecha=fecha, horas=D("12"),
              trabajo_realizado="Transporte", costo_combustible=D("180000"), combustible_litros=D("120"),
              costo_mantenimiento=D("0"), costo_hora=maq["camion"].costo_hora, **imp(s))
        return c

    cosecha(s_old["papa_f1"], date(2026, 1, 22), 560, 38, guardada=30)  # 30 t se guardan para semilla
    cosecha(s_old["ceb_f1"], date(2026, 2, 18), 470, 30)
    cosecha(s_old["ceb_f2"], date(2026, 2, 12), 820, 55, "segunda")
    cosecha(s_old["maiz_f3"], date(2026, 4, 25), 2900, 90)
    cosecha(s_old["papa_f4"], date(2026, 2, 3), 410, 35, guardada=20)

    # La papa de esta campaña se sembró con esa semilla propia: sin costo de semilla
    for clave in ("papa_f1", "papa_f4"):
        s = s_new[clave]
        s.insumo_id, s.origen_semilla, s.costo_semilla = ins["sem_papa_propia"].id, "propia", 0
        db.session.flush()
        op.guardar_siembra(s, False, None)

    # --- Ventas (con cobros; algunas pendientes)
    def venta(fecha, cliente, finca, camp, renglones, forma="transferencia", cobrar=None, venc=None, flete=0):
        v = Venta(empresa_id=empresa.id, cliente_id=cliente.id, fecha=fecha, finca_id=finca.id, campana_id=camp.id,
                  forma_pago=forma, fecha_vencimiento_cobro=venc, transporte="Camión propio" if flete else "A cargo del comprador",
                  costo_flete=D(flete), flete_a_cargo="vendedor" if flete else "comprador", usuario_id=padre.id,
                  observaciones=DEMO)
        svc_ventas.guardar_venta(v, [{"cultivo_id": c.id, "cantidad": D(q), "unidad_id": un.id, "precio_unitario": D(p),
                                      "calidad": cal} for c, q, un, p, cal in renglones], True)
        for f_cobro, monto in (cobrar or []):
            svc_ventas.registrar_cobro(v, f_cobro, D(monto) if monto != "total" else v.saldo, "transferencia")
        return v

    venta(date(2026, 1, 28), cli[0], f1, c25, [(papa, 300, u["t"], 260000, "primera")],
          cobrar=[(date(2026, 2, 15), "total")], flete=1400000)
    venta(date(2026, 2, 20), cli[0], f1, c25, [(papa, 222, u["t"], 245000, "primera")], cobrar=[(date(2026, 3, 10), "total")])
    venta(date(2026, 2, 25), cli[1], f1, c25, [(cebolla, 440, u["t"], 175000, "primera")],
          cobrar=[(date(2026, 3, 20), 50000000)], venc=date(2026, 4, 30))
    venta(date(2026, 2, 16), cli[1], f2, c25, [(cebolla, 765, u["t"], 160000, "segunda")],
          cobrar=[(date(2026, 3, 1), "total")])
    venta(date(2026, 5, 10), cli[2], f3, c25, [(maiz, 2810, u["qq"], 26000, "primera")],
          cobrar=[(date(2026, 6, 1), 40000000)], venc=date(2026, 7, 15))
    venta(date(2026, 2, 10), cli[0], f4, c25, [(papa, 300, u["t"], 255000, "primera")], cobrar=[(date(2026, 3, 1), "total")])
    venta(date(2026, 2, 28), cli[3], f4, c25, [(papa, 3000, u["bolsa25"], 7200, "segunda")], forma="efectivo",
          cobrar=[(date(2026, 2, 28), "total")])

    # --- Gastos generales manuales (estructura) y cuentas a pagar
    def gasto(fecha, codigo, descripcion, monto, finca=None, metodo="transferencia", proveedor=None, venc=None, camp=None):
        g = x.add(Gasto, op.guardar_gasto, fecha=fecha, categoria_id=gastos_auto.categoria_id(codigo),
                  descripcion=descripcion, monto=D(monto), metodo_pago=metodo, finca_id=finca.id if finca else None,
                  proveedor_id=proveedor.id if proveedor else None, vencimiento=venc, usuario_id=padre.id,
                  campana_id=camp.id if camp else None, observaciones=DEMO)
        return g

    for mes in range(7, 13):
        gasto(date(2025, mes, 10), "servicios", "Energía eléctrica bombeo", 380000, f1, camp=c25)
    gasto(date(2025, 9, 15), "impuestos", "Impuesto inmobiliario rural (4 fincas)", 2400000, camp=c25)
    gasto(date(2025, 10, 1), "alquileres", "Alquiler de galpón de acopio", 1800000, f2, camp=c25)
    gasto(date(2026, 3, 5), "reparaciones", "Reparación de bomba de riego", 950000, f3, camp=c25)
    gasto(date(2026, 9, 10), "reparaciones", "Cubiertas para acoplado", 1650000, f4, metodo="cuenta_corriente",
          proveedor=prov["repuestos"], venc=date(2026, 10, 10), camp=c26)
    gasto(date(2026, 9, 1), "servicios", "Energía eléctrica bombeo", 420000, f1, camp=c26)

    # Pagos a proveedores: parte de la compra de semillas 2026 (cuenta vencida con saldo)
    cuenta_semillas = db.session.scalar(select(CuentaPagar).where(CuentaPagar.empresa_id == empresa.id,
                                                                   CuentaPagar.origen == "compra")
                                        .order_by(CuentaPagar.vencimiento))
    if cuenta_semillas:
        svc_cuentas.registrar_pago(cuenta_semillas, date(2026, 8, 30), D("20000000"), "transferencia", "Pago parcial")

    # --- Pagos a empleados (cancelan lo trabajado) y un sueldo administrativo imputado como costo
    for nombre in ("Miguel", "Luis", "Sergio", "Hugo", "Ana", "Carlos", "Jorge", "Ramón", "Pablo"):
        e = emp[nombre]
        total = sum((t.total for t in db.session.scalars(select(Trabajo).where(Trabajo.empleado_id == e.id,
                                                                               Trabajo.fecha < date(2026, 7, 1)))),
                    D("0"))
        if total:
            x.add(PagoEmpleado, op.guardar_pago_empleado, empleado_id=e.id, fecha=date(2026, 6, 30),
                  concepto="Pago de jornales", periodo="Campaña 2025/2026", monto=total, metodo_pago="transferencia",
                  finca_id=e.finca_id, imputar_costo=False, usuario_id=padre.id)
    for mes in (7, 8, 9):
        x.add(PagoEmpleado, op.guardar_pago_empleado, empleado_id=emp["Marta"].id, fecha=date(2026, mes, 5),
              concepto="Sueldo mensual", periodo=f"2026-{mes:02d}", monto=D("750000"), metodo_pago="transferencia",
              imputar_costo=True, campana_id=c26.id, usuario_id=padre.id)
    # Trabajos de carga de septiembre (para "¿cuánto pagamos a los cargadores este mes?")
    for dia in (8, 15, 22):
        for nombre, s in (("Miguel", s_new["papa_f1"]), ("Sergio", s_new["papa_f4"])):
            e = emp[nombre]
            x.add(Trabajo, op.guardar_trabajo, fecha=date(2026, 9, dia), empleado_id=e.id, tipo_trabajo="Carga de bolsas",
                  modalidad="jornal", jornales=D("2"), precio_unitario=e.tarifa, **imp(s))
    x.add(PagoEmpleado, op.guardar_pago_empleado, empleado_id=emp["Miguel"].id, fecha=date(2026, 9, 20),
          concepto="Quincena", periodo="1ª quincena sep", monto=D("128000"), metodo_pago="efectivo", finca_id=f1.id,
          usuario_id=padre.id)

    # Otro ingreso (no venta) y actividades/tareas pendientes
    x.add(Ingreso, op.guardar_ingreso, fecha=date(2026, 3, 15), concepto="Alquiler de tractor a vecino",
          monto=D("900000"), metodo_pago="efectivo", estado="acreditado", finca_id=f3.id, campana_id=c25.id,
          usuario_id=padre.id, observaciones=DEMO)
    x.add(ActividadCultivo, op.guardar_actividad, tipo="plagas", fecha=date.today() + timedelta(days=2),
          estado="pendiente", descripcion="Monitoreo de polilla en papa", responsable_id=juan.id, costo=0,
          **imp(s_new["papa_f1"]))
    x.add(ActividadCultivo, op.guardar_actividad, tipo="fertilizacion", fecha=date.today() + timedelta(days=6),
          estado="pendiente", descripcion="Segunda fertilización nitrogenada", responsable_id=pedro.id, costo=0,
          **imp(s_new["papa_f4"]))
    x.add(Alerta, titulo="Renovar seguro del camión", tipo="vencimiento", prioridad="alta",
          fecha=date.today() + timedelta(days=5), estado="pendiente", usuario_id=padre.id)
    x.add(Alerta, titulo="Revisar cinta de goteo Lote A", tipo="tarea", prioridad="media", finca_id=f1.id,
          fecha=date.today() + timedelta(days=1), asignado_id=juan.id, estado="pendiente", usuario_id=padre.id)
    db.session.commit()
    return empresa
