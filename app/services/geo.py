"""Geometrías del mapa (GeoJSON) y cálculo de superficies.

Formato guardado (texto JSON, un "Feature" de GeoJSON):
  * Pivote / círculo:  {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lng, lat]},
                        "properties": {"forma": "circulo", "radio": 333.8}}      (radio en metros)
  * Rectángulo, polígono o sector: {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[lng, lat], ...]]},
                        "properties": {"forma": "rectangulo" | "poligono" | "sector"}}

La superficie se calcula en el servidor (no se confía en la que manda el navegador) con la fórmula de área
geodésica sobre la esfera (la misma que usan Leaflet.draw y Google Earth para superficies agrícolas).
"""
import json
import math
from decimal import Decimal

from ..utils.validacion import ErrorNegocio

RADIO_TIERRA = 6378137.0
FORMAS = {"circulo", "rectangulo", "poligono", "sector"}
MAX_VERTICES = 3000


def _numero(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ErrorNegocio("La figura dibujada tiene coordenadas inválidas.")
    return float(v)


def _punto(par):
    if not isinstance(par, (list, tuple)) or len(par) < 2:
        raise ErrorNegocio("La figura dibujada tiene coordenadas inválidas.")
    lng, lat = _numero(par[0]), _numero(par[1])
    if not (-180 <= lng <= 180 and -90 <= lat <= 90):
        raise ErrorNegocio("La figura está fuera del mapa.")
    return [round(lng, 7), round(lat, 7)]


def validar(feature, formas_permitidas=FORMAS):
    """Valida y normaliza un Feature GeoJSON recibido del navegador. Devuelve un dict limpio."""
    if isinstance(feature, str):
        if len(feature) > 300_000:
            raise ErrorNegocio("La figura es demasiado grande.")
        try:
            feature = json.loads(feature)
        except ValueError:
            raise ErrorNegocio("Figura inválida.")
    if not isinstance(feature, dict) or not isinstance(feature.get("geometry"), dict):
        raise ErrorNegocio("Figura inválida.")
    props = feature.get("properties") or {}
    forma = props.get("forma")
    if forma not in formas_permitidas:
        raise ErrorNegocio("Forma no permitida.")
    geom = feature["geometry"]
    limpio_props = {"forma": forma}
    if forma == "circulo":
        if geom.get("type") != "Point":
            raise ErrorNegocio("Un pivote se guarda como centro y radio.")
        centro = _punto(geom.get("coordinates"))
        radio = _numero(props.get("radio"))
        if not (5 <= radio <= 5000):
            raise ErrorNegocio("El radio del pivote debe estar entre 5 m y 5 km.")
        limpio_props["radio"] = round(radio, 2)
        limpio_geom = {"type": "Point", "coordinates": centro}
    else:
        if geom.get("type") != "Polygon" or not isinstance(geom.get("coordinates"), list) or not geom["coordinates"]:
            raise ErrorNegocio("Figura inválida.")
        anillos = []
        for anillo in geom["coordinates"][:20]:
            if not isinstance(anillo, list) or len(anillo) > MAX_VERTICES:
                raise ErrorNegocio("La figura tiene demasiados puntos.")
            puntos = [_punto(p) for p in anillo]
            if puntos and puntos[0] != puntos[-1]:
                puntos.append(puntos[0])
            if len(puntos) < 4:
                raise ErrorNegocio("Un polígono necesita al menos 3 esquinas.")
            anillos.append(puntos)
        limpio_geom = {"type": "Polygon", "coordinates": anillos}
        if forma == "sector":
            for clave in ("angulo_inicio", "angulo_fin", "angulo", "ancho"):
                if isinstance(props.get(clave), (int, float)) and math.isfinite(props[clave]):
                    limpio_props[clave] = round(float(props[clave]), 2)
    salida = {"type": "Feature", "geometry": limpio_geom, "properties": limpio_props}
    if area_m2(salida) < 1:
        raise ErrorNegocio("La figura dibujada no tiene superficie.")
    return salida


def _area_anillo(coords):
    total = 0.0
    for i in range(len(coords) - 1):
        lng1, lat1 = coords[i]
        lng2, lat2 = coords[i + 1]
        total += math.radians(lng2 - lng1) * (2 + math.sin(math.radians(lat1)) + math.sin(math.radians(lat2)))
    return abs(total * RADIO_TIERRA * RADIO_TIERRA / 2.0)


def area_m2(feature):
    geom = feature["geometry"]
    if geom["type"] == "Point":
        radio = feature["properties"]["radio"]
        return math.pi * radio * radio
    anillos = geom["coordinates"]
    return max(_area_anillo(anillos[0]) - sum(_area_anillo(a) for a in anillos[1:]), 0.0)


def hectareas(feature):
    return (Decimal(str(area_m2(feature))) / Decimal("10000")).quantize(Decimal("0.01"))


def a_texto(feature):
    return json.dumps(feature, separators=(",", ":"))


def leer(texto):
    if not texto:
        return None
    try:
        return json.loads(texto)
    except ValueError:
        return None


# ------------------------------------------------------------------ figuras (datos de ejemplo y pruebas)
def _destino(lat, lng, rumbo, distancia):
    d = distancia / RADIO_TIERRA
    b, f1, l1 = math.radians(rumbo), math.radians(lat), math.radians(lng)
    f2 = math.asin(math.sin(f1) * math.cos(d) + math.cos(f1) * math.sin(d) * math.cos(b))
    l2 = l1 + math.atan2(math.sin(b) * math.sin(d) * math.cos(f1), math.cos(d) - math.sin(f1) * math.sin(f2))
    return [round(math.degrees(l2), 7), round(math.degrees(f2), 7)]


def circulo(lat, lng, hectareas_):
    """Pivote centrado en (lat, lng) con la superficie indicada."""
    radio = math.sqrt(float(hectareas_) * 10000 / math.pi)
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {"forma": "circulo", "radio": round(radio, 2)}}


