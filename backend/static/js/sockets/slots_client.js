// static/js/sockets/slots_client.js
// Paso 1: sólo conectar, join_day y escuchar hello/snapshot
(() => {
  if (!window.io) {
    console.warn("socket.io client no cargado");
    return;
  }

  // Conecta al namespace /slots (mismo host)
  const socket = io("/slots", {
    withCredentials: true, // incluye cookies para que el server lea agendatec_token
    transports: ["websocket"], // preferimos WS directo
  });

  window.__slotsSocket = socket; // útil en consola

  socket.on("connect", () => {
    console.log("[WS] conectado", socket.id);
  });

  socket.on("connect_error", (err) => {
    console.error("[WS] error", err?.message || err);
  });

  socket.on("hello", (payload) => {
    console.log("[WS] hello:", payload);
  });

  socket.on("joined_day", (p) => console.log("[WS] joined_day", p));
  socket.on("left_day",   (p) => console.log("[WS] left_day", p));
  socket.on("slots_snapshot", (p) => console.log("[WS] snapshot", p));

  // Helpers de prueba en consola:
  window.joinDay = (day) => socket.emit("join_day", { day });
  window.leaveDay = (day) => socket.emit("leave_day", { day });
})();
