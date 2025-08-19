// static/js/coord_home.js
(async () => {
    const modalEl = document.getElementById("forcePwModal");
    const newPw = document.getElementById("newPw");
    const btnSave = document.getElementById("btnSavePw");
    const pwErr = document.getElementById("pwErr");

    const modal = new bootstrap.Modal(modalEl, { backdrop: "static", keyboard: false });

    try {
        const r = await fetch("/api/v1/coord/password-state", { credentials: "include" });
        if (r.ok) {
            const { must_change } = await r.json();
            console.log("Must change: " + must_change);
            if (must_change) modal.show();
        }
    } catch { }

    btnSave.addEventListener("click", async () => {
        const v = (newPw.value || "").trim();
        if (!/^\d{4}$/.test(v)) {
            pwErr.classList.remove("d-none");
            return;
        }
        pwErr.classList.add("d-none");
        btnSave.disabled = true;

        try {
            const res = await fetch("/api/v1/coord/change_password", {
                method: "POST",
                credentials: "include",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ new_password: v })
            });
            if (!res.ok) throw 0;
            showToast("Contraseña actualizada.", "success");
            modal.hide();
            // Empuja al flujo de slots si así lo quieres:
            // window.location.href = "/coord/slots";
        } catch {
            showToast("No se pudo actualizar el NIP.", "error");
        } finally {
            btnSave.disabled = false;
            newPw.value = "";
        }
    });
})();