def rectangulo(lat, lng, ancho_m, alto_m):
    """Rectángulo con esquina sudoeste en (lat, lng)."""
    dlat = alto_m / 110540
    dlng = ancho_m / (111320 * math.cos(math.radians(lat)))
    anillo = [[lng, lat], [lng + dlng, lat], [lng + dlng, lat + dlat], [lng, lat + dlat], [lng, lat]]
    return {"type": "Feature", "geometry": {"type": "Polygon",
                                            "coordinates": [[[round(x, 7), round(y, 7)] for x, y in anillo]]},
            "properties": {"forma": "rectangulo"}}


def gajos(pivote, porcentajes, inicio=0):
    """Divide un pivote en sectores (gajos) según porcentajes, empezando en 'inicio' grados (0 = norte)."""
    lng, lat = pivote["geometry"]["coordinates"]
    radio = pivote["properties"]["radio"]
    total = float(sum(porcentajes)) or 1.0
    angulo, salida = float(inicio), []
    for p in porcentajes:
        barrido = 360.0 * float(p) / total
        pasos = max(8, math.ceil(barrido / 3))
        anillo = [[lng, lat]] + [_destino(lat, lng, angulo + barrido * i / pasos, radio) for i in range(pasos + 1)]
        anillo.append([lng, lat])
        salida.append({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [anillo]},
                       "properties": {"forma": "sector", "angulo_inicio": round(angulo % 360, 2),
                                      "angulo_fin": round((angulo + barrido) % 360, 2)}})
        angulo += barrido
    return salida


# ------------------------------------------------------------------ caminos (líneas con ancho)
def validar_linea(feature):
    """Camino interno: Feature LineString. Devuelve dict limpio."""
    if isinstance(feature, str):
        try:
            feature = json.loads(feature)
        except ValueError:
            raise ErrorNegocio("Camino inválido.")
    if not isinstance(feature, dict) or not isinstance(feature.get("geometry"), dict):
        raise ErrorNegocio("Camino inválido.")
    geom = feature["geometry"]
    if geom.get("type") != "LineString" or not isinstance(geom.get("coordinates"), list):
        raise ErrorNegocio("Un camino se dibuja como una línea.")
    puntos = [_punto(p) for p in geom["coordinates"][:MAX_VERTICES]]
    if len(puntos) < 2:
        raise ErrorNegocio("El camino necesita al menos 2 puntos.")
    salida = {"type": "Feature", "geometry": {"type": "LineString", "coordinates": puntos},
              "properties": {"forma": "camino"}}
    if longitud_m(salida) < 1:
        raise ErrorNegocio("El camino es demasiado corto.")
    return salida


class _Plano:
    """Proyección local en metros (x = este, y = norte) alrededor de un punto. Precisa para un campo."""

    def __init__(self, lat0, lng0):
        self.lat0, self.lng0 = lat0, lng0
        self.kx = math.cos(math.radians(lat0)) * 111320.0
        self.ky = 110540.0

    def a_xy(self, p):
        return ((p[0] - self.lng0) * self.kx, (p[1] - self.lat0) * self.ky)

    def a_lnglat(self, q):
        return [round(q[0] / self.kx + self.lng0, 7), round(q[1] / self.ky + self.lat0, 7)]


def _anillo(feature, lados=180):
    """Anillo exterior [[lng, lat], ...] (el pivote se aproxima con un polígono de muchos lados)."""
    geom = feature["geometry"]
    if geom["type"] == "Point":
        lng, lat = geom["coordinates"]
        radio = feature["properties"]["radio"]
        anillo = [_destino(lat, lng, 360.0 * i / lados, radio) for i in range(lados)]
        return anillo + [anillo[0]]
    return geom["coordinates"][0]


def _centro(anillo):
    n = len(anillo) - 1 or 1
    return sum(p[1] for p in anillo[:-1]) / n, sum(p[0] for p in anillo[:-1]) / n


def longitud_m(feature):
    coords = feature["geometry"]["coordinates"]
    plano = _Plano(coords[0][1], coords[0][0])
    total = 0.0
    for a, b in zip(coords, coords[1:]):
        (x1, y1), (x2, y2) = plano.a_xy(a), plano.a_xy(b)
        total += math.hypot(x2 - x1, y2 - y1)
    return total


