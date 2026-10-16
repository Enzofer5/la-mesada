"""Pruebas automáticas: recorren todas las pantallas con cada rol, prueban altas/ediciones/bajas, reglas de
negocio (stock, gastos automáticos, cobros), aislamiento entre empresas y exportaciones.

Ejecutar:  pytest -q                    (usa SQLite en memoria)
           TEST_DATABASE_URL=mysql+pymysql://usuario:clave@localhost/la_mesada_test pytest -q   (MySQL real)
"""
from datetime import date
from decimal import Decimal

import re

import pytest
from sqlalchemy import select, text

from app import create_app
from app.cli import crear_vista
from app.config import TestConfig
from app.crud.modulo import REGISTRO
from app.extensions import db
from app.models import (Cosecha, Cultivo, Empresa, Finca, Gasto, Insumo, Siembra, Trabajo, Usuario, Venta)
from app.services.seed import cargar_demo, crear_empresa, crear_superadmin
from app.services.tenant import usar_empresa

CLAVE = "LaMesada2026"


@pytest.fixture(scope="module")
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.session.execute(text("DROP VIEW IF EXISTS produccion"))
        db.session.commit()
        db.drop_all()
        db.create_all()
        crear_vista()
        crear_superadmin("admin@lamesada.app", CLAVE)
        cargar_demo(CLAVE)
        otra, _ = crear_empresa("Finca Vecina", "Otro dueño", "otro@vecina.com", CLAVE)
        usar_empresa(otra.id)
        db.session.add(Finca(empresa_id=otra.id, nombre="Finca Secreta", superficie_total=10, superficie_cultivable=10))
        db.session.commit()
    yield app


def login(app, email):
    cliente = app.test_client()
    r = cliente.post("/login", data={"email": email, "clave": CLAVE})
    assert r.status_code == 302, r.data[:500]
    return cliente


def ok(cliente, url, codigo=200):
    r = cliente.get(url)
    assert r.status_code == codigo, f"{url} → {r.status_code}\n{r.data[:3000].decode(errors='ignore')}"
    return r


def primer_id(app, modelo, **filtros):
    with app.app_context():
        stmt = select(modelo.id)
        empresa = db.session.scalar(select(Empresa).where(Empresa.slug == "la-mesada"))
        stmt = stmt.where(modelo.empresa_id == empresa.id)
        for k, v in filtros.items():
            stmt = stmt.where(getattr(modelo, k) == v)
        return db.session.scalar(stmt.order_by(modelo.id).limit(1))


PANTALLAS = ["/dashboard", "/dashboard?todo=1", "/dashboard?anio=2026", "/alertas/", "/calendario/",
             "/calendario/?anio=2026&mes=2", "/calendario/eventos.json", "/inventario/", "/inventario/?bajo=1",
             "/compras/", "/compras/nueva", "/ventas/", "/ventas/?buscar=1", "/ventas/?estado=con_saldo",
             "/ventas/nueva", "/finanzas/", "/rentabilidad/", "/rentabilidad/?agrupar=finca&prorratear=1&todo=1",
             "/rentabilidad/?agrupar=campana_cultivo&todo=1", "/reportes/", "/documentos/", "/documentos/subir",
             "/configuracion/", "/mi-cuenta/clave"]


def test_login_incorrecto(app):
    r = app.test_client().post("/login", data={"email": "propietario@lamesada.com", "clave": "mala"})
    assert "incorrectos".encode() in r.data


def test_requiere_login(app):
    r = app.test_client().get("/dashboard")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_pantallas_propietario(app):
    c = login(app, "propietario@lamesada.com")
    for url in PANTALLAS + ["/configuracion/usuarios", "/configuracion/usuarios/nuevo", "/configuracion/empresa",
                            "/configuracion/historial"]:
        ok(c, url)
    finca = primer_id(app, Finca)
    ok(c, f"/fincas/{finca}")
    ok(c, f"/fincas/{finca}?todo=1")


def test_todos_los_modulos_crud(app):
    c = login(app, "propietario@lamesada.com")
    for key, modulo in REGISTRO.items():
        ok(c, f"/m/{key}/")
        ok(c, f"/m/{key}/?buscar=1")
        ok(c, f"/m/{key}/nuevo")
        for formato in ("csv", "xlsx", "pdf"):
            r = ok(c, f"/m/{key}/?exportar={formato}")
            assert len(r.data) > 20
        id_ = primer_id(app, modulo.modelo)
        if id_:
            if modulo.detalle_url is None:
                ok(c, f"/m/{key}/{id_}")
            r = c.get(f"/m/{key}/{id_}/editar")
            assert r.status_code in (200, 302), key


