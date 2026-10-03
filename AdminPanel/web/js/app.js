/**
 * ASSETTO CORSA COMPETIZIONE — RACE CONTROL (frontend)
 * Estado reactivo, sondeo de la API REST e interacciones del panel. Vanilla JS, sin dependencias.
 */

document.addEventListener("DOMContentLoaded", () => {
  const $ = id => document.getElementById(id);

  // --- Token de acceso: se toma de la URL una vez y se guarda en la sesión del navegador ---
  const url = new URL(window.location.href);
  const tokenFromUrl = url.searchParams.get("token");
  if (tokenFromUrl) {
    sessionStorage.setItem("acc-panel-token", tokenFromUrl);
    url.searchParams.delete("token");
    window.history.replaceState({}, document.title, `${url.pathname}${url.search}${url.hash}`);
  }
  const panelToken = sessionStorage.getItem("acc-panel-token") || "";

  const POLL_INTERVAL_MS = 3000;
  const POLL_HIDDEN_INTERVAL_MS = 15000;
  const RANKING_LIMIT = 15;
  const SESSIONS_LIMIT = 12;

  const appState = {
    isRunning: false,
    unmanaged: false,
    currentTab: "tab-telemetry",
    configData: null,
    autoScrollLogs: true,
    rotationRequestPending: false,
    activePlayers: 0
  };

  // ==========================================================================
  // Helpers de formato
  // ==========================================================================
  function formatLapTime(ms) {
    if (!ms || ms <= 0 || ms >= 2147483647) return "—";
    const minutes = Math.floor(ms / 60000);
    const seconds = ((ms % 60000) / 1000).toFixed(3).padStart(6, "0");
    return `${minutes}:${seconds}`;
  }

  function formatUptime(seconds) {
    if (!seconds || seconds <= 0) return "00:00:00";
    const pad = value => String(Math.floor(value)).padStart(2, "0");
    return `${pad(seconds / 3600)}:${pad((seconds % 3600) / 60)}:${pad(seconds % 60)}`;
  }

  function formatResultDate(filename) {
    const match = /^(\d{2})(\d{2})(\d{2})_(\d{2})(\d{2})/.exec(String(filename || ""));
    return match ? `${match[3]}/${match[2]} ${match[4]}:${match[5]}` : "";
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>'"]/g, char => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
    }[char]));
  }

  function encodePayload(value) {
    const bytes = new TextEncoder().encode(JSON.stringify(value));
    let binary = "";
    bytes.forEach(byte => { binary += String.fromCharCode(byte); });
    return btoa(binary);
  }

  function decodePayload(value) {
    const bytes = Uint8Array.from(atob(value), char => char.charCodeAt(0));
    return JSON.parse(new TextDecoder().decode(bytes));
  }

  function steamProfileUrl(playerId) {
    const id = String(playerId || "").replace(/^S/, "");
    return /^\d{5,25}$/.test(id) ? `https://steamcommunity.com/profiles/${id}` : "#";
  }

  function sessionClass(value) {
    const normalized = String(value || "").toLowerCase();
    return ["p", "fp", "q", "r"].includes(normalized) ? normalized : "fp";
  }

  function percent(value) {
    return typeof value === "number" ? `${Math.round(value * 100)}%` : "—";
  }

  // Actualiza un texto y lo destaca brevemente si cambió (sin animar la primera carga).
  function setText(id, value) {
    const element = $(id);
    if (!element) return;
    const text = String(value);
    if (element.textContent === text) return;
    const hadValue = element.dataset.loaded === "1";
    element.textContent = text;
    element.dataset.loaded = "1";
    if (hadValue) {
      element.classList.remove("value-flash");
      void element.offsetWidth;
      element.classList.add("value-flash");
    }
  }

  function emptyState(title, text = "", variant = "") {
    return `
      <div class="empty-state ${variant}">
        <span class="empty-state-icon" aria-hidden="true"></span>
        <span class="empty-state-title">${escapeHtml(title)}</span>
        ${text ? `<span class="empty-state-text">${escapeHtml(text)}</span>` : ""}
      </div>`;
  }

  function emptyRow(colspan, title, text = "", variant = "") {
    return `<tr><td colspan="${colspan}" class="empty-cell">${emptyState(title, text, variant)}</td></tr>`;
  }

  function carPlate(number) {
    return `<span class="car-number-badge">${escapeHtml(number ?? "—")}</span>`;
  }

  function markLoaded(id) {
    const element = $(id);
    if (element) element.removeAttribute("aria-busy");
  }

  // ==========================================================================
  // Notificaciones
  // ==========================================================================
  function showToast(message, type = "info") {
    const container = $("toast-container");
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    if (type === "error") toast.setAttribute("role", "alert");

    const icon = document.createElement("span");
    icon.className = "toast-icon";
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = type === "success" ? "✓" : (type === "error" ? "!" : "i");
    const text = document.createElement("span");
    text.textContent = String(message || "");
    toast.append(icon, text);
    container.appendChild(toast);

    const dismiss = () => {
      toast.classList.add("leaving");
      setTimeout(() => toast.remove(), 300);
    };
    toast.addEventListener("click", dismiss);
    setTimeout(dismiss, type === "error" ? 7000 : 4500);
  }

  // ==========================================================================
  // Cliente de la API con estado de conexión
  // ==========================================================================
  let connectionOk = true;

  function setConnection(ok, message = "") {
    const banner = $("connection-banner");
    $("panel-link").classList.toggle("lost", !ok);
    $("panel-link-text").textContent = ok ? "Conectado" : "Sin conexión";
    if (ok) {
      banner.hidden = true;
    } else {
      banner.textContent = message;
      banner.hidden = false;
    }
    connectionOk = ok;
  }

  async function apiRequest(endpoint, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (panelToken) headers["X-Admin-Token"] = panelToken;
    let response;
    try {
      response = await fetch(endpoint, { ...options, headers, cache: "no-store" });
    } catch (error) {
      setConnection(false, "Sin conexión con el panel. Comprueba que ACC_AdminPanel sigue abierto; reintentando…");
      return { ok: false, status: 0, data: null };
    }
    if (response.status === 401) {
      setConnection(false, "Acceso no autorizado: abre el panel con el enlace que se abre al iniciarlo (incluye el token).");
    } else if (!connectionOk) {
      setConnection(true);
    }
    let data = null;
    try {
      data = await response.json();
    } catch {
      data = null;
    }
    return { ok: response.ok, status: response.status, data };
  }

  async function apiGet(endpoint) {
    const result = await apiRequest(endpoint);
    return result.ok ? result.data : null;
  }

  async function apiPost(endpoint, body = {}) {
    const result = await apiRequest(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    if (result.data && typeof result.data === "object") {
      if (result.data.success === undefined) result.data.success = result.ok;
      return result.data;
    }
    return { success: false, message: result.status ? `Error HTTP ${result.status}` : "Sin conexión con el panel." };
  }

  // Bloquea el botón mientras dura la acción: evita dobles clics y muestra un spinner.
  async function withBusy(button, action) {
    if (!button || button.classList.contains("is-busy")) return undefined;
    button.classList.add("is-busy");
    button.setAttribute("aria-busy", "true");
    const wasDisabled = button.disabled;
    button.disabled = true;
    try {
      return await action();
    } finally {
      button.classList.remove("is-busy");
      button.removeAttribute("aria-busy");
      button.disabled = wasDisabled;
      updateServerButtons();
    }
  }

  // ==========================================================================
  // 1. Estado del servidor (/api/status)
  // ==========================================================================
  function updateServerButtons() {
    const busy = id => $(id).classList.contains("is-busy");
    if (!busy("btn-start")) $("btn-start").disabled = appState.isRunning || appState.unmanaged;
    if (!busy("btn-stop")) $("btn-stop").disabled = !appState.isRunning;
    if (!busy("btn-restart")) $("btn-restart").disabled = !appState.isRunning;
  }

  async function syncServerStatus() {
    const data = await apiGet("/api/status");
    if (!data) return;

    // Un ejecutable antiguo sirve esta web desde AdminPanel\web pero no tiene la API nueva.
    $("version-banner").hidden = data.api_version !== undefined;
    appState.isRunning = Boolean(data.is_running);
    appState.unmanaged = Boolean(data.unmanaged_acc_detected);

    const lights = $("server-status-badge");
    const state = appState.isRunning ? "online" : (appState.unmanaged ? "unmanaged" : "offline");
    lights.className = `start-lights ${state}`;
    $("server-status-text").textContent = { online: "ONLINE", unmanaged: "EXTERNO", offline: "OFFLINE" }[state];
    $("server-status-sub").textContent = {
      online: `PID ${data.pid}`,
      unmanaged: "accServer no gestionado",
      offline: "accServer detenido"
    }[state];
    updateServerButtons();

    $("server-uptime-val").textContent = formatUptime(data.uptime_seconds);
    $("net-udp-port").textContent = data.udp_port ?? "—";
    $("net-tcp-port").textContent = data.tcp_port ?? "—";

    const stateValue = $("kpi-server-state");
    setText("kpi-server-state", appState.isRunning ? "ONLINE" : (appState.unmanaged ? "EXTERNO" : "OFFLINE"));
    stateValue.classList.toggle("is-online", appState.isRunning);
    stateValue.classList.toggle("is-offline", !appState.isRunning);
    setText("kpi-server-pid", data.pid ? `PID ${data.pid}` : "PID —");
    setText("kpi-status-message", data.status_message || "En espera");
    $("kpi-status-message").title = data.status_message || "";

    setText("kpi-track-name", data.track_display_name || data.track_name || "—");
    $("kpi-track-name").title = data.track_display_name || "";
    setText("kpi-track-file", data.current_track_file || "cfg/event.json");
    const weather = data.weather || {};
    setText("kpi-track-weather", `Temp ${weather.ambient_temp ?? "—"}°C · Nubes ${percent(weather.cloud_level)} · Lluvia ${percent(weather.rain)}`);

    const sessionsContainer = $("kpi-sessions-container");
    const sessions = Array.isArray(data.sessions) ? data.sessions : [];
    sessionsContainer.innerHTML = sessions.length
      ? sessions.map(s => `<span class="session-pill ${sessionClass(s.sessionType)}">${escapeHtml(s.sessionType)} · ${escapeHtml(s.sessionDurationMinutes)}′</span>`).join("")
      : `<span class="kpi-sub-val">Sin sesiones en event.json</span>`;
    setText("kpi-race-locked", data.is_race_locked === 1 ? "Bloqueado" : (data.is_race_locked === 0 ? "Abierto" : "—"));

    setText("kpi-max-slots", `${data.max_car_slots ?? "—"} SLOTS`);
    setText("kpi-max-connections", `Max conexiones: ${data.max_connections ?? "—"}`);
    setText("kpi-server-room-name", data.server_name || "ACC Dedicated Server");
    $("kpi-server-room-name").title = data.server_name || "";

    if (!appState.rotationRequestPending) renderAutoRotation(Boolean(data.auto_rotation));
  }

  function renderAutoRotation(enabled) {
    $("auto-rotation-toggle").checked = enabled;
    const badge = $("auto-rotation-status-badge");
    badge.textContent = enabled ? "ACTIVA" : "PAUSADA";
    badge.className = `toggle-status${enabled ? "" : " paused"}`;
  }

  // ==========================================================================
  // 2. Catálogo de circuitos y rotación (/api/tracks)
  // ==========================================================================
  async function loadTracksPool() {
    const data = await apiGet("/api/tracks");
    if (!data) {
      if ($("categories-tracks-container").getAttribute("aria-busy")) {
        $("categories-tracks-container").innerHTML = emptyState("No se pudo cargar el catálogo", "Se reintentará al volver a abrir la pestaña.", "error");
      }
      return;
    }
    const categories = data.categories || [];
    const activeDlcs = data.active_dlcs || [];
    const disabledTracks = data.disabled_tracks || [];

    $("rotation-active-count").textContent = `${data.active_rotation_count ?? (data.rotation_pool || []).length} / ${data.total_tracks_count ?? "—"}`;

    const presetState = {
      "btn-preset-all": activeDlcs.length === categories.length && disabledTracks.length === 0,
      "btn-preset-base": activeDlcs.length === 1 && activeDlcs.includes("base") && disabledTracks.length === 0,
      "btn-preset-dlc": activeDlcs.length === categories.length - 1 && !activeDlcs.includes("base") && disabledTracks.length === 0
    };
    Object.entries(presetState).forEach(([id, active]) => {
      $(id).classList.toggle("active", active);
      $(id).setAttribute("aria-pressed", String(active));
    });

    // Selector rápido agrupado por paquete
    const select = $("select-direct-track");
    const previous = select.value;
    select.innerHTML = categories.map(cat => `
      <optgroup label="${escapeHtml(cat.name)}">
        ${cat.tracks.map(t => {
          const selected = t.filename === (previous || data.current_track_file);
          return `<option value="${escapeHtml(t.filename)}" ${selected ? "selected" : ""}>${escapeHtml(t.display_name)}${t.filename === data.current_track_file ? " · actual" : ""}</option>`;
        }).join("")}
      </optgroup>`).join("");

    $("dlc-chips-container").innerHTML = categories.map(cat => `
      <div class="dlc-chip-card ${cat.is_active ? "active" : "inactive"}">
        <div class="dlc-chip-info">
          <span class="dlc-chip-name" title="${escapeHtml(cat.name)}">${escapeHtml(cat.name)}</span>
          <div class="dlc-chip-meta">
            <span class="dlc-chip-count">${cat.active_tracks_count}/${cat.total_tracks}</span>
            <span>en rotación</span>
          </div>
        </div>
        <label class="switch switch-sm">
          <input type="checkbox" role="switch" ${cat.is_active ? "checked" : ""} data-action="toggle-dlc" data-dlc-id="${escapeHtml(cat.id)}" aria-label="Incluir ${escapeHtml(cat.name)} en la rotación">
          <span class="slider"></span>
        </label>
      </div>`).join("");
    markLoaded("dlc-chips-container");

    $("categories-tracks-container").innerHTML = categories.map(cat => {
      const isBase = cat.id === "base";
      const cards = cat.tracks.map(t => {
        const isCurrent = t.filename === data.current_track_file || t.is_current;
        return `
          <article class="track-pool-card ${isCurrent ? "active-server-track" : ""} ${t.in_rotation ? "" : "excluded-from-rotation"}">
            <div class="track-card-top">
              <div class="track-card-header-row">
                <h5 class="track-card-title">${escapeHtml(t.display_name)}</h5>
                ${isCurrent ? '<span class="track-badge-live">EN PISTA</span>' : ""}
              </div>
              <span class="track-card-code">${escapeHtml(t.filename)}</span>
            </div>
            <div class="track-weather-grid">
              <div class="weather-metric"><span>Temp</span><strong>${escapeHtml(t.ambient_temp)}°C</strong></div>
              <div class="weather-metric"><span>Lluvia</span><strong>${percent(t.rain)}</strong></div>
              <div class="weather-metric"><span>Nubes</span><strong>${percent(t.cloud_level)}</strong></div>
              <div class="weather-metric"><span>Overtime</span><strong>${escapeHtml(t.session_over_time_seconds ?? 120)} s</strong></div>
            </div>
            <div class="track-card-footer">
              <div class="track-toggle-inline">
                <label class="switch switch-sm">
                  <input type="checkbox" role="switch" ${t.in_rotation ? "checked" : ""} ${cat.is_active ? "" : "disabled"} data-action="toggle-track" data-track-file="${escapeHtml(t.filename)}" aria-label="Incluir ${escapeHtml(t.display_name)} en la rotación">
                  <span class="slider"></span>
                </label>
                <span class="toggle-label">${t.in_rotation ? "En rotación" : "Excluido"}</span>
              </div>
              <button type="button" class="btn btn-sm ${isCurrent ? "btn-success" : "btn-secondary"}" data-action="select-track" data-track-file="${escapeHtml(t.filename)}" ${isCurrent ? 'aria-current="true"' : ""}>
                ${isCurrent ? "Pista actual" : "Cargar pista"}
              </button>
            </div>
          </article>`;
      }).join("");

      return `
        <section class="dlc-category-section ${isBase ? "is-base" : "is-dlc"} ${cat.is_active ? "active" : "inactive"}" aria-label="${escapeHtml(cat.name)}">
          <div class="dlc-category-header">
            <div class="dlc-category-title-group">
              <h4 class="dlc-category-title">${escapeHtml(cat.name)}</h4>
              <span class="dlc-badge ${isBase ? "base" : "dlc"}">${isBase ? "Juego base" : "DLC"}</span>
              <span class="dlc-category-desc">${escapeHtml(cat.description)}</span>
            </div>
            <div class="dlc-category-actions">
              <span class="dlc-category-count-badge">${cat.active_tracks_count} de ${cat.total_tracks} en rotación</span>
              <label class="switch">
                <input type="checkbox" role="switch" ${cat.is_active ? "checked" : ""} data-action="toggle-dlc" data-dlc-id="${escapeHtml(cat.id)}" aria-label="Incluir todo ${escapeHtml(cat.name)} en la rotación">
                <span class="slider"></span>
              </label>
            </div>
          </div>
          <div class="tracks-cards-grid">${cards}</div>
        </section>`;
    }).join("");
    markLoaded("categories-tracks-container");
  }

  async function runRotationChange(endpoint, body, control) {
    if (control) control.disabled = true;
    const res = await apiPost(endpoint, body);
    showToast(res.message || "No se pudo actualizar la rotación.", res.success ? "success" : "error");
    await Promise.all([syncServerStatus(), loadTracksPool()]);
  }

  async function changeTrack(filename, button) {
    if (!filename) return;
    if (appState.isRunning && !confirm(`Cargar ${filename} reinicia accServer y desconecta a los pilotos. ¿Continuar?`)) return;
    await withBusy(button, async () => {
      showToast(`Cargando ${filename}…`, "info");
      const res = await apiPost("/api/rotation/select", { track_file: filename });
      showToast(res.message, res.success ? "success" : "error");
      await Promise.all([syncServerStatus(), loadTracksPool()]);
    });
  }

  // ==========================================================================
  // 3. Telemetría (/api/telemetry)
  // ==========================================================================
  async function loadTelemetry() {
    const data = await apiGet("/api/telemetry");
    if (!data) {
      $("track-records-container").innerHTML = emptyState("No se pudo cargar la telemetría", "Se reintentará con «Actualizar».", "error");
      return;
    }

    const records = Object.entries(data.track_records || {})
      .map(([track, item]) => ({ track, ...item }))
      .sort((a, b) => String(a.track_display_name || a.track).localeCompare(String(b.track_display_name || b.track)));
    $("track-records-container").innerHTML = records.length
      ? records.map((item, index) => `
          <article class="record-card" style="animation-delay: ${Math.min(index * 40, 400)}ms">
            <div class="record-card-track" title="${escapeHtml(item.track_display_name || item.track)}">${escapeHtml(item.track_display_name || item.track)}</div>
            <div class="record-card-time">${formatLapTime(item.time_ms)}</div>
            <div class="record-card-driver">${carPlate(item.car_num)}<strong>${escapeHtml(item.driver)}</strong></div>
          </article>`).join("")
      : emptyState("Sin récords todavía", "Aparecerán cuando se complete una vuelta válida en cualquier sesión.");
    markLoaded("track-records-container");

    const drivers = Object.entries(data.drivers || {}).sort(([, a], [, b]) =>
      (b.wins - a.wins) || (b.podiums - a.podiums) || (b.races - a.races) || (b.total_laps - a.total_laps));
    const shown = drivers.slice(0, RANKING_LIMIT);
    $("drivers-ranking-tbody").innerHTML = shown.length
      ? shown.map(([name, stats], index) => {
          const position = index + 1;
          const podiumClass = position <= 3 && stats.wins + stats.podiums > 0 ? `p${position}` : "";
          return `
            <tr>
              <td><span class="pos-badge ${podiumClass}"><span>P${position}</span></span></td>
              <td class="driver-pill">${escapeHtml(name)}</td>
              <td class="text-center num win-count">${escapeHtml(stats.wins)}</td>
              <td class="text-center num podium-count">${escapeHtml(stats.podiums)}</td>
              <td class="text-center num">${escapeHtml(stats.races)}</td>
              <td class="text-center num">${escapeHtml(stats.total_laps)}</td>
            </tr>`;
        }).join("")
      : emptyRow(6, "Sin pilotos registrados", "La clasificación se construye con los resultados de carrera.");
    $("drivers-ranking-footnote").textContent = drivers.length > RANKING_LIMIT
      ? `Mostrando los ${RANKING_LIMIT} primeros de ${drivers.length} pilotos.` : "";

    const sessions = (data.recent_sessions || []).slice(0, SESSIONS_LIMIT);
    $("recent-sessions-list").innerHTML = sessions.length
      ? sessions.map(s => {
          const winner = s.leaderboard && s.leaderboard.length ? s.leaderboard[0] : null;
          const laps = (s.leaderboard || []).map(line => line.best_lap_ms).filter(ms => ms > 0 && ms < 2147483647);
          const fastest = laps.length ? Math.min(...laps) : 0;
          return `
            <div class="session-item-card">
              <span class="session-badge ${sessionClass(s.session_type)}">${escapeHtml(s.session_type)}</span>
              <div>
                <div class="session-track">${escapeHtml(s.track_display_name || s.track_name)}</div>
                <div class="session-meta">
                  ${winner ? `P1 <strong>${escapeHtml(winner.driver)}</strong> (#${escapeHtml(winner.car_num)})` : "Sin clasificados"}
                  · ${escapeHtml(s.total_drivers)} pilotos
                  · Vuelta rápida <span class="session-best">${formatLapTime(fastest)}</span>
                </div>
              </div>
              <span class="session-when" title="${escapeHtml(s.filename)}">${escapeHtml(formatResultDate(s.filename))}</span>
            </div>`;
        }).join("")
      : emptyState("Sin sesiones en results/", "ACC escribe un archivo al terminar cada sesión (dumpLeaderboards = 1).");
    markLoaded("recent-sessions-list");
  }

  // ==========================================================================
  // 4. Configuración (/api/config)
  // ==========================================================================
  async function loadConfigData() {
    const data = await apiGet("/api/config");
    if (!data) {
      showToast("No se pudo cargar la configuración.", "error");
      return;
    }
    appState.configData = data;
    const s = data.settings || {};
    const e = data.event || {};
    const a = data.assistRules || {};
    const secretsSet = data.secrets_set || {};

    $("cfg-server-name").value = s.serverName || "";
    $("cfg-admin-password").value = "";
    $("cfg-admin-password").placeholder = secretsSet.adminPassword ? "•••••••• (sin cambios)" : "Obligatoria";
    $("cfg-server-password").value = "";
    $("cfg-server-password").placeholder = secretsSet.password ? "•••••••• (sin cambios)" : "Sala pública (sin contraseña)";
    $("cfg-clear-server-password").checked = false;
    $("cfg-max-slots").value = s.maxCarSlots ?? 24;
    $("cfg-is-race-locked").value = s.isRaceLocked ?? 1;
    $("cfg-car-group").value = s.carGroup || "FreeForAll";

    const sessions = e.sessions || [];
    const practice = sessions.find(x => x.sessionType === "P" || x.sessionType === "FP");
    const qualifying = sessions.find(x => x.sessionType === "Q");
    const race = sessions.find(x => x.sessionType === "R");
    if (practice) $("cfg-duration-fp").value = practice.sessionDurationMinutes;
    if (qualifying) $("cfg-duration-q").value = qualifying.sessionDurationMinutes;
    if (race) $("cfg-duration-r").value = race.sessionDurationMinutes;

    $("cfg-ambient-temp").value = e.ambientTemp ?? 25;
    $("cfg-cloud-level").value = e.cloudLevel ?? 0.1;
    $("cfg-rain").value = e.rain ?? 0;
    $("cfg-weather-random").value = e.weatherRandomness ?? 1;
    $("cfg-stability-control").value = a.stabilityControlLevelMax ?? 100;
    $("cfg-disable-ideal-line").value = a.disableIdealLine ?? 0;
  }

  $("config-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const form = ev.currentTarget;
    if (!appState.configData) {
      showToast("La configuración aún no se ha cargado.", "error");
      return;
    }
    form.classList.add("was-validated");
    if (!form.reportValidity()) return;

    const s = { ...(appState.configData.settings || {}) };
    const e = JSON.parse(JSON.stringify(appState.configData.event || {}));
    const a = { ...(appState.configData.assistRules || {}) };
    const c = { ...(appState.configData.configuration || {}) };

    // Contraseñas: sólo se envían si se escribieron o si se pide quitar la de acceso.
    s.serverName = $("cfg-server-name").value.trim();
    const newAdminPassword = $("cfg-admin-password").value.trim();
    const newServerPassword = $("cfg-server-password").value.trim();
    if (newAdminPassword) s.adminPassword = newAdminPassword;
    if ($("cfg-clear-server-password").checked) s.password = "";
    else if (newServerPassword) s.password = newServerPassword;
    s.maxCarSlots = parseInt($("cfg-max-slots").value, 10);
    s.isRaceLocked = parseInt($("cfg-is-race-locked").value, 10);
    s.carGroup = $("cfg-car-group").value;
    s.dumpLeaderboards = 1;
    s.configVersion = 1;

    const durations = {
      P: parseInt($("cfg-duration-fp").value, 10),
      FP: parseInt($("cfg-duration-fp").value, 10),
      Q: parseInt($("cfg-duration-q").value, 10),
      R: parseInt($("cfg-duration-r").value, 10)
    };
    (e.sessions || []).forEach(session => {
      if (durations[session.sessionType] !== undefined) session.sessionDurationMinutes = durations[session.sessionType];
    });
    e.ambientTemp = parseInt($("cfg-ambient-temp").value, 10);
    e.cloudLevel = parseFloat($("cfg-cloud-level").value);
    e.rain = parseFloat($("cfg-rain").value);
    e.weatherRandomness = parseInt($("cfg-weather-random").value, 10);
    a.stabilityControlLevelMax = parseInt($("cfg-stability-control").value, 10);
    a.disableIdealLine = parseInt($("cfg-disable-ideal-line").value, 10);

    await withBusy($("btn-save-config"), async () => {
      const res = await apiPost("/api/config", { settings: s, event: e, assistRules: a, configuration: c });
      if (res.success) {
        showToast("Configuración guardada en UTF-16 LE. Se aplicará en el próximo arranque.", "success");
        await Promise.all([loadConfigData(), syncServerStatus()]);
      } else {
        showToast(res.message || "No se pudo guardar la configuración.", "error");
      }
    });
  });

  // ==========================================================================
  // 5. Consola (/api/logs)
  // ==========================================================================
  function highlightLogLine(line) {
    const safe = escapeHtml(line);
    const withTimestamp = safe.replace(/^(\d+:)/, '<span class="log-ts">$1</span>');
    if (/==ERR|error/i.test(line)) return `<span class="log-err">${withTimestamp}</span>`;
    if (/New connection request|Creating new car connection|client\(s\) online|closed the connection|dead connection|no driving connection/.test(line)) {
      return `<span class="log-conn">${withTimestamp}</span>`;
    }
    if (/Session changed|sessionPhase|Server starting|Track .* was set/.test(line)) return `<span class="log-session">${withTimestamp}</span>`;
    return withTimestamp;
  }

  async function loadLogs() {
    const lines = $("select-log-lines").value;
    const hideSpam = $("toggle-hide-spam").checked ? 1 : 0;
    const data = await apiGet(`/api/logs?lines=${lines}&hide_spam=${hideSpam}`);
    if (!data || !data.logs) return;

    const terminalWindow = $("logs-terminal-window");
    $("logs-content").innerHTML = data.logs.map(line => highlightLogLine(line.replace(/\n$/, ""))).join("\n");
    $("logs-hidden-count").textContent = data.hidden_spam_lines ? `${data.hidden_spam_lines} líneas de spam ocultas` : "";
    if (appState.autoScrollLogs) terminalWindow.scrollTop = terminalWindow.scrollHeight;
  }

  // ==========================================================================
  // 6. Pilotos y moderación (/api/players)
  // ==========================================================================
  async function loadPlayersData() {
    const data = await apiGet("/api/players");
    const activeTbody = $("active-players-tbody");
    if (!data) {
      activeTbody.innerHTML = emptyRow(7, "No se pudo consultar /api/players", "Se reintentará automáticamente.", "error");
      return;
    }

    const active = data.active_players || [];
    appState.activePlayers = data.total_active || 0;
    const counter = $("active-players-counter");
    counter.textContent = appState.activePlayers;
    counter.classList.toggle("has-players", appState.activePlayers > 0);
    const sessionName = data.session && data.session.name ? ` · ${data.session.name}` : "";
    const countTag = $("live-drivers-count-tag");
    countTag.textContent = `${appState.activePlayers} ${appState.activePlayers === 1 ? "piloto" : "pilotos"} en línea${sessionName}`;
    countTag.title = data.live_source === "stream"
      ? "Datos en tiempo real desde la consola de accServer"
      : "Datos desde server.log: accServer lo escribe con buffer y puede ir con retraso";

    if (data.live_error) {
      activeTbody.innerHTML = emptyRow(7, "No se pudo leer server.log", data.live_error, "error");
    } else if (data.server_running === undefined) {
      activeTbody.innerHTML = emptyRow(7, "Backend desactualizado", "Recompila ACC_AdminPanel.exe (build_release.bat) para ver pilotos en vivo.", "error");
    } else if (!data.server_running) {
      activeTbody.innerHTML = emptyRow(7, "Servidor detenido", "Inicia accServer desde el panel para ver a los pilotos en vivo.", "offline");
    } else if (active.length === 0) {
      activeTbody.innerHTML = emptyRow(7, "Pista vacía", "Esperando conexiones en el lobby.");
    } else {
      activeTbody.innerHTML = active.map(p => `
        <tr>
          <td>${carPlate(p.race_number ?? p.car_id)}</td>
          <td><span class="driver-pill">${escapeHtml(p.driver_name)}</span>
            ${p.is_admin ? '<span class="badge-admin">ADMIN</span>' : ""}${p.is_banned ? '<span class="badge-banned">BANEADO</span>' : ""}</td>
          <td>${escapeHtml(p.car_model_name)}</td>
          <td><a href="${steamProfileUrl(p.player_id)}" target="_blank" rel="noopener noreferrer" class="steam-link">${escapeHtml(p.player_id)}</a></td>
          <td class="text-center"><span class="conn-id" title="connId / carId según server.log">${escapeHtml(p.conn_id)} / ${escapeHtml(p.car_id)}</span></td>
          <td class="text-center">${p.lag_ms
            ? `<span class="status-chip lag" title="accServer no recibe paquetes UDP del piloto desde hace ${escapeHtml(p.lag_ms)} ms">LAG ${(p.lag_ms / 1000).toFixed(1)} s</span>`
            : '<span class="status-chip">EN PISTA</span>'}</td>
          <td class="text-center">
            <button type="button" class="btn btn-sm btn-secondary" data-action="open-modal" data-payload="${encodePayload(p)}">Moderar</button>
          </td>
        </tr>`).join("");
    }

    const recent = data.recent_players || [];
    $("recent-players-tbody").innerHTML = recent.length
      ? recent.map(p => {
          const payload = encodePayload(p);
          const role = p.is_admin ? '<span class="role-admin">Admin</span>' : (p.is_banned ? '<span class="role-banned">Baneado</span>' : "Piloto");
          return `
            <tr>
              <td>${carPlate(p.race_number || "—")}</td>
              <td><span class="driver-pill">${escapeHtml(p.driver_name)}</span>
                ${p.is_admin ? '<span class="badge-admin">ADMIN</span>' : ""}${p.is_banned ? '<span class="badge-banned">BANEADO</span>' : ""}</td>
              <td>${escapeHtml(p.car_model_name)}</td>
              <td><a href="${steamProfileUrl(p.player_id)}" target="_blank" rel="noopener noreferrer" class="steam-link">${escapeHtml(p.player_id)}</a></td>
              <td class="text-center num" style="color: var(--timing-purple);">${formatLapTime(p.best_lap_ms)}</td>
              <td class="text-center num">${escapeHtml(p.total_laps)}</td>
              <td class="text-center">${role}</td>
              <td>
                <div class="row-actions">
                  <button type="button" class="btn btn-sm btn-secondary" data-action="open-modal" data-payload="${payload}">Moderar</button>
                  <button type="button" class="btn btn-sm btn-secondary" data-action="toggle-admin" data-payload="${payload}" data-make-admin="${!p.is_admin}">${p.is_admin ? "Quitar admin" : "Hacer admin"}</button>
                  <button type="button" class="btn btn-sm btn-stop" data-action="ban-player" data-payload="${payload}" aria-label="Añadir ${escapeHtml(p.driver_name)} a la lista negra">Ban</button>
                </div>
              </td>
            </tr>`;
        }).join("")
      : emptyRow(8, "Sin historial", "Todavía no hay pilotos en results/.");

    const banlist = data.banlist || [];
    $("banlist-tbody").innerHTML = banlist.length
      ? banlist.map(b => `
          <tr>
            <td class="driver-pill">${escapeHtml(b.driverName || "Desconocido")}</td>
            <td><code>${escapeHtml(b.playerId)}</code></td>
            <td style="color: #ff8a94;">${escapeHtml(b.reason || "Sin motivo")}</td>
            <td class="text-center">
              <button type="button" class="btn btn-sm btn-secondary" data-action="unban-player" data-payload="${encodePayload({ player_id: b.playerId })}">Desbanear</button>
            </td>
          </tr>`).join("")
      : emptyRow(4, "Lista negra vacía");

    const entrylist = data.entrylist || {};
    const entries = entrylist.entries || [];
    $("toggle-force-entrylist").checked = entrylist.forceEntryList === 1;
    $("entrylist-tbody").innerHTML = entries.length
      ? entries.map(e => {
          const driver = (e.drivers && e.drivers[0]) || {};
          const name = `${driver.firstName || ""} ${driver.lastName || ""}`.trim() || "Piloto registrado";
          return `
            <tr>
              <td class="driver-pill">${escapeHtml(name)}</td>
              <td><code>${escapeHtml(driver.playerID || "—")}</code></td>
              <td class="text-center">${carPlate(e.raceNumber || "—")}</td>
              <td class="text-center">${e.isServerAdmin === 1 ? '<span class="badge-admin">ADMIN</span>' : '<span class="badge-tag">AUTORIZADO</span>'}</td>
              <td class="text-center">
                <button type="button" class="btn btn-sm btn-secondary" data-action="remove-entry" data-payload="${encodePayload({ player_id: driver.playerID || "", driver_name: name })}">Quitar</button>
              </td>
            </tr>`;
        }).join("")
      : emptyRow(5, "Entry list vacía", "Registra pilotos para darles dorsal fijo o rango de administrador.");
  }

  // ==========================================================================
  // Modal de moderación
  // ==========================================================================
  const modal = $("moderation-modal");
  let modalTrigger = null;
  let currentModDriver = null;
  let currentModCar = null;

  function openModModal(payload) {
    const driver = decodePayload(payload);
    modalTrigger = document.activeElement;
    currentModDriver = driver;
    currentModCar = driver.race_number || driver.car_id || 1;

    $("mod-modal-car-badge").textContent = currentModCar;
    $("mod-modal-driver-name").textContent = driver.driver_name || "Piloto";
    $("mod-modal-car-model").textContent = driver.car_model_name || "—";
    $("mod-modal-steamid").textContent = driver.player_id || "—";
    $("mod-modal-steam-link").href = steamProfileUrl(driver.player_id);
    COMMANDS.forEach(command => {
      $(`btn-cmd-${command}`).querySelector(".cmd-text").textContent = `/${command} ${currentModCar}`;
    });
    $("btn-mod-toggle-admin").querySelector("span").textContent = driver.is_admin ? "Quitar administrador" : "Asignar administrador";

    modal.classList.remove("hidden");
    $("btn-close-mod-modal").focus();
  }

  function closeModModal() {
    modal.classList.add("hidden");
    if (modalTrigger instanceof HTMLElement && document.contains(modalTrigger)) modalTrigger.focus();
  }

  $("btn-close-mod-modal").addEventListener("click", closeModModal);
  $("btn-mod-modal-close").addEventListener("click", closeModModal);
  modal.addEventListener("click", event => { if (event.target === modal) closeModModal(); });

  document.addEventListener("keydown", event => {
    if (modal.classList.contains("hidden")) return;
    if (event.key === "Escape") {
      closeModModal();
      return;
    }
    if (event.key === "Tab") {
      // Mantener el foco dentro del diálogo
      const focusable = [...modal.querySelectorAll("button, [href], input, select")].filter(el => !el.disabled && el.offsetParent !== null);
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  });

  function copyCommand(command) {
    navigator.clipboard.writeText(command)
      .then(() => showToast(`Copiado «${command}». Pégalo en el chat de ACC.`, "success"))
      .catch(() => showToast(`Comando: ${command}`, "info"));
  }

  const COMMANDS = ["kick", "ban", "dq", "dt", "dtc", "sg10", "sg30", "tp5", "tp15", "clear"];
  COMMANDS.forEach(command => {
    $(`btn-cmd-${command}`).addEventListener("click", () => copyCommand(`/${command} ${currentModCar}`));
  });
  $("btn-cmd-ballast").addEventListener("click", () => copyCommand(`/ballast ${currentModCar} ${$("mod-ballast-val").value || 0}`));
  $("btn-cmd-restrictor").addEventListener("click", () => copyCommand(`/restrictor ${currentModCar} ${$("mod-restrictor-val").value || 0}`));

  async function setAdmin(driver, makeAdmin, carNumber) {
    const res = await apiPost("/api/moderation/admin", {
      playerId: driver.player_id,
      driverName: driver.driver_name,
      carNumber: carNumber || 99,
      isAdmin: makeAdmin
    });
    showToast(res.message, res.success ? "success" : "error");
    await loadPlayersData();
    return res.success;
  }

  async function banDriver(driver, carNumber) {
    const reason = prompt(`Motivo del baneo para ${driver.driver_name}:`, "Conducta antideportiva");
    if (!reason) return false;
    const res = await apiPost("/api/moderation/ban", {
      playerId: driver.player_id,
      driverName: driver.driver_name,
      carNumber: carNumber || 0,
      reason
    });
    showToast(res.message, res.success ? "success" : "error");
    await loadPlayersData();
    return res.success;
  }

  $("btn-mod-toggle-admin").addEventListener("click", async (ev) => {
    if (!currentModDriver) return;
    await withBusy(ev.currentTarget, () => setAdmin(currentModDriver, !currentModDriver.is_admin, currentModCar));
    closeModModal();
  });

  $("btn-mod-add-ban").addEventListener("click", async (ev) => {
    if (!currentModDriver) return;
    const done = await withBusy(ev.currentTarget, () => banDriver(currentModDriver, currentModCar));
    if (done) closeModModal();
  });

  // ==========================================================================
  // Acciones delegadas (tablas y tarjetas generadas dinámicamente)
  // ==========================================================================
  document.addEventListener("change", event => {
    const control = event.target.closest("[data-action]");
    if (!control) return;
    if (control.dataset.action === "toggle-dlc") {
      runRotationChange("/api/rotation/dlc-toggle", { dlc_id: control.dataset.dlcId, enabled: control.checked }, control);
    }
    if (control.dataset.action === "toggle-track") {
      runRotationChange("/api/rotation/track-toggle", { track_file: control.dataset.trackFile, enabled: control.checked }, control);
    }
  });

  document.addEventListener("click", async event => {
    const control = event.target.closest("button[data-action]");
    if (!control) return;
    const { action, payload, trackFile, makeAdmin } = control.dataset;
    try {
      if (action === "select-track") await changeTrack(trackFile, control);
      if (action === "open-modal") openModModal(payload);
      if (action === "toggle-admin") {
        const driver = decodePayload(payload);
        await withBusy(control, () => setAdmin(driver, makeAdmin === "true", driver.race_number));
      }
      if (action === "ban-player") {
        const driver = decodePayload(payload);
        await withBusy(control, () => banDriver(driver, driver.race_number));
      }
      if (action === "unban-player") {
        const player = decodePayload(payload);
        if (!confirm(`¿Quitar de la lista negra a ${player.player_id}?`)) return;
        await withBusy(control, async () => {
          const res = await apiPost("/api/moderation/unban", { playerId: player.player_id });
          showToast(res.message, res.success ? "success" : "error");
          await loadPlayersData();
        });
      }
      if (action === "remove-entry") {
        const entry = decodePayload(payload);
        if (!confirm(`¿Quitar a ${entry.driver_name} (${entry.player_id}) de la entry list?`)) return;
        await withBusy(control, async () => {
          const res = await apiPost("/api/entrylist/remove", { playerId: entry.player_id });
          showToast(res.message || "No se pudo quitar la entrada.", res.success ? "success" : "error");
          await loadPlayersData();
        });
      }
    } catch {
      showToast("La acción contiene datos inválidos.", "error");
    }
  });

  // ==========================================================================
  // Controles del servidor y la rotación
  // ==========================================================================
  $("btn-start").addEventListener("click", ev => withBusy(ev.currentTarget, async () => {
    const res = await apiPost("/api/server/start");
    showToast(res.message, res.success ? "success" : "error");
    await syncServerStatus();
  }));

  $("btn-restart").addEventListener("click", ev => {
    if (!confirm("Reiniciar accServer desconectará a todos los pilotos. ¿Continuar?")) return;
    withBusy(ev.currentTarget, async () => {
      showToast("Reiniciando servidor y liberando puertos…", "info");
      const res = await apiPost("/api/server/restart");
      showToast(res.message, res.success ? "success" : "error");
      await syncServerStatus();
    });
  });

  $("btn-stop").addEventListener("click", ev => {
    if (!confirm("¿Detener accServer? Los pilotos conectados serán desconectados.")) return;
    withBusy(ev.currentTarget, async () => {
      const res = await apiPost("/api/server/stop");
      showToast(res.message, res.success ? "success" : "error");
      await syncServerStatus();
    });
  });

  $("auto-rotation-toggle").addEventListener("change", async ev => {
    const toggle = ev.currentTarget;
    const enabled = toggle.checked;
    appState.rotationRequestPending = true;
    toggle.disabled = true;
    renderAutoRotation(enabled);
    const res = await apiPost("/api/rotation/toggle", { enabled });
    appState.rotationRequestPending = false;
    toggle.disabled = false;
    if (!res.success) renderAutoRotation(!enabled);
    showToast(res.message || "No se pudo cambiar la auto-rotación.", res.success ? "info" : "error");
  });

  $("btn-skip-track").addEventListener("click", ev => {
    if (appState.isRunning && !confirm("Saltar de pista reinicia accServer y desconecta a los pilotos. ¿Continuar?")) return;
    withBusy(ev.currentTarget, async () => {
      const res = await apiPost("/api/rotation/skip");
      showToast(res.message, res.success ? "success" : "error");
      await Promise.all([syncServerStatus(), loadTracksPool()]);
    });
  });

  $("btn-apply-track").addEventListener("click", ev => changeTrack($("select-direct-track").value, ev.currentTarget));

  [["btn-preset-all", "all"], ["btn-preset-base", "base_only"], ["btn-preset-dlc", "dlc_only"]].forEach(([id, preset]) => {
    $(id).addEventListener("click", ev => withBusy(ev.currentTarget, () => runRotationChange("/api/rotation/preset", { preset })));
  });

  $("btn-refresh-telemetry").addEventListener("click", ev => withBusy(ev.currentTarget, loadTelemetry));
  $("btn-refresh-players").addEventListener("click", ev => withBusy(ev.currentTarget, loadPlayersData));
  $("btn-refresh-logs").addEventListener("click", ev => withBusy(ev.currentTarget, loadLogs));
  $("toggle-hide-spam").addEventListener("change", loadLogs);
  $("select-log-lines").addEventListener("change", loadLogs);

  $("btn-autoscroll-toggle").addEventListener("click", ev => {
    appState.autoScrollLogs = !appState.autoScrollLogs;
    ev.currentTarget.classList.toggle("active", appState.autoScrollLogs);
    ev.currentTarget.setAttribute("aria-pressed", String(appState.autoScrollLogs));
    ev.currentTarget.textContent = appState.autoScrollLogs ? "Auto-scroll" : "Auto-scroll (pausado)";
  });

  $("form-add-ban").addEventListener("submit", async ev => {
    ev.preventDefault();
    const form = ev.currentTarget;
    await withBusy(form.querySelector("button[type=submit]"), async () => {
      const res = await apiPost("/api/moderation/ban", {
        playerId: $("ban-input-pid").value.trim(),
        driverName: $("ban-input-name").value.trim(),
        carNumber: 0,
        reason: $("ban-input-reason").value.trim()
      });
      showToast(res.message, res.success ? "success" : "error");
      if (res.success) form.reset();
      await loadPlayersData();
    });
  });

  $("form-add-entry").addEventListener("submit", async ev => {
    ev.preventDefault();
    const form = ev.currentTarget;
    await withBusy(form.querySelector("button[type=submit]"), async () => {
      const res = await apiPost("/api/moderation/admin", {
        playerId: $("entry-input-pid").value.trim(),
        driverName: $("entry-input-name").value.trim(),
        carNumber: parseInt($("entry-input-num").value, 10) || 99,
        isAdmin: $("entry-input-is-admin").checked
      });
      showToast(res.message, res.success ? "success" : "error");
      if (res.success) form.reset();
      await loadPlayersData();
    });
  });

  $("toggle-force-entrylist").addEventListener("change", async ev => {
    const toggle = ev.currentTarget;
    const enabled = toggle.checked;
    toggle.disabled = true;
    const res = await apiPost("/api/entrylist/force", { enabled });
    toggle.disabled = false;
    if (!res.success) toggle.checked = !enabled;
    showToast(res.message || "No se pudo cambiar la whitelist.", res.success ? "success" : "error");
  });

  // ==========================================================================
  // Pestañas accesibles (flechas, Inicio/Fin) y enlazables por #hash
  // ==========================================================================
  const tabButtons = [...document.querySelectorAll(".tab-btn")];
  const TAB_LOADERS = {
    "tab-telemetry": loadTelemetry,
    "tab-players": loadPlayersData,
    "tab-config": loadConfigData,
    "tab-tracks": loadTracksPool,
    "tab-logs": loadLogs
  };

  function activateTab(targetId, { focus = false, updateHash = true } = {}) {
    const button = tabButtons.find(btn => btn.dataset.tab === targetId);
    if (!button) return;
    tabButtons.forEach(btn => {
      const selected = btn === button;
      btn.classList.toggle("active", selected);
      btn.setAttribute("aria-selected", String(selected));
      btn.tabIndex = selected ? 0 : -1;
    });
    document.querySelectorAll(".tab-content").forEach(panel => panel.classList.toggle("active", panel.id === targetId));
    appState.currentTab = targetId;
    if (focus) button.focus();
    if (updateHash) history.replaceState(null, "", `#${targetId.replace("tab-", "")}`);
    TAB_LOADERS[targetId]();
  }

  tabButtons.forEach((button, index) => {
    button.addEventListener("click", () => activateTab(button.dataset.tab));
    button.addEventListener("keydown", event => {
      const moves = { ArrowRight: index + 1, ArrowLeft: index - 1, Home: 0, End: tabButtons.length - 1 };
      if (!(event.key in moves)) return;
      event.preventDefault();
      const next = tabButtons[(moves[event.key] + tabButtons.length) % tabButtons.length];
      activateTab(next.dataset.tab, { focus: true });
    });
  });

  // ==========================================================================
  // Arranque y sondeo secuencial (sin solapar peticiones; más lento en segundo plano)
  // ==========================================================================
  async function pollTick() {
    await syncServerStatus();
    if (appState.currentTab === "tab-logs") await loadLogs();
    if (appState.currentTab === "tab-players") await loadPlayersData();
  }

  async function pollLoop() {
    try {
      await pollTick();
    } finally {
      setTimeout(pollLoop, document.hidden ? POLL_HIDDEN_INTERVAL_MS : POLL_INTERVAL_MS);
    }
  }

  const initialTab = `tab-${(location.hash || "").replace("#", "")}`;
  syncServerStatus();
  loadTracksPool();
  loadPlayersData();
  if (TAB_LOADERS[initialTab] && initialTab !== "tab-telemetry") {
    activateTab(initialTab, { updateHash: false });
    loadTelemetry();
  } else {
    loadTelemetry();
  }
  setTimeout(pollLoop, POLL_INTERVAL_MS);
});
