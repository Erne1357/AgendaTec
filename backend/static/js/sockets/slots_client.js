// static/js/sockets/slots_client.js
// Cliente de WebSockets para slots - Versión corregida
(() => {
  if (!window.io) {
    console.warn("socket.io client no cargado");
    return;
  }

  // Evitar múltiples conexiones
  if (window.__slotsSocket) {
    console.log("[WS] Ya existe una conexión, reutilizando");
    return;
  }

  // Conecta al namespace /slots (mismo host)
  const socket = io("/slots", {
    withCredentials: true, // incluye cookies para que el server lea agendatec_token
    forceNew: false,
    reconnection: true,
    timeout: 20000,
  });

  window.__slotsSocket = socket; // útil en consola y para el request.js

  socket.on("connect", () => {
    console.log("[WS] conectado", socket.id);
  });

  socket.on("disconnect", (reason) => {
    console.log("[WS] desconectado:", reason);
  });

  socket.on("connect_error", (err) => {
    console.error("[WS] error de conexión:", err?.message || err);
  });

  socket.on("error", (err) => {
    console.error("[WS] error del servidor:", err);
  });

  socket.on("hello", (payload) => {
    console.log("[WS] hello:", payload);
  });

  socket.on("joined_day", (p) => {
    console.log("[WS] joined_day", p);
  });
  
  socket.on("left_day", (p) => {
    console.log("[WS] left_day", p);
  });
  
  socket.on("slots_snapshot", (p) => {
    console.log("[WS] snapshot", p);
  });

  socket.on("slot_held", (p) => {
    console.log("[WS] slot_held", p);
  });

  socket.on("slot_released", (p) => {
    console.log("[WS] slot_released", p);
  });

  socket.on("slot_booked", (p) => {
    console.log("[WS] slot_booked", p);
  });

  socket.on("hold_slot_ack", (p) => {
    console.log("[WS] hold_slot_ack", p);
  });

  socket.on("release_hold_ack", (p) => {
    console.log("[WS] release_hold_ack", p);
  });

  // Función helper para otros scripts
  window.__joinDay = (day) => {
    if (socket && socket.connected) {
      console.log(`[WS] Joining day: ${day}`);
      socket.emit("join_day", { day });
    } else {
      console.warn("[WS] Socket no conectado, no se puede hacer join_day");
    }
  };

  window.__leaveDay = (day) => {
    if (socket && socket.connected) {
      console.log(`[WS] Leaving day: ${day}`);
      socket.emit("leave_day", { day });
    }
  };

})();