def test_reportes_y_exportaciones(app):
    from app.services.reportes import POR_CLAVE
    c = login(app, "propietario@lamesada.com")
    for tipo in POR_CLAVE:
        ok(c, f"/reportes/{tipo}?todo=1")
        ok(c, f"/reportes/{tipo}?anio=2026")
        for formato in ("csv", "xlsx", "pdf"):
            r = ok(c, f"/reportes/{tipo}?todo=1&exportar={formato}")
            assert len(r.data) > 50, tipo
    r = ok(c, "/reportes/")
    assert "cargadores".encode() in r.data


def test_encargado_ve_solo_sus_fincas(app):
    c = login(app, "juan@lamesada.com")
    for url in PANTALLAS:
        ok(c, url)
    with app.app_context():
        f1 = db.session.scalar(select(Finca.id).where(Finca.nombre == "Finca 1"))
        f3 = db.session.scalar(select(Finca.id).where(Finca.nombre == "Finca 3"))
    ok(c, f"/fincas/{f1}")
    ok(c, f"/fincas/{f3}", 403)
    r = ok(c, "/m/fincas/")
    assert b"Finca 1" in r.data and b"Finca 3" not in r.data
    siembra_f3 = primer_id(app, Siembra, finca_id=f3)
    ok(c, f"/m/siembras/{siembra_f3}", 403)
    ok(c, "/configuracion/usuarios", 403)
    ok(c, "/configuracion/historial", 403)
    # no puede cargar datos en una finca ajena
    r = c.post("/m/gastos/nuevo", data={"fecha": "2026-09-01", "categoria_id": "1", "descripcion": "x",
                                        "monto": "100", "metodo_pago": "efectivo", "finca_id": str(f3)})
    assert r.status_code == 400


def test_trabajador(app):
    c = login(app, "carlos@lamesada.com")
    r = ok(c, "/mi-panel/")
    assert b"Mis trabajos" in r.data
    ok(c, "/calendario/")
    ok(c, "/dashboard", 403)
    ok(c, "/m/gastos/", 403)
    ok(c, "/ventas/", 403)


def test_superadmin_y_aislamiento(app):
    c = login(app, "admin@lamesada.app")
    ok(c, "/admin/empresas")
    ok(c, "/admin/empresas/nueva")
    ok(c, "/dashboard", 403)
    r = c.post("/admin/empresas/nueva", data={"nombre": "Cliente Nuevo", "propietario": "Ana", "email": "ana@nuevo.com",
                                             "clave": "Clave1234"})
    assert r.status_code == 302
    # la otra empresa no ve datos de La Mesada ni al revés
    otro = login(app, "otro@vecina.com")
    r = ok(otro, "/m/fincas/")
    assert b"Finca Secreta" in r.data and b"Finca 1" not in r.data
    finca_lm = primer_id(app, Finca)
    ok(otro, f"/fincas/{finca_lm}", 404)
    ok(otro, f"/m/fincas/{finca_lm}/editar", 404)
    prop = login(app, "propietario@lamesada.com")
    r = ok(prop, "/m/fincas/")
    assert b"Finca Secreta" not in r.data


