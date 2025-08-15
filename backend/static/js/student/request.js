// static/js/student_request.js

(() => {
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  const ALLOWED_DAYS = ["2025-08-25", "2025-08-26", "2025-08-27"];

  // State
  const state = {
    type: null,            // DROP | APPOINTMENT | BOTH
    program_id: null,
    day: null,
    slot_id: null,
  };

  // Elements
  const stepType = $("#stepType");
  const stepProgram = $("#stepProgram");
  const stepForms = $("#stepForms");
  const stepCalendar = $("#stepCalendar");
  const programSelect = $("#programSelect");
  const coordCard = $("#coordCard");
  const coordName = $("#coordName");
  const coordEmail = $("#coordEmail");
  const coordHours = $("#coordHours");
  const typeHint = $("#typeHint");

  const altaFields = $("#altaFields");
  const bajaFields = $("#bajaFields");
  const altaMateria = $("#altaMateria");
  const altaNoSe = $("#altaNoSe");
  const altaHorario = $("#altaHorario");
  const bajaMateria = $("#bajaMateria");
  const bajaHorario = $("#bajaHorario");

  const calendarBlock = $("#calendarBlock");
  const slotsWrap = $("#slotsWrap");
  const slotGrid = $("#slotGrid");

  const btnConfirmForms = $("#btnConfirmForms");
  const btnSubmit = $("#btnSubmit");
  const actionBar = $("#actionBar");


  // ------------- Paso 1: elegir tipo -------------
  $("[data-type='DROP']").addEventListener("click", () => chooseType("DROP"));
  $("[data-type='APPOINTMENT']").addEventListener("click", () => chooseType("APPOINTMENT"));
  $("[data-type='BOTH']").addEventListener("click", () => chooseType("BOTH"));

  function chooseType(t) {
    state.type = t;
    stepType.hidden = true;
    if (t === "DROP") {
      typeHint.textContent = "Solo se generará la solicitud de baja. Verifica tus créditos.";
    } else if (t === "APPOINTMENT") {
      typeHint.textContent = "Se agendará una cita con tu coordinador para alta.";
    } else {
      typeHint.textContent = "Se generará una solicitud y necesitarás cita para alta.";
    }

    stepProgram.hidden = false;
    loadPrograms();
    // Mostrar campos según tipo
    altaFields.hidden = (t === "DROP");
    bajaFields.hidden = (t === "APPOINTMENT");


    // Botonera de acción visible ya (en DROP, se permitirá enviar sin slot)
    actionBar.hidden = false;
    updateSubmitDisabled();
    animateEnter(calendarBlock, !stepCalendar.hidden);
  }

  // ------------- Paso 2: programas + coordinador -------------
  $("#btnReloadPrograms").addEventListener("click", loadPrograms);

  async function loadPrograms() {
    try {
      const r = await fetch("/api/v1/programs", { credentials: "include" });
      if (!r.ok) throw 0;
      const data = await r.json();
      programSelect.innerHTML = `<option value="">Selecciona...</option>` +
        (data.items || []).map(p => `<option value="${p.id}">${p.name}</option>`).join("");
    } catch {
      showToast("No se pudieron cargar los programas.", "error");
    }
  }

  programSelect.addEventListener("change", async (e) => {
    stepForms.hidden = false;
    btnConfirmForms.hidden = state.type === "DROP";
    const id = parseInt(e.target.value || "0", 10);
    state.program_id = Number.isFinite(id) && id > 0 ? id : null;
    coordCard.hidden = true;

    if (!state.program_id) { updateSubmitDisabled(); return; }
    try {
      const r = await fetch(`/api/v1/programs/${state.program_id}/coordinator`, { credentials: "include" });
      if (!r.ok) throw 0;
      const c = await r.json();
      coordName.textContent = c?.coordinators[0].full_name || "Coordinador";
      coordEmail.textContent = c?.coordinators[0].email || "";
      coordHours.textContent = c?.coordinators[0].office_hours || "";
      coordCard.hidden = false;
    } catch {
      showToast("No se pudo obtener el coordinador.", "warn");
    }
    updateSubmitDisabled();
  });

  // ------------- Paso 3: formularios Alta/Baja -------------
  altaNoSe.addEventListener("change", () => {
    altaMateria.disabled = altaNoSe.checked;
    if (altaNoSe.checked) altaMateria.value = "";
  });

  // ------------- Paso 4: calendario + slots -------------
    btnConfirmForms.addEventListener("click", () => {
        if( state.type != "DROP") {
        stepCalendar.hidden = false;
        stepForms.hidden = true;
        stepProgram.hidden = true;}
    });

  
  $$(".day-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const day = btn.getAttribute("data-day");
      if (!ALLOWED_DAYS.includes(day)) return;
      state.day = day;
      await loadSlots();
    });
  });

  $("#btnChangeDay").addEventListener("click",  () => {
    // “Elegir otro día”: resetea slots y vuelve a mostrar botones de día
    state.day = null;
    state.slot_id = null;
    slotsWrap.hidden = true;
    slotGrid.innerHTML = "";
    updateSubmitDisabled();
  });

  async function loadSlots() {
    if (!state.program_id || !state.day) return;
    try {
      const r = await fetch(`/api/v1/availability/program/${state.program_id}/slots?day=${state.day}`, {
        credentials: "include"
      });
      if (!r.ok) throw 0;
      const data = await r.json();
      console.log(data);
      renderSlots(data.items || []);
      // Animación al mostrar grid
      slotsWrap.hidden = false;
    } catch {
      showToast("No se pudieron cargar los horarios.", "error");
    }
  }

  function renderSlots(items) {
    console.log("items : " +items)
    state.slot_id = null;
    updateSubmitDisabled();

    if (!items.length) {
      slotGrid.innerHTML = `<div class="text-muted">No hay horarios disponibles para este día.</div>`;
      return;
    }
    slotGrid.innerHTML = "";
    items.forEach((s) => {
      const btn = document.createElement("button");
      btn.className = "btn btn-outline-secondary slot-btn";
      btn.textContent = s.start_time + " - "+ s.end_time;
      btn.dataset.slot = s.slot_id;
      btn.addEventListener("click", () => {
        // marcar seleccionado
        $$(".slot-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        state.slot_id = s.slot_id;
        updateSubmitDisabled();
      });
      slotGrid.appendChild(btn);
    });
  }

  // ------------- Envío -------------
  btnSubmit.addEventListener("click", async () => {
    if (!state.type) return;

    // Validaciones mínimas
    if (!state.program_id) { showToast("Selecciona tu carrera.", "warn"); return; }

    // Armar payloads informativos (nota: tus endpoints actuales para /requests
    // solo usan type, program_id y slot_id; estos campos extra puedes guardarlos
    // luego en una tabla de “request_details” si lo deseas).
    const altaInfo = {
      materia: altaNoSe.checked ? null : (altaMateria.value || null),
      no_se: !!altaNoSe.checked,
      horario: altaHorario.value || null
    };
    const bajaInfo = {
      materia: bajaMateria.value || null,
      horario: bajaHorario.value || null
    };

    let body;
    if (state.type === "DROP") {
      body = { type: "DROP" , program_id : state.program_id };
    } else {
      if (!state.day || !state.slot_id) {
        showToast("Selecciona un día y un horario.", "warn");
        return;
      }
      body = {
        type: "APPOINTMENT",
        program_id: state.program_id,
        slot_id: state.slot_id
      };
    }

    try {
      const r = await fetch("/api/v1/requests", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(body)
      });

      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        if (err.error === "already_has_pending") {
          showToast("Ya tienes una solicitud pendiente.", "warn");
        } else if (err.error === "slot_unavailable") {
          showToast("El horario ya no está disponible.", "warn");
        } else if (err.error === "slot_conflict") {
          showToast("Conflicto al reservar, intenta otro horario.", "warn");
        } else if (err.error === "day_not_allowed") {
          showToast("Ese día no está permitido.", "warn");
        } else {
          showToast("No se pudo crear la solicitud.", "error");
        }
        return;
      }

      // Éxito → redirigir a Mis solicitudes
      showToast("Solicitud creada correctamente.", "success");
      setTimeout(() => { window.location.href = "/student/requests"; }, 500);

    } catch {
      showToast("No se pudo conectar.", "error");
    }
  });

  function updateSubmitDisabled() {
    if (!state.type) { btnSubmit.disabled = true; return; }
    if (!state.program_id) { btnSubmit.disabled = true; return; }
    if (state.type === "DROP") { btnSubmit.disabled = false; return; }
    // Appointment / Both → necesita slot
    btnSubmit.disabled = !(state.day && state.slot_id);
  }

  // ------------- Animaciones helpers -------------
  function animateEnter(el, shouldAnimate) {
    if (!el || !shouldAnimate) return;
    el.classList.remove("expand-fade-exit", "expand-fade-exit-active");
    el.classList.add("expand-fade-enter");
    // force reflow
    void el.offsetWidth;
    el.classList.add("expand-fade-enter-active");
    setTimeout(() => {
      el.classList.remove("expand-fade-enter", "expand-fade-enter-active");
    }, 220);
  }
})();
