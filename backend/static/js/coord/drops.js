// static/js/coord_drops.js
// Página: /coord/drops  → Listar drops y actualizar estado

(() => {
  const $ = (sel) => document.querySelector(sel);

  $("#btnLoadDrops").addEventListener("click", async () => {
    const status = $("#dropStatus").value;
    const url = new URL("/api/v1/coord/drops", window.location.origin);
    if (status) url.searchParams.set("status", status);

    try {
      const r = await fetch(url, { credentials: "include" });
      if (!r.ok) throw new Error();
      const data = await r.json();
      renderDrops(data.items || []);
    } catch {
      showToast("Error al cargar drops.", "error");
    }
  });

  function renderDrops(items) {
    const el = document.getElementById("dropList");
    if (!items.length) {
      el.innerHTML = `<div class="text-muted">Sin solicitudes.</div>`;
      return;
    }
    let html = `<table class="table table-sm table-striped align-middle">
      <thead><tr><th>ID</th><th>Estado</th><th>Creada</th><th class="text-end">Acciones</th></tr></thead><tbody>`;
    for (const it of items) {
      const created = it.created_at ? new Date(it.created_at).toLocaleString() : "-";
      html += `<tr>
        <td>#${it.id}</td>
        <td><span class="badge text-bg-secondary">${it.status}</span></td>
        <td>${created}</td>
        <td class="text-end">
          <div class="btn-group btn-group-sm">
            <button class="btn btn-outline-success" data-drop="${it.id}" data-st="RESOLVED_SUCCESS">RESUELTO</button>
            <button class="btn btn-outline-warning" data-drop="${it.id}" data-st="RESOLVED_NOT_COMPLETED">NO COMPLETADO</button>
            <button class="btn btn-outline-secondary" data-drop="${it.id}" data-st="NO_SHOW">NO_SHOW</button>
            <button class="btn btn-outline-info"     data-drop="${it.id}" data-st="ATTENDED_OTHER_SLOT">OTRO SLOT</button>
            <button class="btn btn-outline-danger"   data-drop="${it.id}" data-st="CANCELED">CANCELAR</button>
          </div>
        </td>
      </tr>`;
    }
    html += `</tbody></table>`;
    el.innerHTML = html;
  }

  document.addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-drop][data-st]");
    if (!btn) return;
    const id = btn.getAttribute("data-drop");
    const st = btn.getAttribute("data-st");
    if (!confirm(`¿Cambiar estado del DROP #${id} a ${st}?`)) return;

    try {
      const r = await fetch(`/api/v1/coord/requests/${id}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ status: st })
      });
      if (!r.ok) throw new Error();
      showToast("Estado de DROP actualizado.", "success");
      $("#btnLoadDrops").click(); // recargar lista
    } catch {
      showToast("No se pudo actualizar el DROP.", "error");
    }
  });

  // Carga inicial opcional
  try { $("#btnLoadDrops").click(); } catch {}
})();