def test_flujo_completo_siembra_aplicacion_cosecha_venta(app):
    c = login(app, "propietario@lamesada.com")
    with app.app_context():
        finca = db.session.scalar(select(Finca).where(Finca.nombre == "Finca 2"))
        lote = finca.lotes[1]
        cultivo = db.session.scalar(select(Cultivo).where(Cultivo.nombre == "Papa"))
        urea = db.session.scalar(select(Insumo).where(Insumo.nombre.like("Urea%")))
        stock_antes = urea.stock
        ids = (finca.id, lote.id, cultivo.id, urea.id)
    campana = primer_id(app, __import__("app.models", fromlist=["Campana"]).Campana, estado="activa")
    f_id, l_id, c_id, u_id = ids
    # Siembra
    r = c.post("/m/siembras/nuevo", data={"finca_id": f_id, "lote_id": l_id, "campana_id": campana, "cultivo_id": c_id,
                                          "fecha_siembra": "2026-09-10", "superficie": "5", "variedad": "Test",
                                          "costo_semilla": "1.000.000", "estado": "en_curso",
                                          "fecha_cosecha_estimada": "2027-01-10", "rendimiento_estimado": "30"})
    assert r.status_code == 302, re.findall(rb"(?:error-campo|mensaje-error)\">([^<]*)", r.data)
    siembra_id = int(r.headers["Location"].rstrip("/").split("/")[-1])
    # Aplicación de fertilizante: descuenta stock y genera gasto
    r = c.post("/m/aplicaciones_fertilizantes/nuevo", data={"finca_id": f_id, "lote_id": l_id, "campana_id": campana,
                                                            "cultivo_id": c_id, "insumo_id": u_id, "fecha": "2026-09-15",
                                                            "superficie": "5", "cantidad": "500"})
    assert r.status_code == 302, re.findall(rb"(?:error-campo|mensaje-error)\">([^<]*)", r.data)
    # Stock insuficiente → error de negocio
    r = c.post("/m/aplicaciones_fertilizantes/nuevo", data={"finca_id": f_id, "campana_id": campana, "cultivo_id": c_id,
                                                            "insumo_id": u_id, "fecha": "2026-09-16",
                                                            "cantidad": "99999999"})
    assert r.status_code == 400 and "Stock insuficiente".encode() in r.data
    # Lote que no es de la finca → error
    otro_lote = primer_id(app, __import__("app.models", fromlist=["Lote"]).Lote)
    r = c.post("/m/riegos/nuevo", data={"finca_id": f_id, "lote_id": otro_lote, "fecha": "2026-09-15", "horas": "2",
                                        "sistema": "goteo", "costo": "1000"})
    assert r.status_code == 400
    # Trabajo por jornales
    empleado = primer_id(app, __import__("app.models", fromlist=["Empleado"]).Empleado, tipo="cargador")
    r = c.post("/m/trabajos/nuevo", data={"fecha": "2026-09-20", "empleado_id": empleado, "tipo_trabajo": "Carga de bolsas",
                                          "finca_id": f_id, "campana_id": campana, "cultivo_id": c_id,
                                          "modalidad": "jornal", "jornales": "3", "precio_unitario": "30000"})
    assert r.status_code == 302, re.findall(rb"(?:error-campo|mensaje-error)\">([^<]*)", r.data)
    # Cosecha
    r = c.post("/m/cosechas/nuevo", data={"siembra_id": siembra_id, "finca_id": f_id, "lote_id": l_id,
                                          "campana_id": campana, "cultivo_id": c_id, "fecha": "2026-09-28",
                                          "superficie": "5", "cantidad": "150", "merma": "10", "calidad": "primera"})
    assert r.status_code == 302, re.findall(rb"(?:error-campo|mensaje-error)\">([^<]*)", r.data)
    with app.app_context():
        urea = db.session.get(Insumo, u_id)
        assert urea.stock == stock_antes - 500
        gastos = db.session.scalars(select(Gasto).where(Gasto.campana_id == campana, Gasto.finca_id == f_id,
                                                        Gasto.cultivo_id == c_id)).all()
        origenes = {g.origen for g in gastos}
        assert {"siembra", "aplicacion_fertilizante", "trabajo"} <= origenes
        trabajo = db.session.scalar(select(Trabajo).order_by(Trabajo.id.desc()))
        assert trabajo.total == Decimal("90000.00")
        assert db.session.get(Siembra, siembra_id).estado == "cosechada"
        cosecha = db.session.scalar(select(Cosecha).order_by(Cosecha.id.desc()))
        assert cosecha.comercializable == Decimal("140") and cosecha.rendimiento == Decimal("30")
        cliente = primer_id(app, __import__("app.models", fromlist=["Cliente"]).Cliente)
        unidad = db.session.get(Cultivo, c_id).unidad_id
    # Venta con renglones y cobro parcial
    r = c.post("/ventas/nueva", data={"cliente_id": cliente, "fecha": "2026-09-29", "finca_id": f_id, "campana_id": campana,
                                      "forma_pago": "cuenta_corriente", "cultivo_id": [c_id], "unidad_id": [unidad],
                                      "cantidad": ["140"], "precio_unitario": ["250000"], "calidad": ["primera"],
                                      "lote_id": [""], "costo_flete": "500000", "flete_a_cargo": "vendedor"})
    assert r.status_code == 302, re.findall(rb"(?:error-campo|mensaje-error)\">([^<]*)", r.data)
    venta_id = int(r.headers["Location"].rstrip("/").split("/")[-1])
    ok(c, f"/ventas/{venta_id}")
    r = c.post(f"/ventas/{venta_id}/cobro", data={"fecha": "2026-09-29", "monto": "10000000", "metodo_pago": "transferencia"})
    assert r.status_code == 302
    r = c.post(f"/ventas/{venta_id}/cobro", data={"fecha": "2026-09-29", "monto": "999999999", "metodo_pago": "efectivo"})
    with app.app_context():
        venta = db.session.get(Venta, venta_id)
        assert venta.total == Decimal("35000000.00")
        assert venta.cobrado == Decimal("10000000.00") and venta.estado_pago == "parcial"
        flete = db.session.scalars(select(Gasto).where(Gasto.origen == "venta_flete", Gasto.origen_id == venta_id)).all()
        assert sum(g.monto for g in flete) == Decimal("500000.00")
    # Editar y eliminar la aplicación restituye el stock
    apl = primer_id(app, __import__("app.models", fromlist=["AplicacionFertilizante"]).AplicacionFertilizante,
                    fecha=date(2026, 9, 15), finca_id=f_id)
    r = c.post(f"/m/aplicaciones_fertilizantes/{apl}/eliminar")
    assert r.status_code == 302
    with app.app_context():
        assert db.session.get(Insumo, u_id).stock == stock_antes
        assert not db.session.scalars(select(Gasto).where(Gasto.origen == "aplicacion_fertilizante",
                                                          Gasto.origen_id == apl)).all()
    # Gasto automático no editable desde Gastos
    gasto_auto = primer_id(app, Gasto, origen="siembra")
    r = c.get(f"/m/gastos/{gasto_auto}/editar")
    assert r.status_code == 302
    # Rentabilidad de la venta nueva aparece
    r = ok(c, f"/rentabilidad/?campana={campana}&finca={f_id}")
    assert b"Papa" in r.data


