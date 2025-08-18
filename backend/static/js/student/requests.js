// static/js/student/requests.js
(async () => {
  const panel = document.getElementById("reqPanel");
  try {
    const r = await fetch("/api/v1/requests/mine", { credentials: "include" });
    if (!r.ok) throw 0;
    const data = await r.json();
    let active = actActive(data.active);
    let history = data.history;
    let html = "";
    let day = getLabelDay(active);
    console.log("Day : ",day);
    if (active) {
      html += `<div class="mb-3">
        <div class="fw-semibold">Solicitud activa</div>
        <div class="small text-muted">${active.type} ${active.appointment ? day : ""}• ${active.appointment ? active.appointment.status : active.status}</div>
        ${active.type === "Cita" && active.appointment ? `
        <div class="small">Cita #${active.appointment.id} (slot ${active.appointment.slot_id})</div>` : ``}
        <div class="small text-muted">Creada el ${active.created_at}</div>
        <div class="small text-muted">${active.description || "Sin descripción"}</div>
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
  } catch (e) {
    panel.innerHTML = `<div class="text-muted">No se pudieron cargar tus solicitudes.</div>`;
    console.error("Error al cargar solicitudes:", e);
  }

  function actActive(active) {
    if (!active) return null;
    let { type, status, created_at, appointment } = active;
    switch (type) {
      case "APPOINTMENT":
        type = "CITA";
        break;
      case "DROP":
        type = "BAJA";
        break;
    }
    switch (status) {
      case "PENDING":
        status = "PENDIENTE";
        break;
      case "RESOLVED_ACCEPTED":
        status = "ATENDIDA Y RESUELTA";
        break;
      case "Resolved_NOT_COMPLETED":
        status = "ATENDIDA PERO NO RESUELTA";
        break;
      case "NO_SHOW":
        status = "NO ASISTIÓ";
        break;
      case "ATTENDED_OTHER_SLOT":
        status = "ASISTIÓ EN OTRO HORARIO";
        break;
      case "CANCELED":
        status = "CANCELADA";
        break;
    }
    created_at = new Date(created_at).toLocaleString("es-MX", {
      year: "numeric", month: "2-digit", day: "2-digit"
    });
    if (!appointment) {
      active = { type, status, created_at, description: active.description };
      return active;
    } else {
      let status_ap = active.appointment.status;
      switch (status_ap) {
        case "SCHEDULED":
          status_ap = "PROGRAMADA";
          break;
        case "DONE":
          status_ap = "CONCLUIDA";
          break;
        case "NO_SHOW":
          status_ap = "NO AISTIÓ";
          break;
        case "CANCELED":
          status_ap = "CANCELADA";
          break;
      }
      appointment.status = status_ap;
      active = { type, status, created_at, description: active.description, appointment };
      return active;
    }

  }
  function getLabelDay(active){
    if(!Boolean(active.appointment)) return "";
    return `el día ${active.appointment.slot.day} de ${active.appointment.slot.start_time} a ${active.appointment.slot.end_time}`;
  }
})();