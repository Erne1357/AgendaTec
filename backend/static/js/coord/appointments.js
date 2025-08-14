// static/js/coord_appointments.js
// Página: /coord/appointments  → Listar y cambiar estado de citas

(() => {
  const $ = (sel) => document.querySelector(sel);

  $("#btnLoadAppointments").addEventListener("click", async () => {
    const day = $("#apDay").value;
    const status = $("#apStatus").value;
    const url = new URL("/api/v1/coord/appointments", window.location.origin);
    url.searchParams.set("day", day);
    if (status) url.searchParams.set("status", status);

    try {
      const r = await fetch(url, { credentials: "include" });
      if (!r.ok) throw new Error();
      const data = await r.json();
      renderAppointments(data.items || []);
    } catch {
      showToast("Error al cargar citas.", "error");
    }
  });

  function renderAppointments(items) {
    const el = document.getElementById("apList");
    if (!items.length) {
      el.innerHTML = `<div class="text-muted">Sin citas.</div>`;
      return;
    }
    let html = `<table class="table table-sm table-striped align-middle">
      <thead>
        <tr><th>Hora</th><th>Programa</th><th>Estado</th><th class="text-end">Acciones</th></tr>
      </thead><tbody>`;
    for (const it of items) {
      html += `<tr>
        <td>${it.slot.start_time}–${it.slot.end_time}</td>
        <td>${it.program.name}</td>
        <td><span class="badge text-bg-secondary">${it.status}</span></td>
        <td class="text-end">
          <div class="btn-group btn-group-sm">
            <button class="btn btn-outline-success" data-ap="${it.appointment_id}" data-st="DONE">Marcar DONE</button>
            <button class="btn btn-outline-warning" data-ap="${it.appointment_id}" data-st="NO_SHOW">NO_SHOW</button>
            <button class="btn btn-outline-danger"  data-ap="${it.appointment_id}" data-st="CANCELED">Cancelar</button>
          </div>
        </td>
      </tr>`;
    }
    html += `</tbody></table>`;
    el.innerHTML = html;
  }

  document.addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-ap][data-st]");
    if (!btn) return;
    const apId = btn.getAttribute("data-ap");
    const st = btn.getAttribute("data-st");
    if (!confirm(`¿Cambiar estado a ${st}?`)) return;

    try {
      const r = await fetch(`/api/v1/coord/appointments/${apId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ status: st })
      });
      if (!r.ok) throw new Error();
      showToast("Estado actualizado.", "success");
      $("#btnLoadAppointments").click(); // recargar lista
    } catch {
      showToast("No se pudo actualizar el estado.", "error");
    }
  });

  // Carga inicial opcional
  try { $("#btnLoadAppointments").click(); } catch {}
})();