def test_compra_en_cuenta_corriente_y_pago(app):
    c = login(app, "propietario@lamesada.com")
    proveedor = primer_id(app, __import__("app.models", fromlist=["Proveedor"]).Proveedor)
    insumo = primer_id(app, Insumo, categoria="agroquimico")
    with app.app_context():
        stock = db.session.get(Insumo, insumo).stock
    r = c.post("/compras/nueva", data={"proveedor_id": proveedor, "fecha": "2026-09-29", "condicion": "cuenta_corriente",
                                       "insumo_id": [insumo], "cantidad": ["10"], "precio_unitario": ["1000"]})
    assert r.status_code == 302, re.findall(rb"(?:error-campo|mensaje-error)\">([^<]*)", r.data)
    compra_id = int(r.headers["Location"].rstrip("/").split("/")[-1])
    from app.models import CuentaPagar
    with app.app_context():
        assert db.session.get(Insumo, insumo).stock == stock + 10
        cuenta = db.session.scalar(select(CuentaPagar).where(CuentaPagar.origen == "compra",
                                                              CuentaPagar.origen_id == compra_id))
        assert cuenta.importe == Decimal("10000.00") and cuenta.estado == "pendiente"
        cuenta_id = cuenta.id
    ok(c, f"/cuentas-pagar/{cuenta_id}/pagar")
    r = c.post(f"/cuentas-pagar/{cuenta_id}/pagar", data={"fecha": "2026-09-29", "monto": "4000", "metodo_pago": "efectivo"})
    assert r.status_code == 302
    with app.app_context():
        cuenta = db.session.get(CuentaPagar, cuenta_id)
        assert cuenta.pagado == Decimal("4000.00") and cuenta.estado == "parcial"
    # no se puede eliminar una compra con pagos
    r = c.post(f"/compras/{compra_id}/eliminar")
    assert r.status_code == 302 and f"/compras/{compra_id}" in r.headers["Location"]


def test_historial_registra_acciones(app):
    c = login(app, "propietario@lamesada.com")
    r = ok(c, "/configuracion/historial")
    assert "registró".encode() in r.data


