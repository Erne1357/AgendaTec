// static/js/admin/home_pies.js
(() => {
  if (window.__homePiesMounted) return;
  window.__homePiesMounted = true;

  const $ = (s) => document.querySelector(s);
  const cfg = window.__adminDashboard || {};
  const piesUrl = cfg.piesUrl || "/api/v1/admin/stats/coordinators";

  if (!window.Chart) {
    console.warn("[home_pies] Chart.js no está cargado");
    return;
  }

  // Exponer recarga para que otras partes (tabs / rango / realtime) la usen
  window.__reloadPies = reloadPies;

  let chGlobal = null;
  const miniCharts = new Map();

  function buildQuery() {
    const q = new URLSearchParams();
    const from = $("#fltFrom")?.value;
    const to   = $("#fltTo")?.value;
    if (from) q.set("from", from);
    if (to)   q.set("to", to);
    if ($("#pieByDay")?.checked) q.set("by_day", "1");
    q.set("states", "1");
    return q.toString();
  }

  function as3Cat(totals) {
    return [
      { label: "Atendidas",    value: Number(totals?.attended   || 0) },
      { label: "Pendientes",   value: Number(totals?.pending    || 0) },
      { label: "No atendidas", value: Number(totals?.unattended || 0) },
    ];
  }
  function asStates(totals) {
    const st = totals?.states || {};
    return [
      { label: "Resueltas",     value: Number(st["RESOLVED_SUCCESS"]       || 0) },
      { label: "No resueltas",  value: Number(st["RESOLVED_NOT_COMPLETED"] || 0) },
      { label: "Otro horario",  value: Number(st["ATTENDED_OTHER_SLOT"]    || 0) },
      { label: "No asistió",    value: Number(st["NO_SHOW"]                || 0) },
      { label: "Canceladas",    value: Number(st["CANCELED"]               || 0) },
    ];
  }
  function sum(arr, key = "value") {
    return (arr || []).reduce((a, b) => a + Number(b?.[key] || 0), 0);
  }
  function debounce(fn, t) { let h; return (...a) => { clearTimeout(h); h = setTimeout(() => fn(...a), t); }; }
  function escapeHtml(s) {
    return (s || "")
      .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;").replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function destroyGlobal() { try { chGlobal?.destroy?.(); } catch {} chGlobal = null; }
  function destroyMiniCharts() { miniCharts.forEach(ch => { try { ch.destroy?.(); } catch {} }); miniCharts.clear(); }

  function drawGlobal(data, total) {
    destroyGlobal();
    const cv = $("#chCoordGlobal");
    if (!cv) return;
    // El contenedor tiene altura fija via CSS (.pieHost)
    chGlobal = new Chart(cv, {
      type: "pie",
      data: { labels: data.map(d => d.label), datasets: [{ data: data.map(d => d.value) }] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        resizeDelay: 120,
        plugins: { legend: { position: "bottom" } },
        animation: { duration: 250 }
      }
    });
    const lbl = $("#lblGlobalTotal");
    if (lbl) lbl.textContent = `Total: ${Number(total || 0)}`;
  }

  function drawMini(coordList, byDay, selectedDay, mode) {
    const grid = $("#miniPieGrid");
    if (!grid) return;
    destroyMiniCharts();
    grid.innerHTML = "";

    for (const c of (coordList || [])) {
      const totals = (!byDay || !selectedDay)
        ? c.totals
        : (c.days || []).find(x => x.day === selectedDay) || { total:0, pending:0, attended:0, unattended:0, states:{} };

      const data = (mode === "3cat") ? as3Cat(totals) : asStates(totals);
      const total = Number(totals?.total || sum(data));

      const col = document.createElement("div");
      col.className = "col-12 col-sm-6 col-md-4";
      col.innerHTML = `
        <div class="border rounded p-2 h-100">
          <div class="d-flex justify-content-between align-items-center mb-1">
            <strong class="text-truncate" title="${escapeHtml(c.coordinator_name || "—")}">${escapeHtml(c.coordinator_name || "—")}</strong>
            <small class="text-muted">#${c.coordinator_id}</small>
          </div>
          <div class="miniPieBox"><canvas id="miniPie-${c.coordinator_id}" style="width:100%; height:100%;"></canvas></div>
          <small class="text-muted">Total: ${total}</small>
        </div>`;
      grid.appendChild(col);

      const canvas = col.querySelector("canvas");
      const chart = new Chart(canvas, {
        type: "pie",
        data: { labels: data.map(d => d.label), datasets: [{ data: data.map(d => d.value) }] },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          resizeDelay: 120,
          plugins: { legend: { display: false } },
          animation: { duration: 250 }
        }
      });
      miniCharts.set(c.coordinator_id, chart);
    }
  }

  async function reloadPies() {
    try {
      const byDay = $("#pieByDay")?.checked;
      const mode = $("#pieMode")?.value || "3cat";
      const r = await fetch(`${piesUrl}?${buildQuery()}`, { credentials: "include" });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();

      // Selector de días
      const sel = $("#pieDay");
      let selectedDay = null;
      if (byDay) {
        const days = (j.overall_by_day || []).map(d => d.day);
        sel.hidden = days.length === 0;
        sel.innerHTML = days.map(d => `<option value="${d}">${d}</option>`).join("");
        if (!sel.value || !days.includes(sel.value)) sel.value = days[0] || "";
        selectedDay = sel.value || null;
      } else {
        sel.hidden = true; sel.innerHTML = "";
      }

      // Global
      let totalsGlobal = j.overall || { total:0, pending:0, attended:0, unattended:0, states:{} };
      if (byDay && selectedDay) {
        const dobj = (j.overall_by_day || []).find(x => x.day === selectedDay);
        totalsGlobal = dobj || totalsGlobal;
      }
      const dataGlobal = (mode === "3cat") ? as3Cat(totalsGlobal) : asStates(totalsGlobal);
      drawGlobal(dataGlobal, totalsGlobal?.total ?? sum(dataGlobal));

      // Por coordinador
      drawMini(j.coordinators || [], byDay, selectedDay, mode);

    } catch (e) {
      try { showToast?.("Error al cargar pasteles de coordinadores", "error"); } catch {}
      console.error("[home_pies] reload error:", e);
      destroyGlobal();
      destroyMiniCharts();
      const grid = $("#miniPieGrid");
      if (grid) grid.innerHTML = `<div class="text-muted small">No se pudo cargar.</div>`;
    }
  }

  // Controles (bind una sola vez)
  $("#btnPiesReload")?.addEventListener("click", reloadPies);
  $("#pieMode")?.addEventListener("change", reloadPies);
  $("#pieByDay")?.addEventListener("change", () => {
    const el = $("#pieDay");
    if (el) el.hidden = !$("#pieByDay").checked;
    reloadPies();
  });
  $("#pieDay")?.addEventListener("change", reloadPies);

  // Realtime (solo para pasteles)
  (function wireRealtime() {
    const tryBind = () => {
      const s = window.__reqSocket;
      if (!s) return setTimeout(tryBind, 400);
      const debounced = debounce(reloadPies, 600);
      s.off?.("appointment_created");
      s.off?.("request_status_changed");
      s.on("appointment_created", debounced);
      s.on("request_status_changed", debounced);
    };
    tryBind();
  })();

  // Importante: solo pinta si el tab de pasteles está visible
  const activeTabId = document.querySelector("#leftTabs .nav-link.active")?.id;
  if (activeTabId === "tabPieGlobal" || activeTabId === "tabPieMini") {
    reloadPies();
  }
})();
