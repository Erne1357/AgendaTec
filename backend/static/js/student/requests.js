// static/js/student/requests.js
(async () => {
  const panel = document.getElementById("reqPanel");
  try {
    const r = await fetch("/api/v1/requests/mine", { credentials: "include" });
    if (!r.ok) throw 0;
    const data = await r.json();
    const { active, history } = data;
    let html = "";
    if (active) {
      html += `<div class="mb-3">
        <div class="fw-semibold">Solicitud activa</div>
        <div class="small text-muted">${active.type} • ${active.status}</div>
        ${active.type === "APPOINTMENT" && active.appointment ? `
        <div class="small">Cita #${active.appointment.id} (slot ${active.appointment.slot_id})</div>` : ``}
      </div>`;
    } else {
      html += `<div class="mb-3 text-muted">No tienes solicitud activa.</div>`;
    }
    html += `<div class="fw-semibold">Historial</div>`;
    if ((history || []).length === 0) html += `<div class="text-muted">Sin historial.</div>`;
    else {
      html += `<ul class="list-group">` +
        history.map(h => `<li class="list-group-item d-flex justify-content-between">
          <span>${h.type} • ${h.status}</span>
          <span class="text-muted small">${h.created_at}</span>
        </li>`).join("") + `</ul>`;
    }
    panel.innerHTML = html;
  } catch {
    panel.innerHTML = `<div class="text-muted">No se pudieron cargar tus solicitudes.</div>`;
  }
})();
xd