def test_calculos_de_rentabilidad(app):
    from app.services import rentabilidad as rent
    with app.app_context():
        usuario = db.session.scalar(select(Usuario).where(Usuario.email == "propietario@lamesada.com"))
        usar_empresa(usuario.empresa_id, usuario)
        f = {"finca": None, "lote": None, "cultivo": None, "campana": None, "categoria": None, "desde": None,
             "hasta": None}
        filas, total = rent.rentabilidad(f, "cultivo")
        assert total["ganancia"] == total["ingresos"] - total["costos"]
        assert sum(x["costos"] for x in filas) == total["costos"]
        con_prorrateo, total_p = rent.rentabilidad(f, "cultivo", prorratear_generales=True)
        assert abs(total_p["costos"] - total["costos"]) < Decimal("1")  # prorratear no crea ni pierde costos
        gastos = db.session.scalar(select(db.func.sum(Gasto.monto)).where(Gasto.empresa_id == usuario.empresa_id))
        assert abs(Decimal(str(gastos)) - total["costos"]) < Decimal("0.01")


def test_mapa_lotes_y_sectores(app):
    from app.models import Campana, Lote
    from app.services import geo
    c = login(app, "juan@lamesada.com")
    ok(c, "/mapa/")
    r = ok(c, "/mapa/datos.json")
    datos = r.get_json()
    assert any(l["forma"] == "rectangulo" for l in datos["lotes"])
    assert all(l["finca"] in ("Finca 1", "Finca 2") for l in datos["lotes"])  # sólo sus fincas
    with app.app_context():
        f1 = db.session.scalar(select(Finca.id).where(Finca.nombre == "Finca 1"))
        f3 = db.session.scalar(select(Finca.id).where(Finca.nombre == "Finca 3"))
        campana = db.session.scalar(select(Campana.id).where(Campana.estado == "activa"))
        papa = db.session.scalar(select(Cultivo.id).where(Cultivo.nombre == "Papa"))
    pivote = geo.circulo(-26.80, -65.60, 50)
    # pivote nuevo de 50 ha: la superficie la calcula el servidor
    r = c.post("/mapa/lotes", json={"finca_id": f1, "nombre": "Pivote Test", "geometria": pivote})
    assert r.status_code == 200 and r.get_json()["ok"], r.get_json()
    assert r.get_json()["superficie"] == 50.0
    lote_id = r.get_json()["lote_id"]
    # un encargado no puede dibujar en una finca ajena
    r = c.post("/mapa/lotes", json={"finca_id": f3, "nombre": "Ajeno", "geometria": pivote})
    assert r.status_code == 400
    # geometría inválida
    r = c.post("/mapa/lotes", json={"finca_id": f1, "nombre": "Malo", "geometria": {"type": "Feature",
               "geometry": {"type": "Point", "coordinates": [999, 0]}, "properties": {"forma": "circulo", "radio": 10}}})
    assert r.status_code == 400
    # sembrar el pivote en 3 gajos: A, B, A
    gajos = geo.gajos(geo.leer(geo.a_texto(pivote)), [40, 20, 40])
    r = c.post("/mapa/sectores", json={
        "lote_id": lote_id, "campana_id": campana, "cultivo_id": papa, "fecha_siembra": "2026-09-25",
        "fecha_cosecha_estimada": "2027-01-20", "rendimiento_estimado": "30",
        "sectores": [{"geometria": g, "variedad": v, "costo_semilla": "1000000"}
                     for g, v in zip(gajos, ["Spunta", "Innovator", "Spunta"])]})
    assert r.status_code == 200 and r.get_json()["ok"], r.get_json()
    with app.app_context():
        siembras = db.session.scalars(select(Siembra).where(Siembra.lote_id == lote_id)).all()
        assert [s.variedad for s in siembras] == ["Spunta", "Innovator", "Spunta"]
        assert abs(sum(s.superficie for s in siembras) - Decimal("50")) < Decimal("0.2")
        assert all(s.geometria for s in siembras)
        gastos = db.session.scalars(select(Gasto).where(Gasto.origen == "siembra",
                                                        Gasto.origen_id.in_([s.id for s in siembras]))).all()
        assert len(gastos) == 3
        siembra_id = siembras[1].id
    # la cosecha del sector se precarga con finca, lote, cultivo y hectáreas
    r = ok(c, f"/m/cosechas/nuevo?siembra_id={siembra_id}")
    assert f'value="{lote_id}" selected'.encode() in r.data
    r = ok(c, f"/mapa/datos.json?campana={campana}")
    assert sum(1 for s in r.get_json()["siembras"] if s["lote_id"] == lote_id) == 3
    r = c.post(f"/mapa/lotes/{lote_id}/quitar")
    assert r.get_json()["ok"]
    # el trabajador no accede al mapa
    ok(login(app, "carlos@lamesada.com"), "/mapa/", 403)