def _dentro(pt, poli):
    x, y = pt
    dentro = False
    for i in range(len(poli)):
        x1, y1 = poli[i]
        x2, y2 = poli[(i + 1) % len(poli)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            dentro = not dentro
    return dentro


def longitud_dentro(linea, poligono, paso=0.5):
    """Metros de la línea que quedan dentro del polígono (muestreo cada 'paso' metros)."""
    anillo = _anillo(poligono)
    lat0, lng0 = _centro(anillo)
    plano = _Plano(lat0, lng0)
    poli = [plano.a_xy(p) for p in anillo[:-1]]
    total = 0.0
    coords = linea["geometry"]["coordinates"]
    for a, b in zip(coords, coords[1:]):
        (x1, y1), (x2, y2) = plano.a_xy(a), plano.a_xy(b)
        largo = math.hypot(x2 - x1, y2 - y1)
        pasos = max(1, int(largo / paso))
        tramo = largo / pasos
        for i in range(pasos):
            t = (i + 0.5) / pasos
            if _dentro((x1 + (x2 - x1) * t, y1 + (y2 - y1) * t), poli):
                total += tramo
    return total


def superficie_caminos_m2(poligono, caminos):
    """caminos: lista de (feature_linea, ancho_m). Área que ocupan dentro del polígono."""
    return sum(longitud_dentro(linea, poligono) * float(ancho) for linea, ancho in caminos)


# ------------------------------------------------------------------ franjas (sectores rectos dentro del lote)
def _recortar(poli, f, c, mayor):
    """Sutherland–Hodgman contra el semiplano f(p) >= c (mayor) o f(p) <= c."""
    def dentro(p):
        return f(p) >= c if mayor else f(p) <= c
    salida = []
    for i in range(len(poli)):
        a, b = poli[i], poli[(i + 1) % len(poli)]
        da, db = dentro(a), dentro(b)
        if da:
            salida.append(a)
        if da != db:
            fa, fb = f(a), f(b)
            t = (c - fa) / (fb - fa)
            salida.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
    return salida


def _area_plana(poli):
    return abs(sum(poli[i][0] * poli[(i + 1) % len(poli)][1] - poli[(i + 1) % len(poli)][0] * poli[i][1]
                   for i in range(len(poli))) / 2.0)


def franjas(lote, anchos_m=None, porcentajes=None, angulo=0.0):
    """Divide el lote (pivote o polígono) en franjas rectas paralelas.

    angulo: dirección de las franjas y de los surcos en grados desde el norte (0 = franjas verticales N-S,
            90 = franjas horizontales E-O). Las franjas se ordenan de oeste a este (o de sur a norte).
    anchos_m: ancho en metros de cada franja menos la última (la última es "el resto").
    porcentajes: alternativa a anchos_m, reparte la SUPERFICIE en esas proporciones.
    """
    anillo = _anillo(lote)
    lat0, lng0 = _centro(anillo)
    plano = _Plano(lat0, lng0)
    poli = [plano.a_xy(p) for p in anillo[:-1]]
    a = math.radians(angulo)
    through = lambda p: p[0] * math.cos(a) - p[1] * math.sin(a)  # noqa: E731  (eje transversal a las franjas)
    valores = [through(p) for p in poli]
    minimo, maximo = min(valores), max(valores)
    cortes = [minimo]
    if anchos_m:
        pos = minimo
        for ancho in anchos_m:
            pos += float(ancho)
            if pos >= maximo:
                raise ErrorNegocio("Las medidas superan el ancho del lote "
                                   f"({maximo - minimo:.0f} m en esa dirección).")
            cortes.append(pos)
    else:
        porcentajes = porcentajes or [1]
        total = _area_plana(poli)
        suma = float(sum(porcentajes)) or 1.0
        acumulado = 0.0
        for p in porcentajes[:-1]:
            acumulado += float(p) / suma
            lo, hi = minimo, maximo
            for _ in range(60):
                mid = (lo + hi) / 2
                if _area_plana(_recortar(poli, through, mid, False)) / total < acumulado:
                    lo = mid
                else:
                    hi = mid
            cortes.append((lo + hi) / 2)
    cortes.append(maximo)
    salida = []
    for i in range(len(cortes) - 1):
        trozo = _recortar(_recortar(poli, through, cortes[i], True), through, cortes[i + 1], False)
        if len(trozo) < 3:
            continue
        coords = [plano.a_lnglat(q) for q in trozo]
        coords.append(coords[0])
        salida.append({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [coords]},
                       "properties": {"forma": "sector", "angulo": round(angulo % 180, 2),
                                      "ancho": round(cortes[i + 1] - cortes[i], 2)}})
    return salida


def linea(puntos):
    """Feature LineString desde [(lat, lng), ...] (datos de ejemplo)."""
    return {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[lng, lat] for lat, lng in puntos]},
            "properties": {"forma": "camino"}}
