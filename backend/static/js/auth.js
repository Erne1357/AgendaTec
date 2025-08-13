(async () => {
  try {
    const r = await fetch("/auth/me", { credentials: "include" });
    if (r.ok) {
      const { user } = await r.json();
      if (user?.role === "student") window.location.href = "/student/home";
      else if (user?.role === "coordinator") window.location.href = "/coord/home";
      else if (user?.role === "social_service") window.location.href = "/social/home";
      else window.location.href = "/";
    }
  } catch {}
})();

(() => {
  const form = document.getElementById("loginForm");
  const btn = document.getElementById("btnLogin");
  const alertBox = document.getElementById("alertBox");

  function showError(msg) {
    alertBox.textContent = msg || "Error al iniciar sesión.";
    alertBox.classList.remove("d-none");
  }
  function hideError() {
    alertBox.classList.add("d-none");
    alertBox.textContent = "";
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideError();

    if (!form.checkValidity()) {
      form.classList.add("was-validated");
      return;
    }

    btn.disabled = true;
    btn.textContent = "Entrando...";

    const payload = {
      control_number: document.getElementById("control_number").value.trim(),
      nip: document.getElementById("nip").value.trim()
    };

    try {
      const res = await fetch("/auth/login", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        if (res.status === 400) showError("Formato inválido. Revisa tus datos.");
        else if (res.status === 401) showError("Credenciales incorrectas.");
        else showError("Ocurrió un error. Intenta de nuevo.");
        return;
      }

      const data = await res.json();
      const role = data?.user?.role;

      // Redirección por rol (placeholders)
      if (role === "student") window.location.href = "/student/home";
      else if (role === "coordinator") window.location.href = "/coord/home";
      else if (role === "social_service") window.location.href = "/social/home";
      else window.location.href = "/";

    } catch (err) {
      showError("No se pudo conectar con el servidor.");
    } finally {
      btn.disabled = false;
      btn.textContent = "Iniciar sesión";
    }
  });
})();