def test_caminos_franjas_y_surcos(app):
    from app.models import CaminoLote, Campana
    from app.services import geo
    c = login(app, "propietario@lamesada.com")
    with app.app_context():
        f3 = db.session.scalar(select(Finca.id).where(Finca.nombre == "Finca 3"))
        campana = db.session.scalar(select(Campana.id).where(Campana.estado == "activa"))
        maiz = db.session.scalar(select(Cultivo.id).where(Cultivo.nombre == "Maíz"))
    pivote = geo.circulo(-26.70, -65.50, 40)
    r = c.post("/mapa/lotes", json={"finca_id": f3, "nombre": "Pivote Franjas", "geometria": pivote})
    lote_id = r.get_json()["lote_id"]
    lng, lat = pivote["geometry"]["coordinates"]
    camino = geo.linea([(lat, lng - 0.01), (lat, lng + 0.01)])  # atraviesa el pivote de oeste a este
    r = c.post("/mapa/caminos", json={"lote_id": lote_id, "nombre": "Central", "ancho": "6", "geometria": camino})
    assert r.get_json()["ok"], r.get_json()
    r = c.post("/mapa/caminos", json={"lote_id": lote_id, "ancho": "0", "geometria": camino})
    assert r.status_code == 400
    datos = ok(c, "/mapa/datos.json").get_json()
    lote = next(l for l in datos["lotes"] if l["id"] == lote_id)
    assert len(lote["caminos"]) == 1 and lote["superficie_util"] < lote["superficie"]
    # franjas verticales de 200 m y 150 m + resto
    sectores = geo.franjas(pivote, anchos_m=[200, 150], angulo=0)
    assert [s["properties"]["ancho"] for s in sectores][:2] == [200.0, 150.0]
    r = c.post("/mapa/sectores", json={
        "lote_id": lote_id, "campana_id": campana, "cultivo_id": maiz, "fecha_siembra": "2026-09-28",
        "distancia_surcos": "0.52", "orientacion": 0,
        "sectores": [{"geometria": g, "variedad": v} for g, v in zip(sectores, ["DK", "AX", "DK"])]})
    assert r.get_json()["ok"], r.get_json()
    assert r.get_json()["neta"] < r.get_json()["superficie"]  # se descontó el camino
    with app.app_context():
        siembras = db.session.scalars(select(Siembra).where(Siembra.lote_id == lote_id).order_by(Siembra.id)).all()
        assert all(s.distancia_surcos == Decimal("0.52") and s.orientacion_surcos == Decimal("0") for s in siembras)
        assert all(s.superficie_caminos > 0 for s in siembras)
        camino_id = db.session.scalar(select(CaminoLote.id).where(CaminoLote.lote_id == lote_id))
    # medidas que no entran en el pivote
    try:
        geo.franjas(pivote, anchos_m=[500, 400])
        assert False, "debía fallar"
    except Exception as e:
        assert "superan" in str(e)
    assert c.post(f"/mapa/caminos/{camino_id}/eliminar").get_json()["ok"]


