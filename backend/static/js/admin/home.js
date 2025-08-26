// static/js/admin/home.js
(() => {
    const $ = (s) => document.querySelector(s);
    const cfg = window.__adminDashboard || {};
    const fetchUrl = cfg.fetchUrl || "/api/v1/admin/stats/overview";

    let chSeries;
    const stateMap = {
        PENDING: "#mPending",
        RESOLVED_SUCCESS: "#mSolved",
        RESOLVED_NOT_COMPLETED: "#mNotCompleted",
        NO_SHOW: "#mNoShow",
        ATTENDED_OTHER_SLOT: "#mOtherSlot",
        CANCELED: "#mCanceled",
    };

    // Rango por defecto: últimos 7 días
    function initDates() {
        const to = new Date();
        const from = new Date(Date.now() - 7 * 86400000);
        $("#fltTo").value = to.toISOString().slice(0, 10);
        $("#fltFrom").value = from.toISOString().slice(0, 10);
    }

    function qs() {
        const q = new URLSearchParams();
        const f = $("#fltFrom")?.value;
        const t = $("#fltTo")?.value;
        if (f) q.set("from", f);
        if (t) q.set("to", t);
        return q.toString();
    }

    async function loadOverview() {
        try {
            const r = await fetch(`${fetchUrl}?${qs()}`, { credentials: "include" });
            if (!r.ok) throw new Error("Bad response");
            const j = await r.json();

            // KPIs por estado
            const totals = Object.fromEntries(
                (j.totals || []).map((x) => [x.status, x.total])
            );
            for (const [st, sel] of Object.entries(stateMap)) {
                const v = totals[st] || 0;
                const el = $(sel);
                if (el) el.textContent = String(v);
            }

            // No-show rate
            $("#lblNoShowRate").textContent =
                (((j.no_show_rate || 0) * 100).toFixed(1) + "%");

            // Serie diaria
            const labels = (j.series || []).map((x) => x.day);
            const data = (j.series || []).map((x) => x.total);
            if (chSeries) chSeries.destroy?.();
            const ctx = $("#chSeries");
            if (ctx) {
                chSeries = new Chart(ctx, {
                    type: "line",
                    data: { labels, datasets: [{ label: "Solicitudes", data }] },
                    options: { responsive: true, maintainAspectRatio: false },
                });
            }
            console.log("Fetch: " + JSON.stringify(j));
            // Pendientes por coordinador
            const ul = $("#lstPendingByCoord");
            if (ul) {
                const combinedData = {};

                // 1. Llenar con datos de citas pendientes (pending_appointment)
                if (j.pending_appointment && Array.isArray(j.pending_appointment)) {
                    j.pending_appointment.forEach(x => {
                        combinedData[x.coordinator_id] = {
                            name: x.coordinator_name,
                            pending_app: x.pending,
                            pending_drop: 0 // Inicializa a 0 por si no hay bajas
                        };
                    });
                }

                // 2. Llenar con datos de bajas pendientes (pending_drop)
                if (j.pending_drop && Array.isArray(j.pending_drop)) {
                    j.pending_drop.forEach(x => {
                        // Si el coordinador ya existe, actualiza el valor de pending_drop
                        if (combinedData[x.coordinator_id]) {
                            combinedData[x.coordinator_id].pending_drop = x.pending;
                        } else {
                            // Si el coordinador no existe, lo agrega
                            combinedData[x.coordinator_id] = {
                                name: x.coordinator_name,
                                pending_app: 0, // Inicializa a 0 por si no hay citas
                                pending_drop: x.pending
                            };
                        }
                    });
                }

                // 3. Convierte el objeto a un array de valores
                const coordinators = Object.values(combinedData);

                // 4. Mapear y generar el HTML
                const items = coordinators.map(
                    (x) =>
                        `<li class="list-group-item d-flex justify-content-between align-items-center">
                            <span>${escapeHtml(x.name || "—")}</span>
                            <div>
                                <span class="badge text-bg-primary me-2">${x.pending_app || 0}</span>
                                <span class="badge text-bg-danger">${x.pending_drop || 0}</span>
                            </div>
                        </li>`
                ).join("");

                ul.innerHTML = items || `<li class="list-group-item text-muted">Sin pendientes.</li>`;
            }
        } catch (e) {
            showToast?.("Error al cargar estadísticas", "error");
            console.error(e);
        }
    }

    function escapeHtml(s) {
        return (s || "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    }

    // Wire time-range
    $("#btnApplyRange")?.addEventListener("click", loadOverview);

    // Realtime (reusar tu /requests socket)
    (function wireRealtime() {
        const tryBind = () => {
            const s = window.__reqSocket;
            if (!s) return setTimeout(tryBind, 400);

            const debounced = debounce(loadOverview, 500);
            s.off?.("appointment_created");
            s.off?.("drop_created");
            s.off?.("request_status_changed");

            s.on("appointment_created", () => debounced());
            s.on("drop_created", () => debounced());
            s.on("request_status_changed", () => debounced());
        };
        tryBind();
    })();

    function debounce(fn, wait) {
        let t;
        return (...args) => {
            clearTimeout(t);
            t = setTimeout(() => fn(...args), wait);
        };
    }

    initDates();
    loadOverview();
})();
