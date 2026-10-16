/* La Mesada · Mapa de lotes
   - Imagen satelital (Esri World Imagery) o calles (OpenStreetMap).
   - Dibujo de lotes: pivote (círculo), rectángulo o polígono libre. Las hectáreas se calculan solas.
   - División de un lote en sectores (gajos del pivote o franjas) con distinta variedad/semilla en cada uno:
     cada sector se guarda como una siembra independiente.
*/
(function () {
  "use strict";
  if (typeof L === "undefined") return;

  const CFG = JSON.parse(document.getElementById("mapa-config").textContent);
  const CSRF = document.querySelector('meta[name="csrf-token"]').content;
  const panel = document.getElementById("m-panel");
  const fmt = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 2 });
  const fmt0 = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 0 });
  const moneda = (v) => "$ " + fmt0.format(v || 0);
  const fecha = (iso) => (iso ? iso.split("-").reverse().join("/") : "");
  const ESTADOS = { planificada: "Pendiente de siembra", en_curso: "Sembrado", cosechada: "Cosechada", perdida: "Perdida" };
  const PALETA = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"];
  const R = 6378137;

  /* ------------------------------------------------------------ utilidades DOM (sin innerHTML con datos) */
  function h(tag, attrs, ...hijos) {
    const el = document.createElement(tag);
    Object.entries(attrs || {}).forEach(([k, v]) => {
      if (v === null || v === undefined || v === false) return;
      if (k === "class") el.className = v;
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else if (k === "value") el.value = v;
      else el.setAttribute(k, v === true ? "" : v);
    });
    hijos.flat().forEach((c) => { if (c !== null && c !== undefined && c !== false) el.append(c instanceof Node ? c : String(c)); });
    return el;
  }
  const boton = (texto, onclick, clase) => h("button", { type: "button", class: "btn btn-sm " + (clase || ""), onclick }, texto);
  const enlace = (texto, href, clase) => h("a", { class: "btn btn-sm " + (clase || ""), href }, texto);
  function campo(etiqueta, control) { return h("label", { class: "campo" }, h("span", {}, etiqueta), control); }
  function select(opciones, valor, vacio) {
    const s = h("select", {});
    if (vacio !== undefined) s.append(h("option", { value: "" }, vacio));
    opciones.forEach((o) => { const op = h("option", { value: o.id }, o.nombre); if (String(o.id) === String(valor)) op.selected = true; s.append(op); });
    return s;
  }
  function mensaje(texto, tipo) { return h("div", { class: "mensaje mensaje-" + (tipo || "info") }, texto); }
  function mostrarPanel(...contenido) {
    ocupado = false;
    panel.replaceChildren(...contenido.flat(Infinity).filter((c) => c !== null && c !== undefined && c !== false && c !== ""));
    if (window.innerWidth < 900) panel.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  async function enviar(url, datos) {
    const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json", "X-CSRFToken": CSRF }, body: JSON.stringify(datos || {}) });
    let json = {};
    try { json = await r.json(); } catch (e) { json = { ok: false, error: "Error del servidor (" + r.status + ")." }; }
    if (!r.ok && json.ok !== false) json = { ok: false, error: "Error " + r.status };
    return json;
  }

  /* ------------------------------------------------------------ geometría */
  const rad = (g) => (g * Math.PI) / 180;
  const deg = (r) => (r * 180) / Math.PI;
  function areaAnillo(coords) { // coords [[lng, lat], ...] cerrado
    let t = 0;
    for (let i = 0; i < coords.length - 1; i++) {
      const [x1, y1] = coords[i], [x2, y2] = coords[i + 1];
      t += rad(x2 - x1) * (2 + Math.sin(rad(y1)) + Math.sin(rad(y2)));
    }
    return Math.abs((t * R * R) / 2);
  }
  function areaFeature(f) {
    if (!f) return 0;
    if (f.geometry.type === "Point") return Math.PI * f.properties.radio * f.properties.radio;
    const anillos = f.geometry.coordinates;
    return Math.max(areaAnillo(anillos[0]) - anillos.slice(1).reduce((a, r) => a + areaAnillo(r), 0), 0);
  }
  const ha = (m2) => m2 / 10000;
  function destino(lat, lng, rumboGrados, distancia) {
    const d = distancia / R, b = rad(rumboGrados), f1 = rad(lat), l1 = rad(lng);
    const f2 = Math.asin(Math.sin(f1) * Math.cos(d) + Math.cos(f1) * Math.sin(d) * Math.cos(b));
    const l2 = l1 + Math.atan2(Math.sin(b) * Math.sin(d) * Math.cos(f1), Math.cos(d) - Math.sin(f1) * Math.sin(f2));
    return [deg(l2), deg(f2)];
  }
  function cerrar(anillo) {
    const a = anillo.slice();
    if (a.length && (a[0][0] !== a[a.length - 1][0] || a[0][1] !== a[a.length - 1][1])) a.push(a[0]);
    return a;
  }
  function featureDeCapa(capa, forma) {
    if (capa instanceof L.Circle) {
      const c = capa.getLatLng();
      return { type: "Feature", geometry: { type: "Point", coordinates: [c.lng, c.lat] }, properties: { forma: "circulo", radio: capa.getRadius() } };
    }
    const latlngs = capa.getLatLngs();
    const anillo = (Array.isArray(latlngs[0]) ? latlngs[0] : latlngs).map((p) => [p.lng, p.lat]);
    return { type: "Feature", geometry: { type: "Polygon", coordinates: [cerrar(anillo)] }, properties: { forma: forma || "poligono" } };
  }
  function capaDeFeature(f, estilo) {
    if (!f || !f.geometry) return null;
    if (f.geometry.type === "Point") {
      const [lng, lat] = f.geometry.coordinates;
      return L.circle([lat, lng], Object.assign({ radius: f.properties.radio }, estilo));
    }
    return L.polygon(f.geometry.coordinates.map((r) => r.map(([lng, lat]) => [lat, lng])), estilo);
  }

  function limites(f) {
    if (f.geometry.type === "Point") return L.latLng(f.geometry.coordinates[1], f.geometry.coordinates[0]).toBounds(f.properties.radio * 2);
    return L.latLngBounds(f.geometry.coordinates[0].map(([lng, lat]) => [lat, lng]));
  }

  /* Gajos de un pivote: porcentajes → sectores circulares, empezando en "inicio" grados (0 = norte, sentido horario) */
  function gajos(f, porcentajes, inicio) {
    const [lng, lat] = f.geometry.coordinates;
    const radio = f.properties.radio;
    const total = porcentajes.reduce((a, b) => a + b, 0) || 1;
    let angulo = inicio || 0;
    return porcentajes.map((p) => {
      const barrido = (360 * p) / total;
      const pasos = Math.max(8, Math.ceil(barrido / 3));
      const anillo = [[lng, lat]];
      for (let i = 0; i <= pasos; i++) anillo.push(destino(lat, lng, angulo + (barrido * i) / pasos, radio));
      anillo.push([lng, lat]);
      const sector = { type: "Feature", geometry: { type: "Polygon", coordinates: [anillo] },
        properties: { forma: "sector", angulo_inicio: angulo % 360, angulo_fin: (angulo + barrido) % 360 } };
      angulo += barrido;
      return sector;
    });
  }

  /* ---- geometría plana local (metros) para franjas, caminos y surcos ---- */
  function anilloDe(f, lados) {
    if (f.geometry.type === "Point") {
      const [lng, lat] = f.geometry.coordinates, n = lados || 180;
      const a = [];
      for (let i = 0; i < n; i++) a.push(destino(lat, lng, (360 * i) / n, f.properties.radio));
      a.push(a[0]);
      return a;
    }
    return f.geometry.coordinates[0];
  }
  function plano(anillo) {
    const n = anillo.length - 1 || 1;
    const lat0 = anillo.slice(0, -1).reduce((a, p) => a + p[1], 0) / n;
    const lng0 = anillo.slice(0, -1).reduce((a, p) => a + p[0], 0) / n;
    const kx = Math.cos(rad(lat0)) * 111320, ky = 110540;
    return { xy: ([x, y]) => [(x - lng0) * kx, (y - lat0) * ky], ll: ([x, y]) => [x / kx + lng0, y / ky + lat0] };
  }
  const areaPlana = (poly) => { let a = 0; for (let i = 0; i < poly.length; i++) { const [x1, y1] = poly[i], [x2, y2] = poly[(i + 1) % poly.length]; a += x1 * y2 - x2 * y1; } return Math.abs(a / 2); };
  function recortar(poly, f, c, mayor) { // Sutherland–Hodgman contra el semiplano f(p) >= c / <= c
    const dentro = (p) => (mayor ? f(p) >= c : f(p) <= c);
    const salida = [];
    for (let i = 0; i < poly.length; i++) {
      const a = poly[i], b = poly[(i + 1) % poly.length], ia = dentro(a), ib = dentro(b);
      if (ia) salida.push(a);
      if (ia !== ib) { const t = (c - f(a)) / (f(b) - f(a)); salida.push([a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])]); }
    }
    return salida;
  }
  /* Franjas rectas paralelas dentro del lote (también dentro del pivote).
     angulo: dirección de las franjas y surcos en grados desde el norte (0 = verticales N-S, 90 = horizontales E-O).
     medidas.anchos: metros de cada franja salvo la última (resto) · medidas.porcentajes: reparte la superficie. */
  function franjas(lote, medidas, angulo) {
    const anillo = anilloDe(lote), pl = plano(anillo);
    const base = anillo.slice(0, -1).map(pl.xy);
    const a = rad(angulo || 0);
    const eje = (p) => p[0] * Math.cos(a) - p[1] * Math.sin(a);
    const vals = base.map(eje), min = Math.min(...vals), max = Math.max(...vals);
    const cortes = [min];
    let error = null;
    if (medidas.anchos) {
      let pos = min;
      medidas.anchos.forEach((w) => { pos += w; if (pos >= max && !error) error = `Las medidas superan el ancho del lote en esa dirección (${fmt0.format(max - min)} m).`; cortes.push(Math.min(pos, max - 0.01)); });
    } else {
      const total = areaPlana(base), suma = medidas.porcentajes.reduce((x, y) => x + y, 0) || 1;
      let acum = 0;
      medidas.porcentajes.slice(0, -1).forEach((p) => {
        acum += p / suma;
        let lo = min, hi = max;
        for (let i = 0; i < 50; i++) { const mid = (lo + hi) / 2; if (areaPlana(recortar(base, eje, mid, false)) / total < acum) lo = mid; else hi = mid; }
        cortes.push((lo + hi) / 2);
      });
    }
    cortes.push(max);
    const sectores = [];
    for (let i = 0; i < cortes.length - 1; i++) {
      const trozo = recortar(recortar(base, eje, cortes[i], true), eje, cortes[i + 1], false);
      if (trozo.length < 3) continue;
      // largo máximo de la franja (en la dirección de los surcos)
      const largo = (() => { const d = trozo.map((p) => p[0] * Math.sin(a) + p[1] * Math.cos(a)); return Math.max(...d) - Math.min(...d); })();
      sectores.push({ type: "Feature", geometry: { type: "Polygon", coordinates: [cerrar(trozo.map(pl.ll))] },
        properties: { forma: "sector", angulo: ((angulo % 180) + 180) % 180, ancho: Math.round((cortes[i + 1] - cortes[i]) * 100) / 100 }, _largo: largo });
    }
    return { sectores, ancho_total: max - min, error };
  }
  function dentroPoligono([x, y], poli) {
    let d = false;
    for (let i = 0, j = poli.length - 1; i < poli.length; j = i++) {
      const [xi, yi] = poli[i], [xj, yj] = poli[j];
      if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) d = !d;
    }
    return d;
  }
  function longitudDentro(linea, poligono) { // metros de un camino que caen dentro de un sector/lote
    const anillo = anilloDe(poligono), pl = plano(anillo), poli = anillo.slice(0, -1).map(pl.xy);
    let total = 0;
    const c = linea.geometry.coordinates;
    for (let k = 0; k < c.length - 1; k++) {
      const [x1, y1] = pl.xy(c[k]), [x2, y2] = pl.xy(c[k + 1]);
      const largo = Math.hypot(x2 - x1, y2 - y1), pasos = Math.max(1, Math.floor(largo / 1)), tramo = largo / pasos;
      for (let i = 0; i < pasos; i++) { const t = (i + 0.5) / pasos; if (dentroPoligono([x1 + (x2 - x1) * t, y1 + (y2 - y1) * t], poli)) total += tramo; }
    }
    return total;
  }
  function longitudLinea(linea) {
    const c = linea.geometry.coordinates, pl = plano([...c, c[0]]);
    let t = 0;
    for (let k = 0; k < c.length - 1; k++) { const [x1, y1] = pl.xy(c[k]), [x2, y2] = pl.xy(c[k + 1]); t += Math.hypot(x2 - x1, y2 - y1); }
    return t;
  }
  const caminosEnM2 = (poligono, caminos) => (caminos || []).reduce((acc, c) => acc + longitudDentro(c.geometria, poligono) * c.ancho, 0);
  /* Líneas de surcos (para dibujar): como máximo "tope" líneas representativas */
  function lineasSurcos(sector, angulo, distancia, tope) {
    const anillo = anilloDe(sector), pl = plano(anillo), poli = anillo.slice(0, -1).map(pl.xy);
    const a = rad(angulo || 0);
    const eje = (p) => p[0] * Math.cos(a) - p[1] * Math.sin(a);     // transversal
    const dir = (p) => p[0] * Math.sin(a) + p[1] * Math.cos(a);     // a lo largo del surco
    const vals = poli.map(eje), min = Math.min(...vals), max = Math.max(...vals);
    const cantidad = Math.floor((max - min) / distancia);
    const salto = Math.max(1, Math.ceil(cantidad / (tope || 60)));
    const lineas = [];
    for (let k = 1; k <= cantidad; k += salto) {
      const s = min + k * distancia, ts = [];
      for (let i = 0; i < poli.length; i++) {
        const p = poli[i], q = poli[(i + 1) % poli.length], ep = eje(p), eq = eje(q);
        if ((ep - s) * (eq - s) < 0) { const t = (s - ep) / (eq - ep); ts.push(dir(p) + t * (dir(q) - dir(p))); }
      }
      ts.sort((x, y) => x - y);
      for (let i = 0; i + 1 < ts.length; i += 2) {
        const aXY = (u) => [s * Math.cos(a) + u * Math.sin(a), -s * Math.sin(a) + u * Math.cos(a)];
        lineas.push([pl.ll(aXY(ts[i])), pl.ll(aXY(ts[i + 1]))].map(([lng, lat]) => [lat, lng]));
      }
    }
    return { lineas, cantidad };
  }

  /* ------------------------------------------------------------ mapa base */
  const mapa = L.map("mapa", { zoomControl: true, preferCanvas: false }).setView([-34.6, -64.2], 5);
  const satelite = L.layerGroup([
    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
      maxZoom: 19, maxNativeZoom: 18, attribution: "Imágenes © Esri, Maxar, Earthstar Geographics" }),
    L.tileLayer("https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}", {
      maxZoom: 19, maxNativeZoom: 18, opacity: 0.9 }),
  ]).addTo(mapa);
  const calles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap" });
  L.control.scale({ imperial: false }).addTo(mapa);
  const etiquetas = () => mapa.getContainer().classList.toggle("sin-etiquetas", mapa.getZoom() < 15);
  mapa.on("zoomend", etiquetas);
  mapa.pm.setLang("es");
  mapa.pm.setGlobalOptions({ snappable: true, snapDistance: 15, allowSelfIntersection: false,
    templineStyle: { color: "#ffdd00" }, hintlineStyle: { color: "#ffdd00", dashArray: [5, 5] },
    pathOptions: { color: "#ffdd00", weight: 3, fillOpacity: 0.15 } });

  const btnCapa = document.getElementById("m-capa");
  btnCapa.addEventListener("click", () => {
    if (mapa.hasLayer(satelite)) { mapa.removeLayer(satelite); calles.addTo(mapa); btnCapa.querySelector("span").textContent = "Satélite"; }
    else { mapa.removeLayer(calles); satelite.addTo(mapa); btnCapa.querySelector("span").textContent = "Calles"; }
  });
  document.getElementById("m-ubicacion").addEventListener("click", () => {
    mapa.locate({ setView: true, maxZoom: 16 });
  });
  mapa.on("locationerror", () => alertaPanel("No se pudo obtener tu ubicación. En el celular hace falta permiso de ubicación y conexión segura (https)."));
  mapa.on("locationfound", (e) => { L.circleMarker(e.latlng, { radius: 7, color: "#fff", weight: 2, fillColor: "#2a78d6", fillOpacity: 1 }).addTo(mapa); });

  /* ------------------------------------------------------------ estado */
  let DATOS = { lotes: [], siembras: [] };
  let ocupado = false; // mientras se dibuja o se arman sectores, los clics sobre lotes no cambian el panel
  const capaLotes = L.featureGroup().addTo(mapa);
  const capaSiembras = L.featureGroup().addTo(mapa);
  const capaEdicion = L.featureGroup().addTo(mapa);
  const capaCaminos = L.featureGroup().addTo(mapa);
  const capaSurcos = L.featureGroup();
  // Los caminos se dibujan con su ancho real en metros según el zoom
  const metrosPorPixel = () => (40075016.686 * Math.cos(rad(mapa.getCenter().lat))) / Math.pow(2, mapa.getZoom() + 8);
  function anchoCaminos() {
    capaCaminos.eachLayer((c) => c.setStyle({ weight: Math.max(2, c.options._ancho / metrosPorPixel()) }));
    if (mapa.getZoom() >= 16) capaSurcos.addTo(mapa); else mapa.removeLayer(capaSurcos);
  }
  mapa.on("zoomend", anchoCaminos);
  function limpiarEdicion() {
    mapa.pm.disableDraw();
    capaEdicion.eachLayer((capa) => { if (capa.pm && capa.pm.enabled()) capa.pm.disable(); });
    capaEdicion.clearLayers();
  }
  let colores = {};
  const selCampana = document.getElementById("m-campana");
  const selFinca = document.getElementById("m-finca");

  const claveVariedad = (s) => s.cultivo + " · " + s.variedad;
  function asignarColores() {
    const claves = [...new Set(DATOS.siembras.map(claveVariedad))].sort();
    colores = {};
    claves.forEach((k, i) => { colores[k] = PALETA[i % PALETA.length]; });
  }
  const lotesVisibles = () => DATOS.lotes.filter((l) => !selFinca.value || String(l.finca_id) === selFinca.value);
  const siembrasDe = (loteId) => DATOS.siembras.filter((s) => s.lote_id === loteId);

  async function cargar(ajustar) {
    const r = await fetch(CFG.urls.datos + "?campana=" + encodeURIComponent(selCampana.value || ""));
    DATOS = await r.json();
    asignarColores();
    dibujar(ajustar);
    if (CFG.lote) {
      const l = DATOS.lotes.find((x) => x.id === CFG.lote);
      CFG.lote = null;
      if (l) { seleccionarLote(l); return; }
    }
    panelInicio();
  }

  function estiloSiembra(s) {
    const color = colores[claveVariedad(s)] || "#888";
    if (s.estado === "cosechada") return { color: "#ffffff", weight: 1.5, dashArray: "4 4", fillColor: color, fillOpacity: 0.25 };
    if (s.estado === "perdida") return { color: "#ffffff", weight: 1, fillColor: "#777", fillOpacity: 0.45 };
    if (s.estado === "planificada") return { color: color, weight: 2.5, dashArray: "8 6", fillColor: color, fillOpacity: 0.18 };
    return { color: "#ffffff", weight: 1.5, fillColor: color, fillOpacity: 0.55 };
  }

  function dibujar(ajustar) {
    capaLotes.clearLayers();
    capaSiembras.clearLayers();
    capaCaminos.clearLayers();
    capaSurcos.clearLayers();
    lotesVisibles().forEach((l) => {
      if (!l.geometria) return;
      const siembras = siembrasDe(l.id);
      const conSector = siembras.filter((s) => s.geometria);
      const enteras = siembras.filter((s) => !s.geometria);
      const relleno = enteras.length ? { fillColor: colores[claveVariedad(enteras[0])], fillOpacity: 0.5 } : { fillOpacity: 0.08, fillColor: "#ffffff" };
      const capa = capaDeFeature(l.geometria, Object.assign({ color: "#ffe14d", weight: 2.5 }, relleno));
      capa.bindTooltip(`${l.nombre} · ${fmt.format(l.superficie)} ha`, { permanent: true, direction: "center", className: "etiqueta-lote" });
      capa.on("click", () => { if (!ocupado) seleccionarLote(l); });
      capaLotes.addLayer(capa);
      conSector.forEach((s) => {
        const cs = capaDeFeature(s.geometria, estiloSiembra(s));
        cs.bindTooltip(`${s.variedad} · ${fmt.format(s.superficie)} ha` + (s.estado === "planificada" ? " · pendiente de siembra" : "") + (s.distancia_surcos ? ` · surcos a ${fmt.format(s.distancia_surcos * 100)} cm` : ""), { sticky: true });
        cs.on("click", (e) => { L.DomEvent.stopPropagation(e); if (!ocupado) seleccionarSiembra(s, l); });
        capaSiembras.addLayer(cs);
        if (s.distancia_surcos && s.orientacion_surcos !== null && s.estado !== "planificada") {
          lineasSurcos(s.geometria, s.orientacion_surcos, s.distancia_surcos, 70).lineas.forEach((ln) =>
            capaSurcos.addLayer(L.polyline(ln, { color: "#ffffff", weight: 1, opacity: 0.45, interactive: false })));
        }
      });
      (l.caminos || []).forEach((c) => {
        const linea = L.polyline(c.geometria.geometry.coordinates.map(([lng, lat]) => [lat, lng]),
          { color: "#c8a46b", opacity: 0.95, lineCap: "butt", _ancho: c.ancho, weight: 3 });
        linea.bindTooltip(`${c.nombre} · ${fmt.format(c.ancho)} m de ancho · ${fmt0.format(c.longitud)} m`, { sticky: true });
        linea.on("click", (e) => { L.DomEvent.stopPropagation(e); if (!ocupado) seleccionarLote(l); });
        capaCaminos.addLayer(linea);
      });
    });
    capaSiembras.bringToFront();
    capaCaminos.bringToFront();
    anchoCaminos();
    if (ajustar) encuadrar();
  }
  function encuadrar() {
    const grupo = L.featureGroup([...capaLotes.getLayers()]);
    if (grupo.getLayers().length) mapa.fitBounds(grupo.getBounds().pad(0.15), { maxZoom: 17 });
  }

  /* ------------------------------------------------------------ paneles */
  function alertaPanel(texto) { panel.prepend(mensaje(texto, "aviso")); }

  function leyenda() {
    const totales = {};
    const pendientes = {};
    DATOS.siembras.filter((s) => lotesVisibles().some((l) => l.id === s.lote_id)).forEach((s) => {
      const destino = s.estado === "planificada" ? pendientes : totales;
      destino[claveVariedad(s)] = (destino[claveVariedad(s)] || 0) + s.superficie;
    });
    const claves = [...new Set([...Object.keys(totales), ...Object.keys(pendientes)])].sort();
    if (!claves.length) return h("p", { class: "vacio-texto" }, "No hay siembras en esta campaña.");
    return h("ul", { class: "leyenda-mapa" }, claves.map((k) =>
      h("li", {}, h("i", { style: "background:" + colores[k] }), h("span", {}, k),
        h("strong", {}, totales[k] ? fmt.format(totales[k]) + " ha" : "",
          pendientes[k] ? h("small", { class: "pendiente-ha" }, (totales[k] ? " + " : "") + fmt.format(pendientes[k]) + " ha pend.") : ""))));
  }

  function panelInicio() {
    limpiarEdicion();
    const visibles = lotesVisibles();
    const dibujados = visibles.filter((l) => l.geometria);
    const sinDibujar = visibles.filter((l) => !l.geometria);
    const totalHa = dibujados.reduce((a, l) => a + l.superficie, 0);
    const contenido = [
      h("h2", {}, "Campaña " + (selCampana.selectedOptions[0] ? selCampana.selectedOptions[0].textContent : "")),
      h("p", { class: "ayuda" }, `${dibujados.length} lotes en el mapa · ${fmt.format(totalHa)} ha. Tocá un lote o un sector para ver su información.`),
      h("h3", {}, "Variedades sembradas"), leyenda(),
    ];
    if (!dibujados.length) {
      contenido.unshift(mensaje("Todavía no hay lotes dibujados. Buscá tu campo en el mapa (con el zoom o «Mi ubicación») y tocá «Dibujar lote».", "info"));
    }
    const pendientes = DATOS.siembras.filter((s) => s.estado === "planificada" && visibles.some((l) => l.id === s.lote_id));
    if (pendientes.length) {
      contenido.push(h("h3", {}, `Pendientes de siembra (${pendientes.length})`));
      contenido.push(h("ul", { class: "lista-simple" }, pendientes.map((s) => {
        const l = DATOS.lotes.find((x) => x.id === s.lote_id);
        return h("li", {}, h("span", {}, `${l.nombre} · ${s.variedad}`, h("br"),
          h("small", {}, `${fmt.format(s.superficie)} ha · prevista ${fecha(s.fecha_siembra)}`)),
          boton("Ver", () => seleccionarLote(l, s)));
      })));
    }
    if (sinDibujar.length) {
      contenido.push(h("h3", {}, "Lotes sin dibujar"));
      contenido.push(h("ul", { class: "lista-simple" }, sinDibujar.map((l) =>
        h("li", {}, h("span", {}, `${l.finca} · ${l.nombre}`, h("br"), h("small", {}, fmt.format(l.superficie) + " ha")),
          CFG.puedeEditar ? boton("Dibujar", () => asistenteDibujo(l)) : ""))));
    }
    mostrarPanel(...contenido);
  }

  function datosLote(l) {
    const enCaminos = (l.caminos || []).reduce((a, c) => a + c.superficie, 0);
    return h("dl", { class: "datos datos-mapa" },
      h("div", { class: "dato" }, h("dt", {}, "Superficie"), h("dd", {}, fmt.format(l.superficie) + " ha")),
      h("div", { class: "dato" }, h("dt", {}, "Sembrable (sin caminos)"), h("dd", {}, fmt.format(l.superficie - enCaminos) + " ha")),
      h("div", { class: "dato" }, h("dt", {}, "Forma"), h("dd", {}, { circulo: "Pivote (círculo)", rectangulo: "Rectángulo", poligono: "Polígono" }[l.forma] || "—")),
      l.forma === "circulo" && l.geometria ? h("div", { class: "dato" }, h("dt", {}, "Radio / diámetro"),
        h("dd", {}, `${fmt0.format(l.geometria.properties.radio)} m / ${fmt0.format(l.geometria.properties.radio * 2)} m`)) : "",
      h("div", { class: "dato" }, h("dt", {}, "Gastos de la campaña"), h("dd", {}, moneda(l.gastos))),
      h("div", { class: "dato" }, h("dt", {}, "Cosechado"), h("dd", {}, l.cosechado ? fmt.format(l.cosechado) : "—")));
  }

  function tarjetaSiembra(s, destacada, l) {
    const extra = [];
    const pendiente = s.estado === "planificada";
    if (s.distancia_surcos) {
      extra.push(`surcos a ${fmt.format(s.distancia_surcos * 100)} cm`);
      if (s.geometria && s.orientacion_surcos !== null) extra.push(`≈ ${fmt0.format(lineasSurcos(s.geometria, s.orientacion_surcos, s.distancia_surcos, 1).cantidad)} surcos`);
    }
    if (s.geometria && s.geometria.properties.ancho) extra.push(`franja de ${fmt0.format(s.geometria.properties.ancho)} m de ancho`);
    if (s.superficie_caminos) extra.push(`${fmt.format(s.superficie_caminos)} ha de caminos descontadas`);
    const zonaForm = h("div", { class: "sector-form" });
    const editar = CFG.puedeEditarSiembra;
    const tarjeta = h("div", { class: "sector-tarjeta" + (destacada ? " destacada" : "") + (pendiente ? " pendiente" : "") },
      h("div", { class: "sector-titulo" }, h("i", { style: "background:" + (colores[claveVariedad(s)] || "#888") }),
        h("strong", {}, `${s.cultivo} · ${s.variedad}`), h("span", { class: "badge badge-" + s.estado }, ESTADOS[s.estado] || s.estado)),
      h("p", { class: "ayuda" }, (pendiente ? `${fmt.format(s.superficie)} ha · siembra prevista ${fecha(s.fecha_siembra)}`
        : `${fmt.format(s.superficie)} ha sembradas el ${fecha(s.fecha_siembra)}`) +
        (s.fecha_cosecha_estimada ? ` · cosecha est. ${fecha(s.fecha_cosecha_estimada)}` : "") +
        (s.origen_semilla === "propia" ? ` · semilla propia${s.semilla ? ": " + s.semilla : ""}`
          : s.origen_semilla === "comprada" || s.semilla ? ` · semilla comprada${s.semilla ? ": " + s.semilla : ""}${s.costo_semilla ? " (" + moneda(s.costo_semilla) + ")" : ""}` : "") +
        (s.rendimiento_estimado ? ` · estimado ${fmt0.format(s.rendimiento_estimado * s.superficie)} ${s.unidad}` : "")),
      extra.length ? h("p", { class: "ayuda" }, extra.join(" · ")) : "",
      h("div", { class: "acciones-sector" },
        pendiente && editar ? boton("Marcar como sembrado", () => formSembrar(s, l, zonaForm), "btn-primario") : "",
        CFG.puedeCosechar && s.estado === "en_curso" ? enlace("Registrar cosecha", s.url_cosecha, "btn-primario") : "",
        enlace("Ver siembra", s.url),
        editar ? enlace("Editar datos", s.url_editar) : "",
        editar && s.geometria ? boton("Ajustar forma", () => asistenteForma(s, l)) : "",
        !pendiente ? enlace("Aplicación", s.url_aplicacion) : "", !pendiente ? enlace("Trabajo", s.url_trabajo) : "",
        editar && s.estado === "en_curso" ? boton("Volver a pendiente", async () => {
          if (!window.confirm("¿Pasar este sector a «pendiente de siembra»? La semilla vuelve al stock y se quita su costo.")) return;
          const r = await enviar(`${CFG.urls.siembras}/${s.id}/pendiente`);
          if (r.ok) { CFG.lote = l.id; cargar(false); } else alertaPanel(r.error);
        }, "btn-fantasma-oscuro") : "",
        CFG.puedeEliminarSiembra ? boton("Eliminar", async () => {
          if (!window.confirm(`¿Eliminar el sector ${s.variedad} (${fmt.format(s.superficie)} ha)? Se borra la siembra, su costo de semilla y su movimiento de stock.`)) return;
          const r = await enviar(`${CFG.urls.siembras}/${s.id}/eliminar`);
          if (r.ok) { CFG.lote = l.id; await cargar(false); panel.prepend(mensaje("Sector eliminado.", "exito")); } else alertaPanel(r.error);
        }, "btn-peligro") : ""),
      zonaForm);
    return tarjeta;
  }

  /* Semilla: propia (guardada de sus cosechas, sin precio) o comprada (con precio) */
  const nombreCultivo = (id) => { const c = CFG.cultivos.find((x) => String(x.id) === String(id)); return c ? c.nombre : ""; };
  function origenSugerido(cultivo) {
    const clave = (cultivo || "").toLowerCase().split(" ")[0];
    return clave && CFG.semillas.some((x) => x.propia && x.base.toLowerCase().includes(clave)) ? "propia" : "comprada";
  }
  function bloqueSemilla(prev, cultivo) {
    prev = prev || {};
    const origen = select([{ id: "propia", nombre: "Propia (nuestra, sin precio)" }, { id: "comprada", nombre: "Comprada (con precio)" }],
      prev.origen || origenSugerido(cultivo));
    origen.classList.add("s-origen");
    origen.dataset.auto = prev.origen ? "0" : "1";
    const semilla = h("select", { class: "s-semilla" });
    const cantidad = h("input", { class: "s-cantidad", type: "text", inputmode: "decimal", placeholder: "kg", value: prev.cantidad || "" });
    const costo = h("input", { class: "s-costo", type: "text", inputmode: "decimal", placeholder: "$ total", value: prev.costo || "" });
    const campoCosto = campo("Precio de la semilla comprada $", costo);
    const nota = h("small", { class: "ayuda s-nota" });
    let cultivoActual = cultivo;
    function opciones(valor) {
      const propia = origen.value === "propia";
      if (!valor && propia) { // sugiere la semilla propia de ese cultivo (ej. «Semilla de papa propia»)
        const clave = (cultivoActual || "").toLowerCase().split(" ")[0];
        const sug = clave && CFG.semillas.find((x) => x.propia && x.base.toLowerCase().includes(clave));
        if (sug) valor = sug.id;
      }
      const lista = CFG.semillas.filter((x) => !!x.propia === propia);
      semilla.replaceChildren(h("option", { value: "" }, propia ? "— No controlar stock —" : "— Comprada aparte (cargo el precio) —"),
        ...lista.map((o) => { const op = h("option", { value: o.id }, o.nombre); if (String(o.id) === String(valor)) op.selected = true; return op; }));
    }
    function refrescar() {
      const propia = origen.value === "propia";
      campoCosto.classList.toggle("oculto", propia || !!semilla.value);
      if (propia) costo.value = "";
      nota.textContent = propia ? "Semilla propia: se registra la cantidad usada y no suma costo."
        : semilla.value ? "Sale del galpón: el costo se calcula con el precio promedio de compra." : "Cargá el precio total que pagaste por esta semilla.";
    }
    origen.addEventListener("change", () => { origen.dataset.auto = "0"; opciones(""); refrescar(); });
    semilla.addEventListener("change", refrescar);
    opciones(prev.semilla);
    refrescar();
    const bloque = h("div", { class: "semilla-bloque" }, campo("Origen de la semilla", origen), campo("Semilla del galpón", semilla),
      campo("Cantidad de semilla", cantidad), campoCosto, nota);
    bloque._cambiarCultivo = (c) => { cultivoActual = c; if (origen.dataset.auto === "1") { origen.value = origenSugerido(c); opciones(""); refrescar(); } };
    return bloque;
  }
  const leerSemilla = (el) => ({ origen_semilla: el.querySelector(".s-origen").value, insumo_id: el.querySelector(".s-semilla").value,
    cantidad_semilla: el.querySelector(".s-cantidad").value, costo_semilla: el.querySelector(".s-origen").value === "propia" ? "" : el.querySelector(".s-costo").value });

  /* Un sector pendiente se siembra (cualquier día): fecha real + semilla usada */
  function formSembrar(s, l, zona) {
    const f = h("input", { type: "date", value: CFG.hoy, max: CFG.hoy });
    const variedad = h("input", { type: "text", maxlength: 60, value: s.variedad === "Sin variedad" ? "" : s.variedad });
    const bloque = bloqueSemilla({ origen: s.origen_semilla, semilla: s.insumo_id, cantidad: s.cantidad_semilla ? fmt.format(s.cantidad_semilla) : "" }, s.cultivo);
    const guardar = boton("Confirmar siembra", async () => {
      guardar.disabled = true;
      const r = await enviar(`${CFG.urls.siembras}/${s.id}/sembrar`, Object.assign({ fecha_siembra: f.value, variedad: variedad.value }, leerSemilla(bloque)));
      guardar.disabled = false;
      if (!r.ok) { zona.prepend(mensaje(r.error, "aviso")); return; }
      CFG.lote = l.id;
      await cargar(false);
      panel.prepend(mensaje(`Sector marcado como sembrado el ${fecha(f.value)}` + (r.costo ? ` · costo de semilla ${moneda(r.costo)}.` : "."), "exito"));
    }, "btn-primario");
    zona.replaceChildren(h("h4", {}, "¿Cuándo se sembró?"),
      h("div", { class: "form-grid" }, campo("Fecha de siembra", f), campo("Variedad", variedad)), bloque,
      h("div", { class: "form-acciones" }, guardar, boton("Cancelar", () => zona.replaceChildren())));
    f.focus();
  }

  /* Ajustar el dibujo de un sector ya cargado (mover puntos o el borde) */
  function asistenteForma(s, l) {
    limpiarEdicion();
    const forma = s.geometria.geometry.type === "Point" ? "circulo" : (s.geometria.properties.forma || "sector");
    const capa = capaDeFeature(s.geometria, { color: "#ffdd00", weight: 3, fillColor: colores[claveVariedad(s)] || "#888", fillOpacity: 0.35 });
    capaEdicion.addLayer(capa);
    capa.pm.enable({ allowSelfIntersection: false });
    const info = h("p", { class: "area-dibujo" });
    function actualizar() {
      const f = featureDeCapa(capa, forma), bruta = ha(areaFeature(f)), cam = ha(caminosEnM2(f, l.caminos));
      info.replaceChildren(h("strong", {}, `${fmt.format(Math.max(bruta - cam, 0))} ha sembrables`),
        cam > 0.005 ? ` (${fmt.format(bruta)} ha − ${fmt.format(cam)} ha de caminos)` : "", ` · antes: ${fmt.format(s.superficie)} ha`);
    }
    capa.on("pm:edit pm:markerdrag pm:vertexadded pm:vertexremoved pm:change", actualizar);
    actualizar();
    mapa.fitBounds(limites(l.geometria).pad(0.2), { maxZoom: 17 });
    const guardar = boton("Guardar forma", async () => {
      guardar.disabled = true;
      const r = await enviar(`${CFG.urls.siembras}/${s.id}/forma`, { geometria: featureDeCapa(capa, forma) });
      guardar.disabled = false;
      if (!r.ok) { alertaPanel(r.error); return; }
      limpiarEdicion();
      CFG.lote = l.id;
      await cargar(false);
      (r.avisos || []).forEach(alertaPanel);
      panel.prepend(mensaje(`Forma guardada: ${fmt.format(r.superficie)} ha.`, "exito"));
    }, "btn-primario");
    mostrarPanel(
      h("h2", {}, `Ajustar sector: ${s.variedad}`), h("p", { class: "subtitulo" }, `${l.nombre} · ${l.finca}`),
      h("p", { class: "ayuda" }, "Arrastrá los puntos amarillos para mover los bordes (tocá un punto intermedio para agregar una esquina). Las hectáreas y el costo se recalculan al guardar."),
      info, h("div", { class: "form-acciones" }, guardar, boton("Cancelar", () => { limpiarEdicion(); seleccionarLote(l, s); })));
    ocupado = true;
  }

  function listaCaminos(l) {
    const caminos = l.caminos || [];
    return [
      h("h3", {}, caminos.length ? `Caminos (${caminos.length})` : "Caminos"),
      caminos.length ? h("ul", { class: "lista-simple" }, caminos.map((c) => h("li", {},
        h("span", {}, c.nombre, h("br"), h("small", {}, `${fmt0.format(c.longitud)} m de largo × ${fmt.format(c.ancho)} m · ${fmt.format(c.superficie)} ha`)),
        CFG.puedeEditar ? boton("Quitar", async () => {
          if (!window.confirm(`¿Quitar el camino «${c.nombre}»?`)) return;
          const r = await enviar(`${CFG.urls.caminos}/${c.id}/eliminar`);
          if (r.ok) { CFG.lote = l.id; cargar(false); } else alertaPanel(r.error);
        }, "btn-peligro") : ""))) : h("p", { class: "ayuda" }, "Marcá los caminos internos: su superficie se descuenta de lo sembrado."),
      CFG.puedeEditar && l.geometria ? boton("+ Marcar camino", () => asistenteCamino(l)) : "",
    ];
  }

  function seleccionarLote(l, siembraDestacada) {
    limpiarEdicion();
    const siembras = siembrasDe(l.id);
    if (l.geometria) mapa.fitBounds(limites(l.geometria).pad(0.3), { maxZoom: 17 });
    const acciones = h("div", { class: "acciones-lote" },
      CFG.puedeSembrar && l.geometria ? boton("Sembrar por sectores", () => asistenteSectores(l), "btn-primario") : "",
      CFG.puedeEditar ? boton(l.geometria ? "Editar forma" : "Dibujar", () => asistenteDibujo(l)) : "",
      CFG.puedeEditar && l.geometria ? boton("Quitar del mapa", async () => {
        if (!window.confirm(`¿Quitar el dibujo de ${l.nombre}? El lote y sus datos no se borran.`)) return;
        const r = await enviar(`${CFG.urls.guardarLote}/${l.id}/quitar`);
        if (r.ok) cargar(false); else alertaPanel(r.error);
      }, "btn-peligro") : "",
      enlace("Ficha del lote", l.url));
    mostrarPanel(
      boton("← Volver", panelInicio, "btn-fantasma-oscuro"),
      h("h2", {}, `${l.nombre}`), h("p", { class: "subtitulo" }, l.finca),
      datosLote(l), acciones,
      h("h3", {}, siembras.length ? `Siembras (${siembras.length})` : "Sin siembras en esta campaña"),
      siembras.map((s) => tarjetaSiembra(s, siembraDestacada && s.id === siembraDestacada.id, l)),
      listaCaminos(l));
  }

  /* ------------------------------------------------------------ asistente: marcar un camino */
  function asistenteCamino(l) {
    limpiarEdicion();
    let capa = null;
    const nombre = h("input", { type: "text", maxlength: 60, value: `Camino ${(l.caminos || []).length + 1}` });
    const ancho = h("input", { type: "text", inputmode: "decimal", value: "4" });
    const info = h("p", { class: "area-dibujo" }, "Tocá el inicio del camino, después cada curva o quiebre, y tocá de nuevo el último punto para terminar.");
    const btnGuardar = boton("Guardar camino", guardar, "btn-primario");
    btnGuardar.disabled = true;
    const numero = (t) => parseFloat(String(t).replace(/\./g, "").replace(",", ".")) || 0;
    function feature() {
      const pts = capa.getLatLngs().map((p) => [p.lng, p.lat]);
      return { type: "Feature", geometry: { type: "LineString", coordinates: pts }, properties: { forma: "camino" } };
    }
    function actualizar() {
      if (!capa) return;
      const f = feature(), largo = longitudLinea(f), dentro = longitudDentro(f, l.geometria), w = numero(ancho.value);
      capa.setStyle({ weight: Math.max(3, w / metrosPorPixel()), color: "#c8a46b", opacity: 0.95 });
      info.replaceChildren(h("strong", {}, `${fmt0.format(largo)} m de largo`), ` · ${fmt.format((dentro * w) / 10000)} ha dentro del lote. Podés mover los puntos.`);
      btnGuardar.disabled = !(w > 0);
    }
    ancho.addEventListener("input", actualizar);
    mapa.off("pm:create");
    mapa.on("pm:create", (e) => {
      const nueva = e.layer;
      setTimeout(() => { capa = nueva; capaEdicion.addLayer(capa); capa.pm.enable(); capa.on("pm:edit pm:markerdrag pm:vertexadded pm:vertexremoved", actualizar); actualizar(); }, 0);
    });
    mapa.pm.enableDraw("Line", { pathOptions: { color: "#c8a46b", weight: 4 } });
    async function guardar() {
      const r = await enviar(CFG.urls.caminos, { lote_id: l.id, nombre: nombre.value, ancho: ancho.value, geometria: feature() });
      if (!r.ok) { alertaPanel(r.error); return; }
      limpiarEdicion();
      CFG.lote = l.id;
      await cargar(false);
      panel.prepend(mensaje(`Camino guardado: ${fmt0.format(r.longitud)} m · ${fmt.format(r.superficie)} ha.`, "exito"));
    }
    mostrarPanel(
      h("h2", {}, `Marcar camino en ${l.nombre}`),
      h("div", { class: "form-grid" }, campo("Nombre", nombre), campo("Ancho (metros)", ancho)),
      info, h("div", { class: "form-acciones" }, btnGuardar, boton("Cancelar", () => { limpiarEdicion(); seleccionarLote(l); })));
    ocupado = true;
  }

  function seleccionarSiembra(s, l) { seleccionarLote(l, s); }

  /* ------------------------------------------------------------ asistente: dibujar o editar un lote */
  function asistenteDibujo(loteExistente) {
    limpiarEdicion();
    mapa.pm.disableDraw();
    let capa = null;
    let forma = loteExistente && loteExistente.forma || null;
    const infoArea = h("p", { class: "area-dibujo" }, "Elegí la forma y dibujala sobre el mapa.");
    const inputHa = h("input", { type: "text", inputmode: "decimal", placeholder: "ej. 50" });
    const inputRadio = h("input", { type: "text", inputmode: "decimal", placeholder: "ej. 400" });
    const bloqueCirculo = h("div", { class: "form-grid oculto" }, campo("Hectáreas del pivote", inputHa), campo("Radio (metros)", inputRadio));
    const selFincaNueva = select(CFG.fincas, selFinca.value || (CFG.fincas[0] && CFG.fincas[0].id));
    const inputNombre = h("input", { type: "text", maxlength: 60, placeholder: "Ej: Pivote 1, Lote A" });
    const btnGuardar = boton("Guardar lote", guardar, "btn-primario");
    btnGuardar.disabled = true;

    function actualizarArea() {
      if (!capa) return;
      const f = featureDeCapa(capa, forma);
      const hect = ha(areaFeature(f));
      infoArea.replaceChildren(h("strong", {}, fmt.format(hect) + " ha"), " · podés mover los puntos para ajustar.");
      if (capa instanceof L.Circle) {
        bloqueCirculo.classList.remove("oculto");
        if (document.activeElement !== inputHa) inputHa.value = fmt.format(hect);
        if (document.activeElement !== inputRadio) inputRadio.value = fmt0.format(capa.getRadius());
      }
      btnGuardar.disabled = false;
    }
    const numero = (t) => parseFloat(String(t).replace(/\./g, "").replace(",", "."));
    inputHa.addEventListener("input", () => { const v = numero(inputHa.value); if (capa instanceof L.Circle && v > 0) { capa.setRadius(Math.sqrt((v * 10000) / Math.PI)); actualizarArea(); } });
    inputRadio.addEventListener("input", () => { const v = numero(inputRadio.value); if (capa instanceof L.Circle && v > 0) { capa.setRadius(v); actualizarArea(); } });

    function tomar(nueva) {
      if (capa) { if (capa.pm.enabled()) capa.pm.disable(); capaEdicion.removeLayer(capa); }
      capa = nueva;
      capaEdicion.addLayer(capa);
      capa.pm.enable({ allowSelfIntersection: false });
      capa.on("pm:edit pm:markerdrag pm:vertexadded pm:vertexremoved pm:centerplaced", actualizarArea);
      capa.on("pm:change", actualizarArea);
      actualizarArea();
    }
    function empezar(tipo) {
      forma = tipo;
      if (capa) { if (capa.pm.enabled()) capa.pm.disable(); capaEdicion.removeLayer(capa); capa = null; }
      bloqueCirculo.classList.add("oculto");
      mapa.pm.enableDraw({ circulo: "Circle", rectangulo: "Rectangle", poligono: "Polygon" }[tipo]);
      infoArea.textContent = { circulo: "Tocá el centro del pivote y después tocá el borde. Luego podés escribir las hectáreas exactas.",
        rectangulo: "Tocá una esquina y arrastrá hasta la esquina opuesta.",
        poligono: "Tocá cada esquina del lote. Para terminar tocá el primer punto." }[tipo];
    }
    mapa.off("pm:create");
    mapa.on("pm:create", (e) => { const nueva = e.layer; setTimeout(() => tomar(nueva), 0); });

    if (loteExistente && loteExistente.geometria) {
      tomar(capaDeFeature(loteExistente.geometria, { color: "#ffdd00", weight: 3, fillOpacity: 0.15 }));
      mapa.fitBounds(limites(loteExistente.geometria).pad(0.3));
    }

    async function guardar() {
      if (!capa) return;
      const datos = { geometria: featureDeCapa(capa, forma === "circulo" ? "circulo" : forma) };
      if (loteExistente) datos.lote_id = loteExistente.id;
      else { datos.finca_id = selFincaNueva.value; datos.nombre = inputNombre.value; }
      btnGuardar.disabled = true;
      const r = await enviar(CFG.urls.guardarLote, datos);
      btnGuardar.disabled = false;
      if (!r.ok) { alertaPanel(r.error); return; }
      limpiarEdicion();
      CFG.lote = r.lote_id;
      await cargar(false);
      (r.avisos || []).forEach(alertaPanel);
      panel.prepend(mensaje(`Lote guardado: ${fmt.format(r.superficie)} ha.`, "exito"));
    }
    function cancelar() { mapa.pm.disableDraw(); limpiarEdicion(); loteExistente ? seleccionarLote(loteExistente) : panelInicio(); }

    const formas = h("div", { class: "formas" },
      boton("◯ Pivote", () => empezar("circulo")), boton("▭ Rectángulo", () => empezar("rectangulo")), boton("⬠ Polígono", () => empezar("poligono")));
    mostrarPanel(
      h("h2", {}, loteExistente ? `Forma de ${loteExistente.nombre}` : "Dibujar un lote nuevo"),
      loteExistente ? h("p", { class: "subtitulo" }, loteExistente.finca) : h("div", { class: "form-grid" }, campo("Finca", selFincaNueva), campo("Nombre del lote", inputNombre)),
      h("p", { class: "ayuda" }, loteExistente && loteExistente.geometria ? "Mové los puntos para ajustar la forma, o elegí otra forma para dibujarla de nuevo:" : "¿Qué forma tiene?"),
      formas, infoArea, bloqueCirculo,
      h("div", { class: "form-acciones" }, btnGuardar, boton("Cancelar", cancelar)));
    ocupado = true;
  }
  const btnDibujar = document.getElementById("m-dibujar");
  if (btnDibujar) btnDibujar.addEventListener("click", () => asistenteDibujo(null));

  /* ------------------------------------------------------------ asistente: sembrar por sectores */
  function asistenteSectores(l) {
    limpiarEdicion();
    const esPivote = l.geometria.geometry.type === "Point";
    const numero = (t) => { const v = parseFloat(String(t || "").replace(/\./g, "").replace(",", ".")); return isNaN(v) ? 0 : v; };
    const selCamp = select(CFG.campanas, selCampana.value);
    const selCult = select(CFG.cultivos.map((c) => ({ id: c.id, nombre: `${c.nombre} (${c.unidad})` })), "", "— Elegir —");
    const fecha = h("input", { type: "date", value: CFG.hoy });
    const cosecha = h("input", { type: "date" });
    const rinde = h("input", { type: "text", inputmode: "decimal", placeholder: "ej. 30" });
    const surcos = h("input", { type: "text", inputmode: "decimal", placeholder: "ej. 75" });
    const direccion = select([{ id: "0", nombre: "Franjas verticales (norte – sur)" }, { id: "90", nombre: "Franjas horizontales (este – oeste)" },
      { id: "otro", nombre: "Franjas con otro ángulo" }].concat(esPivote ? [{ id: "gajos", nombre: "Gajos desde el centro" }] : []), "0");
    const angulo = h("input", { type: "number", min: 0, max: 179, value: 45 });
    const bloqueAngulo = campo("Ángulo de los surcos (grados desde el norte)", angulo);
    const modo = select([{ id: "m", nombre: "Metros de ancho" }, { id: "ha", nombre: "Hectáreas" }, { id: "pct", nombre: "Porcentaje" }], "m");
    const cantidad = h("select", {}, [1, 2, 3, 4, 5, 6, 8, 10].map((n) => h("option", { value: n }, n === 1 ? "1 (todo el lote)" : `${n} sectores`)));
    cantidad.value = "3";
    const infoAncho = h("p", { class: "ayuda" });
    const filas = h("div", { class: "filas-sectores" });
    const resumen = h("p", { class: "area-dibujo" });
    let sectores = [];

    const esGajos = () => direccion.value === "gajos";
    const anguloActual = () => (direccion.value === "otro" ? numero(angulo.value) : numero(direccion.value));
    const anchoTotal = () => franjas(l.geometria, { porcentajes: [1] }, anguloActual()).ancho_total;

    function valoresPorDefecto() {
      const n = parseInt(cantidad.value, 10);
      const inputs = [...filas.querySelectorAll(".s-medida")];
      const m = esGajos() ? "pct" : modo.value;
      const total = m === "m" ? anchoTotal() : m === "ha" ? l.superficie : 100;
      inputs.forEach((inp, i) => {
        const ultimo = i === n - 1 && m !== "pct";
        inp.readOnly = ultimo;
        inp.value = ultimo ? "resto" : fmt.format(m === "m" ? Math.round(total / n) : Math.round((total / n) * 100) / 100);
      });
      filas.querySelectorAll(".s-medida-etiqueta").forEach((e) => { e.textContent = m === "m" ? "Ancho (m)" : m === "ha" ? "Hectáreas" : "% del lote"; });
    }

    function crearFilas() {
      const n = parseInt(cantidad.value, 10);
      const previas = [...filas.children].map((f) => ({ variedad: f.querySelector(".s-variedad").value, semilla: f.querySelector(".s-semilla").value,
        origen: f.querySelector(".s-origen").dataset.auto === "1" ? null : f.querySelector(".s-origen").value,
        cantidad: f.querySelector(".s-cantidad").value, costo: f.querySelector(".s-costo").value,
        estado: f.querySelector(".s-estado").value, fecha: f.querySelector(".s-fecha").value, auto: f.querySelector(".s-fecha").dataset.auto }));
      filas.replaceChildren();
      for (let i = 0; i < n; i++) {
        const prev = previas[i] || {};
        filas.append(h("div", { class: "fila-sector" },
          h("span", { class: "s-color" }), h("strong", {}, `Sector ${i + 1}`),
          h("label", { class: "campo" }, h("span", { class: "s-medida-etiqueta" }, "Ancho (m)"), h("input", { class: "s-medida", type: "text", inputmode: "decimal" })),
          campo("Variedad / semilla", h("input", { class: "s-variedad", type: "text", maxlength: 60, placeholder: "Ej: Spunta", value: prev.variedad || "" })),
          campo("Estado", (() => { const e = select([{ id: "en_curso", nombre: "Sembrado" }, { id: "planificada", nombre: "Pendiente de siembra" }], prev.estado || "en_curso"); e.classList.add("s-estado"); return e; })()),
          campo("Fecha de siembra", h("input", { class: "s-fecha", type: "date", value: prev.fecha || fecha.value, "data-auto": prev.auto === undefined ? "1" : prev.auto })),
          bloqueSemilla(prev, nombreCultivo(selCult.value)),
          h("span", { class: "s-ha ayuda" })));
      }
      valoresPorDefecto();
      vistaPrevia();
    }

    function vistaPrevia() {
      limpiarEdicion();
      const n = parseInt(cantidad.value, 10);
      const ang = anguloActual();
      const medidas = [...filas.querySelectorAll(".s-medida")].map((i) => numero(i.value));
      const m = esGajos() ? "pct" : modo.value;
      bloqueAngulo.classList.toggle("oculto", direccion.value !== "otro");
      modo.closest(".campo").classList.toggle("oculto", esGajos());
      let error = null, total;
      if (n === 1) { sectores = [l.geometria]; }
      else if (esGajos()) { sectores = gajos(l.geometria, medidas, 0); }
      else {
        let r;
        if (m === "m") r = franjas(l.geometria, { anchos: medidas.slice(0, -1) }, ang);
        else if (m === "ha") {
          const usadas = medidas.slice(0, -1), resto = Math.max(l.superficie - usadas.reduce((a, b) => a + b, 0), 0);
          if (resto <= 0) error = "Las hectáreas indicadas superan la superficie del lote.";
          r = franjas(l.geometria, { porcentajes: usadas.concat([resto || 0.0001]) }, ang);
        } else r = franjas(l.geometria, { porcentajes: medidas }, ang);
        sectores = r.sectores;
        total = r.ancho_total;
        error = error || r.error;
      }
      infoAncho.textContent = !esGajos() && n > 1 ? `En esa dirección el lote mide ${fmt0.format(total || anchoTotal())} m de punta a punta.` : "";
      const variedades = [...filas.querySelectorAll(".s-variedad")].map((i) => i.value.trim() || "Sin variedad");
      const unicas = [...new Set(variedades)];
      const dist = numero(surcos.value) / 100;
      let totalBruto = 0, totalNeto = 0;
      sectores.forEach((f, i) => {
        const fila = filas.children[i];
        if (!fila) return;
        const color = PALETA[unicas.indexOf(variedades[i]) % PALETA.length];
        const bruta = ha(areaFeature(f)), enCaminos = ha(caminosEnM2(f, l.caminos)), neta = Math.max(bruta - enCaminos, 0);
        totalBruto += bruta; totalNeto += neta;
        const pend = fila.querySelector(".s-estado").value === "planificada";
        const capa = capaDeFeature(f, pend ? { color: color, weight: 2.5, dashArray: "8 6", fillColor: color, fillOpacity: 0.2 }
          : { color: "#fff", weight: 2, fillColor: color, fillOpacity: 0.6 });
        capa.bindTooltip(`Sector ${i + 1} · ${variedades[i]} · ${fmt.format(neta)} ha` + (pend ? " (pendiente)" : ""), { permanent: true, direction: "center", className: "etiqueta-sector" });
        capaEdicion.addLayer(capa);
        const partes = [`${fmt.format(neta)} ha sembrables`];
        if (enCaminos > 0.005) partes.push(`${fmt.format(bruta)} ha − ${fmt.format(enCaminos)} ha de caminos`);
        if (f.properties.ancho) partes.push(`${fmt0.format(f.properties.ancho)} m de ancho × ${fmt0.format(f._largo || 0)} m de largo máx.`);
        if (dist > 0 && !esGajos()) {
          const ls = lineasSurcos(f, ang, dist, 40);
          partes.push(`≈ ${fmt0.format(ls.cantidad)} surcos`);
          ls.lineas.forEach((ln) => capaEdicion.addLayer(L.polyline(ln, { color: "#fff", weight: 1, opacity: 0.5, interactive: false })));
        }
        fila.querySelector(".s-color").style.background = color;
        fila.querySelector(".s-ha").textContent = partes.join(" · ");
        const ultimo = fila.querySelector(".s-medida");
        if (ultimo.readOnly && i === n - 1) ultimo.value = m === "m" ? `resto (${fmt0.format(f.properties.ancho || 0)} m)` : `resto (${fmt.format(bruta)} ha)`;
      });
      resumen.replaceChildren(h("strong", {}, `${fmt.format(totalNeto)} ha a sembrar`),
        ` de ${fmt.format(l.superficie)} ha del lote` + (totalBruto - totalNeto > 0.005 ? ` (${fmt.format(totalBruto - totalNeto)} ha de caminos)` : ""));
      if (error) resumen.append(h("br"), h("span", { class: "negativo" }, error));
      btnGuardar.disabled = !!error;
    }
    filas.addEventListener("input", (e) => { if (e.target.classList.contains("s-medida") || e.target.classList.contains("s-variedad")) vistaPrevia(); });
    filas.addEventListener("change", (e) => {
      if (e.target.classList.contains("s-fecha")) e.target.dataset.auto = e.target.value === fecha.value ? "1" : "0";
      if (e.target.classList.contains("s-estado")) e.target.closest(".fila-sector").classList.toggle("pendiente", e.target.value === "planificada");
      vistaPrevia();
    });
    fecha.addEventListener("change", () => filas.querySelectorAll(".s-fecha").forEach((i) => { if (i.dataset.auto === "1") i.value = fecha.value; }));
    cantidad.addEventListener("change", crearFilas);
    [direccion, modo].forEach((c) => c.addEventListener("change", () => { valoresPorDefecto(); vistaPrevia(); }));
    angulo.addEventListener("input", () => { valoresPorDefecto(); vistaPrevia(); });
    surcos.addEventListener("input", vistaPrevia);
    selCult.addEventListener("change", () => filas.querySelectorAll(".semilla-bloque").forEach((b) => b._cambiarCultivo(nombreCultivo(selCult.value))));

    const btnGuardar = boton("Guardar siembras", async () => {
      const datos = {
        lote_id: l.id, campana_id: selCamp.value, cultivo_id: selCult.value, fecha_siembra: fecha.value,
        fecha_cosecha_estimada: cosecha.value, rendimiento_estimado: rinde.value,
        distancia_surcos: numero(surcos.value) ? String(numero(surcos.value) / 100) : "",
        orientacion: esGajos() ? null : anguloActual(),
        sectores: sectores.map((f, i) => {
          const fila = filas.children[i];
          const g = { type: "Feature", geometry: f.geometry, properties: Object.assign({}, f.properties) };
          return { geometria: g, variedad: fila.querySelector(".s-variedad").value, ...leerSemilla(fila),
            estado: fila.querySelector(".s-estado").value, fecha_siembra: fila.querySelector(".s-fecha").value || fecha.value };
        }),
      };
      if (!datos.cultivo_id) { alertaPanel("Elegí el cultivo."); return; }
      btnGuardar.disabled = true;
      const r = await enviar(CFG.urls.sectores, datos);
      btnGuardar.disabled = false;
      if (!r.ok) { alertaPanel(r.error); return; }
      limpiarEdicion();
      if (selCamp.value !== selCampana.value) selCampana.value = selCamp.value;
      CFG.lote = l.id;
      await cargar(false);
      panel.prepend(mensaje(`Se registraron ${r.siembras.length} sector(es) · ${fmt.format(r.neta)} ha.` +
        (r.pendientes ? ` ${r.pendientes} quedan pendientes de siembra: cuando se siembren, tocá el sector y «Marcar como sembrado».` : " Los costos de semilla ya se imputaron."), "exito"));
    }, "btn-primario");

    mapa.fitBounds(limites(l.geometria).pad(0.3), { maxZoom: 17 });
    mostrarPanel(
      boton("← Volver", () => { limpiarEdicion(); seleccionarLote(l); }, "btn-fantasma-oscuro"),
      h("h2", {}, `Sembrar ${l.nombre} por sectores`),
      siembrasDe(l.id).filter((x) => x.estado !== "cosechada" && x.estado !== "perdida").length
        ? mensaje(`Este lote ya tiene ${siembrasDe(l.id).length} siembra(s) en la campaña elegida en el mapa. Para cambiar un sector existente usá sus botones (Marcar como sembrado, Editar datos, Ajustar forma). Usá este asistente sólo para sectores nuevos.`, "aviso") : "",
      h("p", { class: "ayuda" }, "El lote se divide en franjas rectas con las medidas que indiques. Podés repetir una variedad en franjas distintas (ej. A · B · A). Los caminos marcados se descuentan solos. Si algún sector se siembra otro día, cambiale la fecha o dejalo «Pendiente de siembra» y marcalo después."),
      h("div", { class: "form-grid" }, campo("Campaña", selCamp), campo("Cultivo", selCult), campo("Fecha de siembra (general)", fecha),
        campo("Cosecha estimada", cosecha), campo("Rendimiento esperado por ha", rinde), campo("Distancia entre surcos (cm)", surcos),
        campo("Cantidad de sectores", cantidad), campo("Dirección", direccion), bloqueAngulo, campo("Medir cada sector en", modo)),
      infoAncho, resumen, filas,
      h("div", { class: "form-acciones" }, btnGuardar, boton("Cancelar", () => { limpiarEdicion(); seleccionarLote(l); })));
    ocupado = true;
    crearFilas();
  }

  /* ------------------------------------------------------------ eventos generales */
  selCampana.addEventListener("change", () => cargar(false));
  selFinca.addEventListener("change", () => { dibujar(true); panelInicio(); });
  cargar(true).then(etiquetas);
})();