def test_siembra_en_distintos_dias_y_edicion(app):
    """Sectores sembrados en fechas distintas, uno pendiente que se siembra después, ajuste de forma y baja."""
    from datetime import date, timedelta
    from app.models import Campana
    from app.services import geo
    c = login(app, "juan@lamesada.com")
    with app.app_context():
        f1 = db.session.scalar(select(Finca.id).where(Finca.nombre == "Finca 1"))
        campana = db.session.scalar(select(Campana.id).where(Campana.estado == "activa"))
        papa = db.session.scalar(select(Cultivo.id).where(Cultivo.nombre == "Papa"))
    pivote = geo.circulo(-26.60, -65.40, 30)
    lote_id = c.post("/mapa/lotes", json={"finca_id": f1, "nombre": "Pivote Días", "geometria": pivote}).get_json()["lote_id"]
    franjas = geo.franjas(pivote, anchos_m=[200, 200], angulo=90)
    hoy = date.today()
    r = c.post("/mapa/sectores", json={
        "lote_id": lote_id, "campana_id": campana, "cultivo_id": papa,
        "fecha_siembra": (hoy - timedelta(days=5)).isoformat(),
        "sectores": [
            {"geometria": franjas[0], "variedad": "Spunta", "costo_semilla": "500000"},
            {"geometria": franjas[1], "variedad": "Innovator", "costo_semilla": "400000",
             "fecha_siembra": (hoy - timedelta(days=2)).isoformat()},
            {"geometria": franjas[2], "variedad": "Spunta", "estado": "planificada",
             "fecha_siembra": (hoy + timedelta(days=2)).isoformat()}]})
    assert r.get_json()["ok"], r.get_json()
    assert r.get_json()["pendientes"] == 1
    with app.app_context():
        ss = db.session.scalars(select(Siembra).where(Siembra.lote_id == lote_id).order_by(Siembra.id)).all()
        assert [s.estado for s in ss] == ["en_curso", "en_curso", "planificada"]
        assert ss[0].fecha_siembra != ss[1].fecha_siembra
        ids = [s.id for s in ss]
        assert not db.session.scalars(select(Gasto).where(Gasto.origen == "siembra", Gasto.origen_id == ids[2])).all()
    # aparece como alerta de siembra pendiente
    assert "Siembra pendiente".encode() in ok(c, "/alertas/").data
    # no se puede marcar con fecha futura
    r = c.post(f"/mapa/siembras/{ids[2]}/sembrar", json={"fecha_siembra": (hoy + timedelta(days=1)).isoformat()})
    assert r.status_code == 400
    r = c.post(f"/mapa/siembras/{ids[2]}/sembrar", json={"fecha_siembra": hoy.isoformat(), "variedad": "Spunta",
                                                        "costo_semilla": "450000"})
    assert r.get_json()["ok"], r.get_json()
    with app.app_context():
        s = db.session.get(Siembra, ids[2])
        assert s.estado == "en_curso" and s.fecha_siembra == hoy
        assert db.session.scalar(select(Gasto.monto).where(Gasto.origen == "siembra", Gasto.origen_id == ids[2])) == Decimal("450000")
    # volver a pendiente quita el costo
    assert c.post(f"/mapa/siembras/{ids[2]}/pendiente", json={}).get_json()["ok"]
    with app.app_context():
        assert db.session.get(Siembra, ids[2]).estado == "planificada"
        assert not db.session.scalars(select(Gasto).where(Gasto.origen == "siembra", Gasto.origen_id == ids[2])).all()
    # ajustar la forma de un sector: se achica y se recalculan las hectáreas
    datos = ok(c, "/mapa/datos.json").get_json()
    s0 = next(s for s in datos["siembras"] if s["id"] == ids[0])
    assert s0["url_editar"]
    anillo = s0["geometria"]["geometry"]["coordinates"][0]
    lat0 = sum(p[1] for p in anillo) / len(anillo)
    lng0 = sum(p[0] for p in anillo) / len(anillo)
    chico = {"type": "Feature", "properties": {"forma": "sector"}, "geometry": {"type": "Polygon", "coordinates": [[
        [lng0 + (x - lng0) * 0.5, lat0 + (y - lat0) * 0.5] for x, y in anillo]]}}
    r = c.post(f"/mapa/siembras/{ids[0]}/forma", json={"geometria": chico})
    assert r.get_json()["ok"], r.get_json()
    assert r.get_json()["superficie"] < s0["superficie"] * 0.3
    # eliminar un sector
    assert c.post(f"/mapa/siembras/{ids[1]}/eliminar").get_json()["ok"]
    with app.app_context():
        assert db.session.get(Siembra, ids[1]) is None
        assert not db.session.scalars(select(Gasto).where(Gasto.origen == "siembra", Gasto.origen_id == ids[1])).all()
    # un encargado de otra finca no puede tocarlo
    otro = login(app, "pedro@lamesada.com")
    assert otro.post(f"/mapa/siembras/{ids[0]}/eliminar").status_code == 403


