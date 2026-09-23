/**
 * ASSETTO CORSA COMPETIZIONE — ADMIN CONTROL PANEL FRONTEND
 * Reactive state management, REST API polling, and motorsport UI interactions
 */

document.addEventListener("DOMContentLoaded", () => {
  const url = new URL(window.location.href);
  const tokenFromUrl = url.searchParams.get("token");
  if (tokenFromUrl) {
    sessionStorage.setItem("acc-panel-token", tokenFromUrl);
    url.searchParams.delete("token");
    window.history.replaceState({}, document.title, `${url.pathname}${url.search}${url.hash}`);
  }
  const panelToken = sessionStorage.getItem("acc-panel-token") || "";
  let authorizationWarningShown = false;

  // --- Estado Local ---
  let appState = {
    isRunning: false,
    autoRotation: true,
    currentTrack: "",
    tracksList: [],
    configData: null,
    autoScrollLogs: true,
    currentTab: "tab-telemetry"
  };

  // --- Helpers de Tiempo y Formato ---
  function formatLapTime(ms) {
    if (!ms || ms >= 2147483647) return "—:——.———";
    const totalSec = ms / 1000;
    const minutes = Math.floor(totalSec / 60);
    const seconds = (totalSec % 60).toFixed(3);
    const secStr = seconds < 10 ? `0${seconds}` : seconds;
    return `${minutes}:${secStr}`;
  }

  function formatUptime(seconds) {
    if (!seconds || seconds <= 0) return "00:00:00";
    const hrs = Math.floor(seconds / 3600).toString().padStart(2, "0");
    const mins = Math.floor((seconds % 3600) / 60).toString().padStart(2, "0");
    const secs = Math.floor(seconds % 60).toString().padStart(2, "0");
    return `${hrs}:${mins}:${secs}`;
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>'"]/g, char => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
    }[char]));
  }

  function encodePayload(value) {
    const bytes = new TextEncoder().encode(JSON.stringify(value));
    return btoa(String.fromCharCode(...bytes));
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

  // --- Sistema de Notificaciones Toast ---
  function showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    
    let icon = "ℹ️";
    if (type === "success") icon = "✅";
    if (type === "error") icon = "❌";

    const iconElement = document.createElement("span");
    iconElement.textContent = icon;
    const messageElement = document.createElement("span");
    messageElement.textContent = String(message);
    toast.append(iconElement, messageElement);
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(100%)";
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // --- API Client ---
  async function apiGet(endpoint) {
    try {
      const res = await fetch(endpoint, { headers: panelToken ? { "X-Admin-Token": panelToken } : {} });
      if (res.status === 401 && !authorizationWarningShown) {
        authorizationWarningShown = true;
        showToast("Acceso no autorizado. Reinicia el panel y usa el enlace mostrado en la consola.", "error");
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      console.error(`Error en GET ${endpoint}:`, err);
      return null;
    }
  }

  async function apiPost(endpoint, data = {}) {
    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(panelToken ? { "X-Admin-Token": panelToken } : {}) },
        body: JSON.stringify(data)
      });
      return await res.json();
    } catch (err) {
      console.error(`Error en POST ${endpoint}:`, err);
      return { success: false, message: err.message };
    }
  }

  // --- 1. Sincronización del Estado del Servidor (/api/status) ---
  async function syncServerStatus() {
    const data = await apiGet("/api/status");
    if (!data) return;

    appState.isRunning = data.is_running;
    appState.autoRotation = data.auto_rotation;
    appState.currentTrack = data.track_name;

    // Header Badge
    const statusBadge = document.getElementById("server-status-badge");
    const statusText = document.getElementById("server-status-text");
    if (data.is_running) {
      statusBadge.className = "status-indicator-badge online";
      statusText.textContent = "ONLINE";
    } else {
      statusBadge.className = "status-indicator-badge offline";
      statusText.textContent = "OFFLINE";
    }

    // Uptime
    document.getElementById("server-uptime-val").textContent = formatUptime(data.uptime_seconds);

    // KPI Cards
    document.getElementById("kpi-server-state").textContent = data.is_running ? "ONLINE" : "OFFLINE";
    document.getElementById("kpi-server-state").style.color = data.is_running ? "var(--accent-green)" : "var(--accent-red)";
    document.getElementById("kpi-server-pid").textContent = data.pid ? `PID: ${data.pid}` : "PID: —";
    document.getElementById("kpi-status-message").textContent = data.status_message || "En espera";

    document.getElementById("kpi-track-name").textContent = data.track_name || "MONZA";
    document.getElementById("kpi-track-file").textContent = data.current_track_file || "cfg/event.json";
    document.getElementById("kpi-server-room-name").textContent = data.server_name || "ACC Dedicated Server";
    document.getElementById("kpi-max-slots").textContent = `${data.max_car_slots || 24} SLOTS`;

    // Render Sessions Pill
    const sessionsContainer = document.getElementById("kpi-sessions-container");
    if (data.sessions && data.sessions.length > 0) {
      sessionsContainer.innerHTML = data.sessions.map(s => {
        const type = sessionClass(s.sessionType);
        return `<span class="session-pill ${type}">${escapeHtml(s.sessionType)}: ${escapeHtml(s.sessionDurationMinutes)}m</span>`;
      }).join("");
    }

    // Auto-Rotation Switch
    const autoRotToggle = document.getElementById("auto-rotation-toggle");
    const autoRotBadge = document.getElementById("auto-rotation-status-badge");
    autoRotToggle.checked = data.auto_rotation;
    if (data.auto_rotation) {
      autoRotBadge.textContent = "ACTIVA";
      autoRotBadge.className = "toggle-status";
    } else {
      autoRotBadge.textContent = "PAUSADA";
      autoRotBadge.className = "toggle-status paused";
    }
  }

  // --- 2. Carga y Renderizado del Catálogo de Pistas y DLCs (/api/tracks) ---
  async function loadTracksPool() {
    const data = await apiGet("/api/tracks");
    if (!data) return;

    appState.tracksList = data.tracks || [];
    appState.categories = data.categories || [];
    appState.activeDlcs = data.active_dlcs || [];
    appState.disabledTracks = data.disabled_tracks || [];

    // 1. Contador Global de Rotación
    const counterEl = document.getElementById("rotation-active-count");
    if (counterEl) {
      counterEl.textContent = `${data.active_rotation_count !== undefined ? data.active_rotation_count : (data.rotation_pool ? data.rotation_pool.length : 0)} / ${data.total_tracks_count || 25}`;
    }

    // Actualizar estado visual de botones de presets
    const btnAll = document.getElementById("btn-preset-all");
    const btnBase = document.getElementById("btn-preset-base");
    const btnDlc = document.getElementById("btn-preset-dlc");
    if (btnAll && btnBase && btnDlc) {
      btnAll.classList.remove("active");
      btnBase.classList.remove("active");
      btnDlc.classList.remove("active");

      const activeDlcs = data.active_dlcs || [];
      const disabledTracks = data.disabled_tracks || [];
      if (activeDlcs.length === 8 && disabledTracks.length === 0) {
        btnAll.classList.add("active");
      } else if (activeDlcs.length === 1 && activeDlcs.includes("base") && disabledTracks.length === 0) {
        btnBase.classList.add("active");
      } else if (activeDlcs.length === 7 && !activeDlcs.includes("base") && disabledTracks.length === 0) {
        btnDlc.classList.add("active");
      }
    }

    // 2. Poblar Selector Rápido del Banner con <optgroup> por DLC
    const selectDirect = document.getElementById("select-direct-track");
    if (selectDirect) {
      const currentVal = selectDirect.value;
      if (data.categories && data.categories.length > 0) {
        selectDirect.innerHTML = data.categories.map(cat => {
          const options = cat.tracks.map(t => {
            const isSel = (t.filename === (currentVal || data.current_track_file));
            return `<option value="${escapeHtml(t.filename)}" ${isSel ? 'selected' : ''}>${escapeHtml(t.display_name)} (${escapeHtml(t.filename)})</option>`;
          }).join("");
          return `<optgroup label="${escapeHtml(cat.name)} (${cat.tracks.length} circuitos)">${options}</optgroup>`;
        }).join("");
      } else {
        selectDirect.innerHTML = (data.tracks || []).map(t => {
          return `<option value="${escapeHtml(t.filename)}">${escapeHtml(t.display_name || t.track_name)} (${escapeHtml(t.filename)})</option>`;
        }).join("");
      }
    }

    // 3. Renderizar Chips Maestros de DLCs
    const chipsContainer = document.getElementById("dlc-chips-container");
    if (chipsContainer && data.categories) {
      chipsContainer.innerHTML = data.categories.map(cat => {
        const isAct = cat.is_active;
        return `
          <div class="dlc-chip-card ${isAct ? 'active' : 'inactive'}">
            <div class="dlc-chip-info">
              <span class="dlc-chip-name">${escapeHtml(cat.name)}</span>
              <div class="dlc-chip-meta">
                <span class="dlc-chip-count">${cat.active_tracks_count}/${cat.total_tracks} activos</span>
                <span>${cat.tracks.length} pistas</span>
              </div>
            </div>
            <label class="switch switch-sm" title="Activar/desactivar ${escapeHtml(cat.name)} en rotación">
              <input type="checkbox" ${isAct ? 'checked' : ''} data-action="toggle-dlc" data-dlc-id="${escapeHtml(cat.id)}">
              <span class="slider round"></span>
            </label>
          </div>
        `;
      }).join("");
    }

    // 4. Renderizar Secciones Categorizadas de Circuitos
    const categoriesContainer = document.getElementById("categories-tracks-container");
    if (categoriesContainer && data.categories) {
      categoriesContainer.innerHTML = data.categories.map(cat => {
        const isBase = (cat.id === "base");
        const isAct = cat.is_active;

        const trackCardsHtml = cat.tracks.map(t => {
          const isServerCurrent = (t.filename === data.current_track_file || t.is_current);
          const inRot = t.in_rotation;
          return `
            <div class="track-pool-card ${isServerCurrent ? 'active-server-track' : ''} ${!inRot ? 'excluded-from-rotation' : ''}">
              <div class="track-card-top">
                <div class="track-card-header-row">
                  <span class="track-card-title">${escapeHtml(t.display_name)}</span>
                  ${isServerCurrent ? '<span class="track-badge-live">● EN VIVO</span>' : ''}
                </div>
                <span class="track-card-code">${escapeHtml(t.filename)}</span>
              </div>

              <div class="track-weather-grid">
                <div class="weather-metric"><span>🌡️ Temp:</span> <strong>${t.ambient_temp}°C</strong></div>
                <div class="weather-metric"><span>🌧️ Lluvia:</span> <strong>${(t.rain * 100).toFixed(0)}%</strong></div>
                <div class="weather-metric"><span>☁️ Nubes:</span> <strong>${(t.cloud_level * 100).toFixed(0)}%</strong></div>
                <div class="weather-metric"><span>⏱️ Overtime:</span> <strong>${t.session_over_time_seconds || 120}s</strong></div>
              </div>

              <div class="track-card-footer">
                <div class="track-toggle-inline">
                  <label class="switch switch-sm" title="Incluir ${escapeHtml(t.display_name)} en rotación automática">
                    <input type="checkbox" ${inRot ? 'checked' : ''} data-action="toggle-track" data-track-file="${escapeHtml(t.filename)}">
                    <span class="slider round"></span>
                  </label>
                  <span class="toggle-label">${inRot ? 'En Rotación' : 'Excluido'}</span>
                </div>

                <button class="btn btn-sm ${isServerCurrent ? 'btn-success' : 'btn-secondary'}" data-action="select-track" data-track-file="${escapeHtml(t.filename)}">
                  ${isServerCurrent ? '★ Pista Actual' : 'Cargar Pista'}
                </button>
              </div>
            </div>
          `;
        }).join("");

        return `
          <div class="dlc-category-section ${isBase ? 'is-base' : 'is-dlc'} ${isAct ? 'active' : 'inactive'}">
            <div class="dlc-category-header">
              <div class="dlc-category-title-group">
                <span class="dlc-category-title">${escapeHtml(cat.name)}</span>
                <span class="dlc-badge ${isBase ? 'base' : 'dlc'}">${isBase ? 'Juego Base' : 'Expansión DLC'}</span>
                <span class="dlc-category-desc">${escapeHtml(cat.description)}</span>
              </div>

              <div class="dlc-category-actions">
                <span class="dlc-category-count-badge">${cat.active_tracks_count} de ${cat.total_tracks} en rotación</span>
                <label class="switch" title="Activar/desactivar todos los circuitos de ${escapeHtml(cat.name)}">
                  <input type="checkbox" ${isAct ? 'checked' : ''} data-action="toggle-dlc" data-dlc-id="${escapeHtml(cat.id)}">
                  <span class="slider round"></span>
                </label>
              </div>
            </div>

            <div class="tracks-cards-grid">
              ${trackCardsHtml}
            </div>
          </div>
        `;
      }).join("");
    }
  }

  // Handlers Globales de Rotación y DLCs
  window.toggleDlc = async (dlcId, enabled) => {
    const res = await apiPost("/api/rotation/dlc-toggle", { dlc_id: dlcId, enabled: enabled });
    if (res.success) {
      showToast(res.message, "success");
      syncServerStatus();
      loadTracksPool();
    } else {
      showToast(res.message || "Error al actualizar DLC.", "error");
      loadTracksPool();
    }
  };

  window.toggleTrackRotation = async (trackFile, enabled) => {
    const res = await apiPost("/api/rotation/track-toggle", { track_file: trackFile, enabled: enabled });
    if (res.success) {
      showToast(res.message, "info");
      syncServerStatus();
      loadTracksPool();
    } else {
      showToast(res.message || "Error al cambiar estado de pista.", "error");
      loadTracksPool();
    }
  };

  window.applyRotationPreset = async (preset) => {
    const res = await apiPost("/api/rotation/preset", { preset: preset });
    if (res.success) {
      showToast(res.message, "success");
      syncServerStatus();
      loadTracksPool();
    } else {
      showToast(res.message || "Error al aplicar preset.", "error");
    }
  };

  // Helper global para seleccionar pista desde las tarjetas
  window.selectTrackDirect = async (filename) => {
    const res = await apiPost("/api/rotation/select", { track_file: filename });
    if (res.success) {
      showToast(res.message, "success");
      syncServerStatus();
      loadTracksPool();
    } else {
      showToast(res.message, "error");
    }
  };

  // --- 3. Telemetría y Leaderboard (/api/telemetry) ---
  async function loadTelemetry() {
    const data = await apiGet("/api/telemetry");
    if (!data) return;

    // Récords de Vuelta
    const recordsContainer = document.getElementById("track-records-container");
    const tracksObj = data.track_records || {};
    const trackKeys = Object.keys(tracksObj);

    if (trackKeys.length === 0) {
      recordsContainer.innerHTML = `<div class="loading-state">No hay récords registrados aún. Se generan al completar vueltas.</div>`;
    } else {
      recordsContainer.innerHTML = trackKeys.map(track => {
        const item = tracksObj[track];
        return `
          <div class="record-card">
            <div class="record-card-track">${escapeHtml(track)}</div>
            <div class="record-card-time">${formatLapTime(item.time_ms)}</div>
            <div class="record-card-driver">Piloto: <strong>${escapeHtml(item.driver)}</strong> (Coche #${escapeHtml(item.car_num)})</div>
          </div>
        `;
      }).join("");
    }

    // Ranking de Pilotos
    const tbody = document.getElementById("drivers-ranking-tbody");
    const driversObj = data.drivers || {};
    const driverNames = Object.keys(driversObj);

    if (driverNames.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="text-center">No hay registros de pilotos aún.</td></tr>`;
    } else {
      // Ordenar por Victorias descendente, luego podios
      driverNames.sort((a, b) => {
        const diffWins = driversObj[b].wins - driversObj[a].wins;
        if (diffWins !== 0) return diffWins;
        return driversObj[b].podiums - driversObj[a].podiums;
      });

      tbody.innerHTML = driverNames.map(name => {
        const stats = driversObj[name];
        return `
          <tr>
            <td class="driver-pill">${escapeHtml(name)}</td>
            <td class="text-center win-count">${escapeHtml(stats.wins)}</td>
            <td class="text-center podium-count">${escapeHtml(stats.podiums)}</td>
            <td class="text-center">${escapeHtml(stats.races)}</td>
            <td class="text-center">${escapeHtml(stats.total_laps)}</td>
          </tr>
        `;
      }).join("");
    }

    // Últimas Sesiones
    const sessionsList = document.getElementById("recent-sessions-list");
    const recent = data.recent_sessions || [];

    if (recent.length === 0) {
      sessionsList.innerHTML = `<div class="loading-state">No hay sesiones en results/.</div>`;
    } else {
      sessionsList.innerHTML = recent.slice(0, 8).map(s => {
        const winner = s.leaderboard.length > 0 ? s.leaderboard[0] : null;
        const winnerText = winner ? `${escapeHtml(winner.driver)} (#${escapeHtml(winner.car_num)})` : "Sin tiempos";
        const bestTime = winner ? formatLapTime(winner.best_lap_ms) : "—";
        return `
          <div class="session-item-card">
            <div>
              <span class="session-badge ${sessionClass(s.session_type)}">${escapeHtml(s.session_type)}</span>
              <strong style="margin-left: 0.5rem; color: #fff;">${escapeHtml(String(s.track_name || "").toUpperCase())}</strong>
              <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.2rem;">
                Ganador: <span style="color: var(--text-secondary);">${winnerText}</span> | Mejor Vuelta: <span style="color: var(--accent-cyan);">${bestTime}</span>
              </div>
            </div>
            <span class="badge-tag">${escapeHtml(s.filename)}</span>
          </div>
        `;
      }).join("");
    }
  }

  // --- 4. Configuración en Caliente (/api/config) ---
  async function loadConfigData() {
    const data = await apiGet("/api/config");
    if (!data) return;
    appState.configData = data;

    const s = data.settings || {};
    const e = data.event || {};
    const a = data.assistRules || {};

    // Parámetros de servidor
    document.getElementById("cfg-server-name").value = s.serverName || "";
    document.getElementById("cfg-admin-password").value = s.adminPassword || "";
    document.getElementById("cfg-server-password").value = s.password || "";
    document.getElementById("cfg-max-slots").value = s.maxCarSlots || 24;
    document.getElementById("cfg-is-race-locked").value = s.isRaceLocked !== undefined ? s.isRaceLocked : 1;
    document.getElementById("cfg-car-group").value = s.carGroup || "FreeForAll";

    // Duraciones
    const sessions = e.sessions || [];
    const fp = sessions.find(x => x.sessionType === "P" || x.sessionType === "FP");
    const q = sessions.find(x => x.sessionType === "Q");
    const r = sessions.find(x => x.sessionType === "R");

    if (fp) document.getElementById("cfg-duration-fp").value = fp.sessionDurationMinutes;
    if (q) document.getElementById("cfg-duration-q").value = q.sessionDurationMinutes;
    if (r) document.getElementById("cfg-duration-r").value = r.sessionDurationMinutes;

    // Clima
    document.getElementById("cfg-ambient-temp").value = e.ambientTemp !== undefined ? e.ambientTemp : 25;
    document.getElementById("cfg-cloud-level").value = e.cloudLevel !== undefined ? e.cloudLevel : 0.1;
    document.getElementById("cfg-rain").value = e.rain !== undefined ? e.rain : 0.0;
    document.getElementById("cfg-weather-random").value = e.weatherRandomness !== undefined ? e.weatherRandomness : 1;

    // Ayudas
    document.getElementById("cfg-stability-control").value = a.stabilityControlLevelMax !== undefined ? a.stabilityControlLevelMax : 100;
    document.getElementById("cfg-disable-ideal-line").value = a.disableIdealLine !== undefined ? a.disableIdealLine : 0;
  }

  // Guardar Configuración
  document.getElementById("config-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();

    if (!appState.configData) {
      showToast("Error: Los datos base de configuración no están listos.", "error");
      return;
    }

    const s = appState.configData.settings || {};
    const e = appState.configData.event || {};
    const a = appState.configData.assistRules || {};
    const c = appState.configData.configuration || {};

    // Actualizar settings
    s.serverName = document.getElementById("cfg-server-name").value.trim();
    s.adminPassword = document.getElementById("cfg-admin-password").value.trim();
    s.password = document.getElementById("cfg-server-password").value.trim();
    s.maxCarSlots = parseInt(document.getElementById("cfg-max-slots").value, 10);
    s.isRaceLocked = parseInt(document.getElementById("cfg-is-race-locked").value, 10);
    s.carGroup = document.getElementById("cfg-car-group").value;
    s.dumpLeaderboards = 1;
    s.configVersion = 1;

    // Actualizar duraciones de sesión
    const fpMin = parseInt(document.getElementById("cfg-duration-fp").value, 10);
    const qMin = parseInt(document.getElementById("cfg-duration-q").value, 10);
    const rMin = parseInt(document.getElementById("cfg-duration-r").value, 10);

    if (e.sessions) {
      for (const sess of e.sessions) {
        if (sess.sessionType === "P" || sess.sessionType === "FP") sess.sessionDurationMinutes = fpMin;
        if (sess.sessionType === "Q") sess.sessionDurationMinutes = qMin;
        if (sess.sessionType === "R") sess.sessionDurationMinutes = rMin;
      }
    }

    // Actualizar clima
    e.ambientTemp = parseInt(document.getElementById("cfg-ambient-temp").value, 10);
    e.cloudLevel = parseFloat(document.getElementById("cfg-cloud-level").value);
    e.rain = parseFloat(document.getElementById("cfg-rain").value);
    e.weatherRandomness = parseInt(document.getElementById("cfg-weather-random").value, 10);

    // Actualizar asistencias
    a.stabilityControlLevelMax = parseInt(document.getElementById("cfg-stability-control").value, 10);
    a.disableIdealLine = parseInt(document.getElementById("cfg-disable-ideal-line").value, 10);

    const payload = {
      settings: s,
      event: e,
      assistRules: a,
      configuration: c
    };

    const res = await apiPost("/api/config", payload);
    if (res.success) {
      showToast("¡Configuración guardada exitosamente con codificación UTF-16 LE!", "success");
      syncServerStatus();
    } else {
      showToast(res.message || "Error al guardar configuración.", "error");
    }
  });

  // --- 5. Monitor de Logs en Tiempo Real (/api/logs) ---
  async function loadLogs() {
    const lines = document.getElementById("select-log-lines").value;
    const data = await apiGet(`/api/logs?lines=${lines}`);
    if (!data || !data.logs) return;

    const terminal = document.getElementById("logs-content");
    const terminalWindow = document.getElementById("logs-terminal-window");

    terminal.textContent = data.logs.join("");

    if (appState.autoScrollLogs) {
      terminalWindow.scrollTop = terminalWindow.scrollHeight;
    }
  }

  // --- 6. Eventos y Controles de Mandos ---
  document.getElementById("btn-start").addEventListener("click", async () => {
    const res = await apiPost("/api/server/start");
    showToast(res.message, res.success ? "success" : "error");
    syncServerStatus();
  });

  document.getElementById("btn-restart").addEventListener("click", async () => {
    showToast("Reiniciando servidor y liberando sockets...", "info");
    const res = await apiPost("/api/server/restart");
    showToast(res.message, res.success ? "success" : "error");
    syncServerStatus();
  });

  document.getElementById("btn-stop").addEventListener("click", async () => {
    if (confirm("¿Seguro que deseas detener el servidor de ACC forzosamente?")) {
      const res = await apiPost("/api/server/stop");
      showToast(res.message, res.success ? "success" : "error");
      syncServerStatus();
    }
  });

  document.getElementById("auto-rotation-toggle").addEventListener("change", async () => {
    const res = await apiPost("/api/rotation/toggle");
    showToast(res.message, "info");
    syncServerStatus();
  });

  document.getElementById("btn-skip-track").addEventListener("click", async () => {
    showToast("Saltando a la siguiente pista del pool...", "info");
    const res = await apiPost("/api/rotation/skip");
    showToast(res.message, res.success ? "success" : "error");
    syncServerStatus();
    loadTracksPool();
  });

  document.getElementById("btn-apply-track").addEventListener("click", async () => {
    const val = document.getElementById("select-direct-track").value;
    if (!val) return;
    showToast(`Cambiando pista a ${val}...`, "info");
    const res = await apiPost("/api/rotation/select", { track_file: val });
    showToast(res.message, res.success ? "success" : "error");
    syncServerStatus();
    loadTracksPool();
  });

  const pAll = document.getElementById("btn-preset-all");
  const pBase = document.getElementById("btn-preset-base");
  const pDlc = document.getElementById("btn-preset-dlc");
  if (pAll) pAll.addEventListener("click", () => window.applyRotationPreset("all"));
  if (pBase) pBase.addEventListener("click", () => window.applyRotationPreset("base_only"));
  if (pDlc) pDlc.addEventListener("click", () => window.applyRotationPreset("dlc_only"));

  document.getElementById("btn-refresh-telemetry").addEventListener("click", () => {
    loadTelemetry();
    showToast("Telemetría actualizada.", "info");
  });

  document.getElementById("btn-refresh-logs").addEventListener("click", () => {
    loadLogs();
  });

  document.getElementById("btn-autoscroll-toggle").addEventListener("click", (ev) => {
    appState.autoScrollLogs = !appState.autoScrollLogs;
    ev.target.textContent = `Auto-Scroll: ${appState.autoScrollLogs ? "ON" : "OFF"}`;
    ev.target.className = `btn btn-sm btn-secondary ${appState.autoScrollLogs ? "active" : ""}`;
  });

  // --- 4.5. Pilotos en Vivo y Moderación (/api/players) ---
  async function loadPlayersData() {
    const data = await apiGet("/api/players");
    if (!data) return;

    // Contador en navbar
    const counter = document.getElementById("active-players-counter");
    if (counter) counter.textContent = data.total_active || 0;

    const countTag = document.getElementById("live-drivers-count-tag");
    if (countTag) countTag.textContent = `${data.total_active || 0} Pilotos en Línea`;

    // 1. Pilotos Activos en Vivo
    const activeTbody = document.getElementById("active-players-tbody");
    if (activeTbody) {
      const active = data.active_players || [];
      if (active.length === 0) {
        activeTbody.innerHTML = `
          <tr>
            <td colspan="7" class="text-center" style="padding: 2.5rem 1rem; color: var(--text-muted);">
              🏁 No hay pilotos conectados en pista en este momento (esperando conexiones en el lobby).
            </td>
          </tr>
        `;
      } else {
        activeTbody.innerHTML = active.map(p => {
          const pingClass = p.ping_ms < 60 ? "good" : (p.ping_ms < 140 ? "med" : "bad");
          const adminBadge = p.is_admin ? `<span class="badge-admin">👑 ADMIN</span>` : "";
          const bannedBadge = p.is_banned ? `<span class="badge-banned">🚫 BANEADO</span>` : "";
          const carNum = p.race_number !== null ? p.race_number : (p.car_id || "—");
          const steamProfile = steamProfileUrl(p.player_id);
          const driverPayload = encodePayload(p);

          return `
            <tr>
              <td><span class="car-number-badge">#${escapeHtml(carNum)}</span></td>
              <td>
                <span class="driver-pill">${escapeHtml(p.driver_name)}</span>
                ${adminBadge}${bannedBadge}
              </td>
              <td><span style="color: var(--accent-cyan); font-weight: 500;">${escapeHtml(p.car_model_name)}</span></td>
              <td><a href="${steamProfile}" target="_blank" rel="noopener noreferrer" class="steam-link">${escapeHtml(p.player_id)}</a></td>
              <td class="text-center"><span class="ping-pill ${pingClass}">${escapeHtml(p.ping_ms)} ms</span></td>
              <td class="text-center"><span style="color: var(--accent-green); font-weight: 600;">● En Pista</span></td>
              <td class="text-center">
                <button class="btn btn-sm btn-secondary" data-action="open-modal" data-payload="${driverPayload}">
                  ⚡ Moderar / Comandos
                </button>
              </td>
            </tr>
          `;
        }).join("");
      }
    }

    // 2. Pilotos Recientes
    const recentTbody = document.getElementById("recent-players-tbody");
    if (recentTbody) {
      const recent = data.recent_players || [];
      if (recent.length === 0) {
        recentTbody.innerHTML = `<tr><td colspan="8" class="text-center">No hay registros de sesiones recientes.</td></tr>`;
      } else {
        recentTbody.innerHTML = recent.map(p => {
          const adminBadge = p.is_admin ? `<span class="badge-admin">👑 ADMIN</span>` : "";
          const bannedBadge = p.is_banned ? `<span class="badge-banned">🚫 BANEADO</span>` : "";
          const steamProfile = steamProfileUrl(p.player_id);
          const driverPayload = encodePayload(p);

          return `
            <tr>
              <td><span class="car-number-badge">#${escapeHtml(p.race_number || '—')}</span></td>
              <td>
                <span class="driver-pill">${escapeHtml(p.driver_name)}</span>
                ${adminBadge}${bannedBadge}
              </td>
              <td><span style="color: var(--text-secondary);">${escapeHtml(p.car_model_name)}</span></td>
              <td><a href="${steamProfile}" target="_blank" rel="noopener noreferrer" class="steam-link">${escapeHtml(p.player_id)}</a></td>
              <td class="text-center" style="color: var(--accent-cyan); font-weight: 600;">${formatLapTime(p.best_lap_ms)}</td>
              <td class="text-center">${escapeHtml(p.total_laps)}</td>
              <td class="text-center">
                ${p.is_admin ? '<strong style="color: var(--accent-gold);">Admin</strong>' : (p.is_banned ? '<strong style="color: var(--accent-red);">Baneado</strong>' : 'Piloto')}
              </td>
              <td class="text-center" style="display: flex; gap: 0.3rem; justify-content: center;">
                <button class="btn btn-sm btn-secondary" data-action="open-modal" data-payload="${driverPayload}" title="Abrir centro de sanciones">
                  ⚡ Sanciones
                </button>
                <button class="btn btn-sm ${p.is_admin ? 'btn-stop' : 'btn-start'}" data-action="toggle-admin" data-payload="${driverPayload}" data-make-admin="${!p.is_admin}" title="Alternar Admin">
                  ${p.is_admin ? 'Quitar Admin' : 'Hacer Admin'}
                </button>
                <button class="btn btn-sm btn-stop" data-action="ban-player" data-payload="${driverPayload}" title="Añadir a lista negra">
                  🚫 Ban
                </button>
              </td>
            </tr>
          `;
        }).join("");
      }
    }

    // 3. Banlist / Lista Negra
    const banlistTbody = document.getElementById("banlist-tbody");
    if (banlistTbody) {
      const banlist = data.banlist || [];
      if (banlist.length === 0) {
        banlistTbody.innerHTML = `<tr><td colspan="4" class="text-center" style="color: var(--text-muted);">No hay pilotos en la lista negra.</td></tr>`;
      } else {
        banlistTbody.innerHTML = banlist.map(b => {
          const playerPayload = encodePayload({ player_id: b.playerId });
          return `
            <tr>
              <td><strong>${escapeHtml(b.driverName || 'Desconocido')}</strong></td>
              <td><code>${escapeHtml(b.playerId)}</code></td>
              <td><span style="color: var(--accent-red); font-size: 0.85rem;">${escapeHtml(b.reason || 'Sin motivo')}</span></td>
              <td class="text-center">
                <button class="btn btn-sm btn-secondary" data-action="unban-player" data-payload="${playerPayload}">
                  Desbanear
                </button>
              </td>
            </tr>
          `;
        }).join("");
      }
    }

    // 4. EntryList
    const entrylistTbody = document.getElementById("entrylist-tbody");
    if (entrylistTbody) {
      const el = data.entrylist || {};
      const entries = el.entries || [];
      
      const forceToggle = document.getElementById("toggle-force-entrylist");
      if (forceToggle) forceToggle.checked = el.forceEntryList === 1;

      if (entries.length === 0) {
        entrylistTbody.innerHTML = `<tr><td colspan="5" class="text-center" style="color: var(--text-muted);">No hay entradas configuradas en entrylist.json.</td></tr>`;
      } else {
        entrylistTbody.innerHTML = entries.map((e, idx) => {
          const d = (e.drivers && e.drivers.length > 0) ? e.drivers[0] : {};
          const dName = `${d.firstName || ''} ${d.lastName || ''}`.trim() || 'Piloto Registrado';
          const isAdmin = e.isServerAdmin === 1;
          return `
            <tr>
              <td><strong>${escapeHtml(dName)}</strong></td>
              <td><code>${escapeHtml(d.playerID || '—')}</code></td>
              <td class="text-center"><span class="car-number-badge">#${escapeHtml(e.raceNumber || '—')}</span></td>
              <td class="text-center">${isAdmin ? '<span class="badge-admin">👑 ADMIN VIP</span>' : '<span class="badge-tag">AUTORIZADO</span>'}</td>
              <td class="text-center">
                <button class="btn btn-sm btn-secondary" data-action="remove-entry" data-entry-index="${idx}">
                  Quitar
                </button>
              </td>
            </tr>
          `;
        }).join("");
      }
    }
  }

  // --- Ventana Modal de Moderación ---
  window.currentModDriver = null;
  window.currentModCar = null;
  let modalTrigger = null;

  window.openModModal = (driverPayload) => {
    const d = decodePayload(driverPayload);
    modalTrigger = document.activeElement;
    window.currentModDriver = d;
    window.currentModCar = d.race_number || d.car_id || 1;

    document.getElementById("mod-modal-car-badge").textContent = `#${window.currentModCar}`;
    document.getElementById("mod-modal-driver-name").textContent = d.driver_name || "Piloto";
    document.getElementById("mod-modal-car-model").textContent = d.car_model_name || "GT3";
    document.getElementById("mod-modal-steamid").textContent = d.player_id;
    
    const steamLink = document.getElementById("mod-modal-steam-link");
    steamLink.href = steamProfileUrl(d.player_id);
    steamLink.rel = "noopener noreferrer";

    const car = window.currentModCar;
    document.getElementById("btn-cmd-kick").querySelector(".cmd-text").textContent = `/kick ${car}`;
    document.getElementById("btn-cmd-ban").querySelector(".cmd-text").textContent = `/ban ${car}`;
    document.getElementById("btn-cmd-dq").querySelector(".cmd-text").textContent = `/dq ${car}`;
    document.getElementById("btn-cmd-dt").querySelector(".cmd-text").textContent = `/dt ${car}`;
    document.getElementById("btn-cmd-dtc").querySelector(".cmd-text").textContent = `/dtc ${car}`;
    document.getElementById("btn-cmd-sg10").querySelector(".cmd-text").textContent = `/sg10 ${car}`;
    document.getElementById("btn-cmd-sg30").querySelector(".cmd-text").textContent = `/sg30 ${car}`;
    document.getElementById("btn-cmd-tp5").querySelector(".cmd-text").textContent = `/tp5 ${car}`;
    document.getElementById("btn-cmd-tp15").querySelector(".cmd-text").textContent = `/tp15 ${car}`;
    document.getElementById("btn-cmd-clear").querySelector(".cmd-text").textContent = `/clear ${car}`;

    const adminBtn = document.getElementById("btn-mod-toggle-admin");
    adminBtn.querySelector("span").textContent = d.is_admin ? "👑 Quitar Administrador" : "👑 Asignar Administrador Permanente";

    document.getElementById("moderation-modal").classList.remove("hidden");
    document.getElementById("btn-close-mod-modal").focus();
  };

  function closeModModal() {
    document.getElementById("moderation-modal").classList.add("hidden");
    if (modalTrigger instanceof HTMLElement) modalTrigger.focus();
  }

  document.getElementById("btn-close-mod-modal").addEventListener("click", closeModModal);
  document.getElementById("btn-mod-modal-close").addEventListener("click", closeModModal);
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && !document.getElementById("moderation-modal").classList.contains("hidden")) {
      closeModModal();
    }
  });

  window.copyCommand = (cmd) => {
    navigator.clipboard.writeText(cmd).then(() => {
      showToast(`¡Comando copiado: "${cmd}"! Pégalo en el chat de ACC.`, "success");
    }).catch(() => {
      showToast(`Comando: ${cmd}`, "info");
    });
  };

  document.getElementById("btn-cmd-kick").addEventListener("click", () => window.copyCommand(`/kick ${window.currentModCar}`));
  document.getElementById("btn-cmd-ban").addEventListener("click", () => window.copyCommand(`/ban ${window.currentModCar}`));
  document.getElementById("btn-cmd-dq").addEventListener("click", () => window.copyCommand(`/dq ${window.currentModCar}`));
  document.getElementById("btn-cmd-dt").addEventListener("click", () => window.copyCommand(`/dt ${window.currentModCar}`));
  document.getElementById("btn-cmd-dtc").addEventListener("click", () => window.copyCommand(`/dtc ${window.currentModCar}`));
  document.getElementById("btn-cmd-sg10").addEventListener("click", () => window.copyCommand(`/sg10 ${window.currentModCar}`));
  document.getElementById("btn-cmd-sg30").addEventListener("click", () => window.copyCommand(`/sg30 ${window.currentModCar}`));
  document.getElementById("btn-cmd-tp5").addEventListener("click", () => window.copyCommand(`/tp5 ${window.currentModCar}`));
  document.getElementById("btn-cmd-tp15").addEventListener("click", () => window.copyCommand(`/tp15 ${window.currentModCar}`));
  document.getElementById("btn-cmd-clear").addEventListener("click", () => window.copyCommand(`/clear ${window.currentModCar}`));

  document.getElementById("btn-cmd-ballast").addEventListener("click", () => {
    const kg = document.getElementById("mod-ballast-val").value || 0;
    window.copyCommand(`/ballast ${window.currentModCar} ${kg}`);
  });

  document.getElementById("btn-cmd-restrictor").addEventListener("click", () => {
    const pct = document.getElementById("mod-restrictor-val").value || 0;
    window.copyCommand(`/restrictor ${window.currentModCar} ${pct}`);
  });

  document.getElementById("btn-mod-toggle-admin").addEventListener("click", async () => {
    if (!window.currentModDriver) return;
    const d = window.currentModDriver;
    const res = await apiPost("/api/moderation/admin", {
      playerId: d.player_id,
      driverName: d.driver_name,
      carNumber: window.currentModCar,
      isAdmin: !d.is_admin
    });
    showToast(res.message, res.success ? "success" : "error");
    closeModModal();
    loadPlayersData();
  });

  document.getElementById("btn-mod-add-ban").addEventListener("click", async () => {
    if (!window.currentModDriver) return;
    const d = window.currentModDriver;
    const reason = prompt(`Motivo de baneo para ${d.driver_name}:`, "Conducta antideportiva");
    if (!reason) return;
    const res = await apiPost("/api/moderation/ban", {
      playerId: d.player_id,
      driverName: d.driver_name,
      carNumber: window.currentModCar,
      reason: reason
    });
    showToast(res.message, res.success ? "success" : "error");
    closeModModal();
    loadPlayersData();
  });

  window.toggleAdminDirect = async (driverPayload, makeAdmin) => {
    const driver = decodePayload(driverPayload);
    const res = await apiPost("/api/moderation/admin", {
      playerId: driver.player_id,
      driverName: driver.driver_name,
      carNumber: driver.race_number || 99,
      isAdmin: makeAdmin
    });
    showToast(res.message, res.success ? "success" : "error");
    loadPlayersData();
  };

  window.banDirect = async (driverPayload) => {
    const driver = decodePayload(driverPayload);
    const reason = prompt(`Motivo de baneo para ${driver.driver_name}:`, "Conducta inapropiada");
    if (!reason) return;
    const res = await apiPost("/api/moderation/ban", {
      playerId: driver.player_id,
      driverName: driver.driver_name,
      carNumber: driver.race_number || 0,
      reason: reason
    });
    showToast(res.message, res.success ? "success" : "error");
    loadPlayersData();
  };

  window.unbanDirect = async (playerPayload) => {
    const player = decodePayload(playerPayload);
    if (!confirm(`¿Desbanear al piloto con SteamID ${player.player_id}?`)) return;
    const res = await apiPost("/api/moderation/unban", { playerId: player.player_id });
    showToast(res.message, res.success ? "success" : "error");
    loadPlayersData();
  };

  window.removeEntryDirect = async (entryIdx) => {
    const el = await apiGet("/api/entrylist");
    if (!el || !el.entries) return;
    el.entries.splice(entryIdx, 1);
    const res = await apiPost("/api/entrylist", el);
    showToast("Entrada removida de entrylist.", res.success ? "success" : "error");
    loadPlayersData();
  };

  document.addEventListener("change", event => {
    const control = event.target.closest("[data-action]");
    if (!control) return;
    if (control.dataset.action === "toggle-dlc") {
      window.toggleDlc(control.dataset.dlcId, control.checked);
    }
    if (control.dataset.action === "toggle-track") {
      window.toggleTrackRotation(control.dataset.trackFile, control.checked);
    }
  });

  document.addEventListener("click", event => {
    const control = event.target.closest("[data-action]");
    if (!control) return;
    const { action, payload, trackFile, makeAdmin, entryIndex } = control.dataset;
    try {
      if (action === "select-track") window.selectTrackDirect(trackFile);
      if (action === "open-modal") window.openModModal(payload);
      if (action === "toggle-admin") window.toggleAdminDirect(payload, makeAdmin === "true");
      if (action === "ban-player") window.banDirect(payload);
      if (action === "unban-player") window.unbanDirect(payload);
      if (action === "remove-entry") window.removeEntryDirect(Number(entryIndex));
    } catch {
      showToast("La acción contiene datos inválidos.", "error");
    }
  });

  document.getElementById("form-add-ban").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const pid = document.getElementById("ban-input-pid").value.trim();
    const name = document.getElementById("ban-input-name").value.trim();
    const reason = document.getElementById("ban-input-reason").value.trim();

    const res = await apiPost("/api/moderation/ban", {
      playerId: pid,
      driverName: name,
      carNumber: 0,
      reason: reason
    });
    showToast(res.message, res.success ? "success" : "error");
    document.getElementById("form-add-ban").reset();
    loadPlayersData();
  });

  document.getElementById("form-add-entry").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const pid = document.getElementById("entry-input-pid").value.trim();
    const name = document.getElementById("entry-input-name").value.trim();
    const carNum = parseInt(document.getElementById("entry-input-num").value, 10) || 99;
    const isAdmin = document.getElementById("entry-input-is-admin").checked;

    const res = await apiPost("/api/moderation/admin", {
      playerId: pid,
      driverName: name,
      carNumber: carNum,
      isAdmin: isAdmin
    });
    showToast(res.message, res.success ? "success" : "error");
    document.getElementById("form-add-entry").reset();
    loadPlayersData();
  });

  document.getElementById("toggle-force-entrylist").addEventListener("change", async (ev) => {
    const el = await apiGet("/api/entrylist");
    if (!el) return;
    el.forceEntryList = ev.target.checked ? 1 : 0;
    const res = await apiPost("/api/entrylist", el);
    showToast(`Modo Whitelist (forceEntryList): ${ev.target.checked ? 'ACTIVADO' : 'DESACTIVADO'}`, res.success ? "success" : "error");
  });

  document.getElementById("btn-refresh-players").addEventListener("click", () => {
    loadPlayersData();
    showToast("Pilotos actualizados.", "info");
  });

  // --- 7. Navegación por Pestañas ---
  const tabButtons = document.querySelectorAll(".tab-btn");
  tabButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      tabButtons.forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

      btn.classList.add("active");
      const targetId = btn.getAttribute("data-tab");
      document.getElementById(targetId).classList.add("active");
      appState.currentTab = targetId;

      if (targetId === "tab-config") loadConfigData();
      if (targetId === "tab-logs") loadLogs();
      if (targetId === "tab-telemetry") loadTelemetry();
      if (targetId === "tab-tracks") loadTracksPool();
      if (targetId === "tab-players") loadPlayersData();
    });
  });

  // --- 8. Inicialización y Bucles de Sondeo (Polling) ---
  syncServerStatus();
  loadTracksPool();
  loadTelemetry();
  loadPlayersData();

  // Bucle de estado cada 3 segundos
  setInterval(() => {
    syncServerStatus();
    if (appState.currentTab === "tab-logs") {
      loadLogs();
    }
    if (appState.currentTab === "tab-players") {
      loadPlayersData();
    }
  }, 3000);
});
