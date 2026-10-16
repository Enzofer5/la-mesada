/* La Mesada · comportamiento de la interfaz (sin JavaScript en línea: compatible con CSP estricta). */
(function () {
  "use strict";

  const $ = (sel, raiz) => (raiz || document).querySelector(sel);
  const $$ = (sel, raiz) => Array.from((raiz || document).querySelectorAll(sel));
  const fmtNum = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 2 });
  const fmtMoneda = new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 });

  function aNumero(texto) {
    if (texto === null || texto === undefined) return 0;
    let t = String(texto).trim().replace(/\$/g, "").replace(/\s/g, "");
    if (t.includes(",")) t = t.replace(/\./g, "").replace(",", ".");
    const n = parseFloat(t);
    return isNaN(n) ? 0 : n;
  }

  /* ------------------------------------------------ menú lateral y mensajes */
  $$("[data-abrir-menu]").forEach((b) => b.addEventListener("click", () => document.body.classList.add("menu-abierto")));
  $$("[data-cerrar-menu]").forEach((b) => b.addEventListener("click", () => document.body.classList.remove("menu-abierto")));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") document.body.classList.remove("menu-abierto"); });
  $$("[data-cerrar-mensaje]").forEach((b) => b.addEventListener("click", () => b.closest(".mensaje").remove()));

  /* filas clickeables */
  $$("tr[data-href]").forEach((tr) => tr.addEventListener("click", (e) => {
    if (e.target.closest("a, button, input, select, form")) return;
    window.location.href = tr.dataset.href;
  }));

  /* confirmación antes de eliminar */
  $$("form[data-confirmar]").forEach((f) => f.addEventListener("submit", (e) => {
    if (!window.confirm(f.dataset.confirmar)) e.preventDefault();
  }));

  /* botón flotante de carga rápida */
  const fab = $("[data-fab]");
  if (fab) {
    const boton = $(".fab-boton", fab);
    const menu = $(".fab-menu", fab);
    boton.addEventListener("click", () => {
      menu.hidden = !menu.hidden;
      boton.setAttribute("aria-expanded", String(!menu.hidden));
    });
    document.addEventListener("click", (e) => { if (!fab.contains(e.target)) { menu.hidden = true; boton.setAttribute("aria-expanded", "false"); } });
  }

  /* números: sólo dígitos, coma, punto y signo */
  $$("input[data-numero]").forEach((i) => i.addEventListener("input", () => {
    const limpio = i.value.replace(/[^0-9.,-]/g, "");
    if (limpio !== i.value) i.value = limpio;
  }));

  /* ------------------------------------------------ selects dependientes (ej. lote según finca) */
  function filtrarDependiente(select, valorPadre) {
    const padres = JSON.parse(select.dataset.padres || "{}");
    let seleccionValida = false;
    Array.from(select.options).forEach((op) => {
      if (!op.value) return;
      const visible = !valorPadre || String(padres[op.value]) === String(valorPadre);
      op.hidden = !visible;
      op.disabled = !visible;
      if (visible && op.selected) seleccionValida = true;
    });
    if (!seleccionValida) select.value = "";
  }
  function enlazarDependientes(raiz) {
    $$("select[data-depende]", raiz).forEach((sel) => {
      const padre = sel.form && sel.form.elements[sel.dataset.depende];
      if (!padre) return;
      const aplicar = () => filtrarDependiente(sel, padre.value);
      padre.addEventListener("change", aplicar);
      aplicar();
    });
    $$("select[data-depende-filtro]", raiz).forEach((sel) => {
      const padre = sel.form && sel.form.elements[sel.dataset.dependeFiltro];
      if (!padre) return;
      const aplicar = () => filtrarDependiente(sel, padre.value);
      padre.addEventListener("change", aplicar);
      aplicar();
    });
  }
  enlazarDependientes(document);

  /* ------------------------------------------------ autocompletar (ej. siembra → finca, lote, cultivo) */
  $$("select[data-autocompleta]").forEach((sel) => {
    const datos = JSON.parse(sel.dataset.autocompleta || "{}");
    sel.addEventListener("change", () => {
      const extra = datos[sel.value];
      if (!extra) return;
      const orden = ["finca_id", "lote_id", "campana_id", "cultivo_id"];
      const claves = Object.keys(extra).sort((a, b) => (orden.indexOf(a) + 1 || 99) - (orden.indexOf(b) + 1 || 99));
      claves.forEach((campo) => {
        const el = sel.form.elements[campo];
        const valor = extra[campo];
        if (!el || valor === null || valor === undefined || valor === "") return;
        el.value = String(valor);
        el.dispatchEvent(new Event("change"));
      });
    });
  });

  /* ------------------------------------------------ trabajos: mostrar sólo el dato que corresponde a la forma de pago */
  const formTrabajo = $('form[data-form-crud="trabajos"]');
  if (formTrabajo) {
    const modalidad = formTrabajo.elements["modalidad"];
    const mapa = { hora: "horas", jornal: "jornales", unidad: "cantidad", monto_fijo: null };
    const aviso = document.createElement("p");
    aviso.className = "total-form";
    formTrabajo.querySelector(".form-acciones").before(aviso);
    const actualizar = () => {
      ["horas", "jornales", "cantidad"].forEach((c) => {
        const cont = formTrabajo.querySelector(`[data-campo="${c}"]`);
        if (cont) cont.classList.toggle("oculto", mapa[modalidad.value] !== c);
      });
      const campo = mapa[modalidad.value];
      const precio = aNumero(formTrabajo.elements["precio_unitario"].value);
      const cantidad = campo ? aNumero(formTrabajo.elements[campo].value) : 1;
      aviso.textContent = precio ? `Total a pagar: ${fmtMoneda.format(precio * cantidad)}` : "";
    };
    formTrabajo.addEventListener("input", actualizar);
    formTrabajo.addEventListener("change", actualizar);
    actualizar();
  }

  /* ------------------------------------------------ renglones de ventas y compras */
  $$("[data-renglones]").forEach((cont) => {
    const plantilla = document.getElementById(cont.dataset.renglones);
    const totalEl = document.getElementById(cont.dataset.total);
    const recalcular = () => {
      let total = 0;
      $$(".renglon", cont).forEach((r) => {
        const sub = aNumero($('[name="cantidad"]', r).value) * aNumero($('[name="precio_unitario"]', r).value);
        total += sub;
        const s = $(".subtotal", r);
        if (s) s.textContent = fmtMoneda.format(sub);
      });
      if (totalEl) totalEl.textContent = "Total: " + fmtMoneda.format(total);
    };
    const enlazar = (r) => {
      const quitar = $("[data-quitar]", r);
      if (quitar) quitar.addEventListener("click", () => {
        if ($$(".renglon", cont).length > 1) r.remove(); else $$("input", r).forEach((i) => { i.value = ""; });
        recalcular();
      });
      const cultivo = $('select[name="cultivo_id"]', r);
      const unidad = $('select[name="unidad_id"]', r);
      if (cultivo && unidad) cultivo.addEventListener("change", () => {
        const op = cultivo.selectedOptions[0];
        if (op && op.dataset.unidad && !unidad.value) unidad.value = op.dataset.unidad;
      });
      $$("input", r).forEach((i) => i.addEventListener("input", recalcular));
    };
    $$(".renglon", cont).forEach(enlazar);
    const agregar = document.querySelector(`[data-agregar="${cont.id}"]`);
    if (agregar && plantilla) agregar.addEventListener("click", () => {
      const nuevo = plantilla.content.firstElementChild.cloneNode(true);
      cont.appendChild(nuevo);
      enlazar(nuevo);
      const primero = $("select, input", nuevo);
      if (primero) primero.focus();
    });
    recalcular();
  });

  /* mostrar campos según forma de pago (ventas / compras / gastos) */
  $$("[data-mostrar-si]").forEach((el) => {
    const [campo, valores] = el.dataset.mostrarSi.split("=");
    const control = el.closest("form").elements[campo];
    if (!control) return;
    const lista = valores.split(",");
    const aplicar = () => el.classList.toggle("oculto", !lista.includes(control.value));
    control.addEventListener("change", aplicar);
    aplicar();
  });

  /* ------------------------------------------------ gráficos (Chart.js) */
  const COLOR_TEXTO = "#4d5647";
  const COLOR_GRILLA = "#e6e9dd";
  function crearGrafico(canvas) {
    if (typeof Chart === "undefined") return;
    const fuente = document.getElementById(canvas.dataset.grafico);
    if (!fuente) return;
    const cfg = JSON.parse(fuente.textContent);
    if (!cfg.labels || !cfg.labels.length) {
      canvas.parentElement.innerHTML = '<p class="vacio-texto">Sin datos para los filtros elegidos.</p>';
      return;
    }
    const esMoneda = !!cfg.moneda;
    const formatear = (v) => (esMoneda ? fmtMoneda.format(v) : fmtNum.format(v) + (cfg.unidad ? " " + cfg.unidad : ""));
    const horizontal = cfg.tipo === "barras_h";
    const datasets = cfg.series.map((s) => {
      const base = { label: s.nombre, data: s.datos };
      if (cfg.tipo === "linea") {
        return Object.assign(base, { borderColor: s.color, backgroundColor: s.color, borderWidth: 2, pointRadius: 3,
          pointHoverRadius: 5, tension: 0.25, fill: false });
      }
      if (cfg.tipo === "dona") {
        return Object.assign(base, { backgroundColor: s.colores, borderColor: "#ffffff", borderWidth: 2, hoverOffset: 4 });
      }
      const colores = s.colores || s.datos.map((v) => (s.color_negativo && v < 0 ? s.color_negativo : s.color));
      return Object.assign(base, { backgroundColor: colores, borderRadius: 4, borderSkipped: "start",
        maxBarThickness: 36, categoryPercentage: 0.7, barPercentage: 0.85 });
    });
    const multiples = cfg.series.length > 1 || cfg.tipo === "dona";
    const opciones = {
      responsive: true, maintainAspectRatio: false, indexAxis: horizontal ? "y" : "x",
      interaction: cfg.tipo === "linea" ? { mode: "index", intersect: false } : { mode: "nearest", intersect: true },
      plugins: {
        legend: { display: multiples, position: "bottom", labels: { color: COLOR_TEXTO, boxWidth: 12, boxHeight: 12, usePointStyle: true } },
        tooltip: { callbacks: { label: (ctx) => {
          const v = ctx.parsed && typeof ctx.parsed === "object" ? (horizontal ? ctx.parsed.x : ctx.parsed.y) : ctx.parsed;
          return `${ctx.dataset.label ? ctx.dataset.label + ": " : ""}${formatear(v)}`;
        } } },
      },
    };
    if (cfg.tipo !== "dona") {
      const ejeValor = { beginAtZero: true, grid: { color: COLOR_GRILLA }, border: { display: false },
        ticks: { color: COLOR_TEXTO, callback: (v) => (esMoneda ? abreviar(v) : fmtNum.format(v)) } };
      const ejeCat = { grid: { display: false }, ticks: { color: COLOR_TEXTO, autoSkip: true, maxRotation: 0 } };
      opciones.scales = horizontal ? { x: ejeValor, y: ejeCat } : { x: ejeCat, y: ejeValor };
    } else {
      opciones.cutout = "62%";
    }
    new Chart(canvas, { type: cfg.tipo === "linea" ? "line" : cfg.tipo === "dona" ? "doughnut" : "bar",
      data: { labels: cfg.labels, datasets }, options: opciones });
  }
  function abreviar(v) {
    const a = Math.abs(v);
    if (a >= 1e9) return "$ " + fmtNum.format(v / 1e9) + " mil M";
    if (a >= 1e6) return "$ " + fmtNum.format(v / 1e6) + " M";
    if (a >= 1e3) return "$ " + fmtNum.format(v / 1e3) + " mil";
    return "$ " + fmtNum.format(v);
  }
  $$("canvas[data-grafico]").forEach(crearGrafico);
})();