def test_semilla_propia_y_comprada(app):
    """La semilla propia se guarda de la cosecha (sin costo) y se usa sin precio; la comprada lleva precio."""
    from app.models import Campana, Cosecha, Insumo
    from app.services import geo
    c = login(app, "propietario@lamesada.com")
    with app.app_context():
        propia = db.session.scalar(select(Insumo).where(Insumo.propia.is_(True)))
        comprada = db.session.scalar(select(Insumo).where(Insumo.nombre == "Semilla de papa Spunta"))
        propia_id, comprada_id, stock0 = propia.id, comprada.id, propia.stock
        assert stock0 > 0 and propia.costo_promedio == 0  # vino de las cosechas de la demo
        # la demo: papa de esta campaña con semilla propia → sin gasto de semilla
        papa = db.session.scalar(select(Cultivo.id).where(Cultivo.nombre == "Papa"))
        ss = db.session.scalars(select(Siembra).where(Siembra.origen_semilla == "propia")).all()
        assert ss and all(s.costo_semilla == 0 for s in ss)
        assert not db.session.scalars(select(Gasto).where(Gasto.origen == "siembra",
                                                          Gasto.origen_id.in_([s.id for s in ss]))).all()
        cos = db.session.scalar(select(Cosecha).where(Cosecha.semilla_guardada > 0))
        assert cos.comercializable == cos.cantidad - cos.merma - cos.semilla_guardada
        f1 = db.session.scalar(select(Finca.id).where(Finca.nombre == "Finca 1"))
        campana = db.session.scalar(select(Campana.id).where(Campana.estado == "activa"))
    pivote = geo.circulo(-26.55, -65.35, 20)
    lote_id = c.post("/mapa/lotes", json={"finca_id": f1, "nombre": "Pivote Semillas", "geometria": pivote}).get_json()["lote_id"]
    fr = geo.franjas(pivote, porcentajes=[50, 50])
    base = {"lote_id": lote_id, "campana_id": campana, "cultivo_id": papa, "fecha_siembra": "2026-09-20"}
    # la semilla propia no acepta precio
    r = c.post("/mapa/sectores", json=dict(base, sectores=[{"geometria": fr[0], "origen_semilla": "propia", "costo_semilla": "1000"}]))
    assert r.status_code == 400
    # propia marcada como comprada → error
    r = c.post("/mapa/sectores", json=dict(base, sectores=[{"geometria": fr[0], "origen_semilla": "comprada",
                                                            "insumo_id": propia_id, "cantidad_semilla": "100"}]))
    assert r.status_code == 400
    r = c.post("/mapa/sectores", json=dict(base, sectores=[
        {"geometria": fr[0], "variedad": "Spunta", "origen_semilla": "propia", "insumo_id": propia_id, "cantidad_semilla": "3000"},
        {"geometria": fr[1], "variedad": "Innovator", "origen_semilla": "comprada", "costo_semilla": "800000"}]))
    assert r.get_json()["ok"], r.get_json()
    with app.app_context():
        s1, s2 = db.session.scalars(select(Siembra).where(Siembra.lote_id == lote_id).order_by(Siembra.id)).all()
        assert (s1.origen_semilla, s1.costo_semilla) == ("propia", 0)
        assert (s2.origen_semilla, s2.costo_semilla) == ("comprada", Decimal("800000"))
        assert db.session.get(Insumo, propia_id).stock == stock0 - 3000
    # cosecha que guarda semilla: sube el stock propio (t → kg)
    r = c.post(f"/m/cosechas/nuevo", data={"csrf_token": "", "siembra_id": s1.id, "finca_id": f1, "lote_id": lote_id,
                                          "campana_id": campana, "cultivo_id": papa, "fecha": "2026-12-20", "superficie": "5",
                                          "cantidad": "150", "merma": "10", "semilla_guardada": "12",
                                          "insumo_semilla_id": propia_id}, follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        cos = db.session.scalar(select(Cosecha).where(Cosecha.siembra_id == s1.id))
        assert cos is not None and cos.semilla_guardada == 12
        assert cos.comercializable == 128
        assert db.session.get(Insumo, propia_id).stock == stock0 - 3000 + 12000
    # se identifican en los listados
    assert b"(propia)" in ok(c, "/m/insumos/").data
    assert b"P/ semilla" in ok(c, "/m/cosechas/?buscar=1").data
    ok(c, "/m/cosechas/nuevo")
