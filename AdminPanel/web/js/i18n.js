/**
 * ASSETTO CORSA COMPETIZIONE — RACE CONTROL (idiomas)
 * Español (por defecto) e inglés. Los textos fijos del HTML se marcan con:
 *   data-i18n="clave"            → textContent
 *   data-i18n-html="clave"       → innerHTML (sólo textos propios con <code>/<strong>)
 *   data-i18n-attr="attr:clave;…" → atributos (placeholder, title, aria-label…)
 * Los elementos con data-loaded="1" ya muestran datos reales y no se sobrescriben.
 * El backend responde en español; translateServer() traduce sus mensajes conocidos.
 */
(function () {
  const STORAGE_KEY = "acc-panel-lang";
  const DEFAULT_LANG = "es";

  const STRINGS = {
    es: {
      // --- Página y cabecera ---
      "meta.title": "ACC Race Control — Panel de administración",
      "brand.subtitle": "Assetto Corsa Competizione · Servidor dedicado",
      "header.ports": "Puertos UDP / TCP",
      "header.uptime": "Tiempo en línea",
      "header.panel": "Panel",
      "header.versionBanner": "El ACC_AdminPanel.exe en ejecución es anterior a esta interfaz: algunos datos (pilotos en vivo, puertos) no estarán disponibles. Ciérralo y recompílalo con build_release.bat, o ejecuta AdminPanel\\panel_server.py.",
      "lang.groupAria": "Idioma de la interfaz",
      "conn.ok": "Conectado",
      "conn.lost": "Sin conexión",
      "conn.offlineBanner": "Sin conexión con el panel. Comprueba que ACC_AdminPanel sigue abierto; reintentando…",
      "conn.unauthorized": "Acceso no autorizado: abre el panel con el enlace que se abre al iniciarlo (incluye el token).",
      "api.httpError": "Error HTTP {status}",
      "api.noConnection": "Sin conexión con el panel.",

      // --- Estado del servidor ---
      "status.online": "ONLINE",
      "status.unmanaged": "EXTERNO",
      "status.offline": "OFFLINE",
      "status.subUnmanaged": "accServer no gestionado",
      "status.subOffline": "accServer detenido",
      "status.waiting": "En espera",
      "status.querying": "Consultando estado…",

      // --- Controles ---
      "controls.aria": "Controles del servidor",
      "controls.server": "Servidor accServer",
      "controls.start": "Iniciar",
      "controls.restart": "Reiniciar",
      "controls.stop": "Detener",
      "controls.rotation": "Rotación de circuitos",
      "controls.autoRotationTitle": "Rota automáticamente a la siguiente pista tras la carrera final del evento",
      "controls.autoRotation": "Auto-rotación",
      "controls.skipTrack": "Siguiente pista",
      "controls.skipTrackTitle": "Detiene el servidor y carga la siguiente pista del pool",
      "controls.selectTrack": "Seleccionar circuito",
      "controls.load": "Cargar",
      "rotation.active": "ACTIVA",
      "rotation.paused": "PAUSADA",
      "rotation.updateError": "No se pudo actualizar la rotación.",
      "rotation.toggleError": "No se pudo cambiar la auto-rotación.",
      "rotation.confirmSkip": "Saltar de pista reinicia accServer y desconecta a los pilotos. ¿Continuar?",
      "server.confirmRestart": "Reiniciar accServer desconectará a todos los pilotos. ¿Continuar?",
      "server.restarting": "Reiniciando servidor y liberando puertos…",
      "server.confirmStop": "¿Detener accServer? Los pilotos conectados serán desconectados.",

      // --- KPI ---
      "kpi.aria": "Resumen del servidor",
      "kpi.process": "Proceso",
      "kpi.track": "Circuito",
      "kpi.weekend": "Fin de semana",
      "kpi.raceLocked": "Cierre en carrera:",
      "kpi.grid": "Parrilla",
      "kpi.weather": "Temp {temp}°C · Nubes {clouds} · Lluvia {rain}",
      "kpi.weatherEmpty": "Clima: —",
      "kpi.noSessions": "Sin sesiones en event.json",
      "kpi.slots": "{n} SLOTS",
      "kpi.maxConnections": "Max conexiones: {n}",
      "kpi.maxConnectionsEmpty": "Max Conx: —",

      // --- Pestañas ---
      "tabs.aria": "Secciones del panel",
      "tabs.telemetry": "Telemetría",
      "tabs.players": "Pilotos",
      "tabs.playersCounterAria": "pilotos conectados",
      "tabs.config": "Configuración",
      "tabs.tracks": "Circuitos",
      "tabs.logs": "Consola",

      // --- Columnas y comunes ---
      "common.refresh": "Actualizar",
      "col.pos": "Pos",
      "col.driver": "Piloto",
      "col.wins": "Victorias",
      "col.podiums": "Podios",
      "col.races": "Carreras",
      "col.laps": "Vueltas",
      "col.number": "Dorsal",
      "col.car": "Coche",
      "col.connCar": "Conexión / Coche",
      "col.status": "Estado",
      "col.raceControl": "Control de carrera",
      "col.bestLap": "Mejor vuelta",
      "col.role": "Rol",
      "col.actions": "Acciones",
      "col.reason": "Motivo",
      "col.action": "Acción",
      "col.rank": "Rango",

      // --- Telemetría ---
      "telemetry.records": "Récords de vuelta",
      "telemetry.recordsSub": "Mejor vuelta registrada por circuito en results/*.json",
      "telemetry.ranking": "Clasificación de pilotos",
      "telemetry.rankingTag": "victorias · podios",
      "telemetry.rankingCaption": "Clasificación de pilotos por victorias y podios",
      "telemetry.sessions": "Últimas sesiones",
      "telemetry.loadError": "No se pudo cargar la telemetría",
      "telemetry.loadErrorText": "Se reintentará con «Actualizar».",
      "telemetry.noRecords": "Sin récords todavía",
      "telemetry.noRecordsText": "Aparecerán cuando se complete una vuelta válida en cualquier sesión.",
      "telemetry.noDrivers": "Sin pilotos registrados",
      "telemetry.noDriversText": "La clasificación se construye con los resultados de carrera.",
      "telemetry.footnote": "Mostrando los {limit} primeros de {total} pilotos.",
      "telemetry.noClassified": "Sin clasificados",
      "telemetry.drivers": "{n} pilotos",
      "telemetry.fastestLap": "Vuelta rápida",
      "telemetry.noSessions": "Sin sesiones en results/",
      "telemetry.noSessionsText": "ACC escribe un archivo al terminar cada sesión (dumpLeaderboards = 1).",

      // --- Pilotos ---
      "players.heading": "Pilotos y control de carrera",
      "players.sub": "Conexiones en vivo desde server.log, historial de resultados, lista negra y entry list",
      "players.live": "En pista ahora",
      "players.liveCaption": "Pilotos conectados en este momento",
      "players.recent": "Pilotos de sesiones recientes",
      "players.recentCaption": "Pilotos vistos en las últimas sesiones",
      "players.onlineOne": "{n} piloto en línea{session}",
      "players.onlineMany": "{n} pilotos en línea{session}",
      "players.sourceStream": "Datos en tiempo real desde la consola de accServer",
      "players.sourceLog": "Datos desde server.log: accServer lo escribe con buffer y puede ir con retraso",
      "players.queryError": "No se pudo consultar /api/players",
      "players.queryErrorText": "Se reintentará automáticamente.",
      "players.logError": "No se pudo leer server.log",
      "players.outdated": "Backend desactualizado",
      "players.outdatedText": "Recompila ACC_AdminPanel.exe (build_release.bat) para ver pilotos en vivo.",
      "players.stopped": "Servidor detenido",
      "players.stoppedText": "Inicia accServer desde el panel para ver a los pilotos en vivo.",
      "players.empty": "Pista vacía",
      "players.emptyText": "Esperando conexiones en el lobby.",
      "players.connTitle": "connId / carId según server.log",
      "players.lagTitle": "accServer no recibe paquetes UDP del piloto desde hace {ms} ms",
      "players.lag": "LAG {s} s",
      "players.onTrack": "EN PISTA",
      "players.moderate": "Moderar",
      "players.removeAdmin": "Quitar admin",
      "players.makeAdmin": "Hacer admin",
      "players.ban": "Ban",
      "players.banAria": "Añadir {name} a la lista negra",
      "players.noHistory": "Sin historial",
      "players.noHistoryText": "Todavía no hay pilotos en results/.",
      "badge.admin": "ADMIN",
      "badge.banned": "BANEADO",
      "role.admin": "Admin",
      "role.banned": "Baneado",
      "role.driver": "Piloto",

      // --- Lista negra ---
      "ban.title": "Lista negra",
      "ban.note": "Registro del panel: accServer no lee este archivo. Para impedir el acceso de forma permanente usa la entry list con whitelist estricta; <code>/ban</code> en el chat sólo dura hasta reiniciar el servidor.",
      "ban.formAria": "Añadir piloto a la lista negra",
      "ban.submit": "Banear",
      "ban.caption": "Pilotos en la lista negra",
      "ban.unknown": "Desconocido",
      "ban.noReason": "Sin motivo",
      "ban.unban": "Desbanear",
      "ban.empty": "Lista negra vacía",
      "ban.promptReason": "Motivo del baneo para {name}:",
      "ban.defaultReason": "Conducta antideportiva",
      "ban.confirmUnban": "¿Quitar de la lista negra a {id}?",
      "form.steamIdPlaceholder": "Steam ID (S7656…)",
      "form.driverName": "Nombre del piloto",
      "form.reason": "Motivo",

      // --- Entry list ---
      "entry.title": "Entry list y administradores",
      "entry.force": "<strong>Whitelist estricta (forceEntryList):</strong> sólo podrán entrar los pilotos registrados",
      "entry.formAria": "Registrar piloto en la entry list",
      "entry.adminTitle": "Asigna rango de administrador sin escribir /admin",
      "entry.admin": "Admin",
      "entry.submit": "Registrar",
      "entry.caption": "Pilotos registrados en la entry list",
      "entry.registered": "Piloto registrado",
      "entry.authorized": "AUTORIZADO",
      "entry.remove": "Quitar",
      "entry.empty": "Entry list vacía",
      "entry.emptyText": "Registra pilotos para darles dorsal fijo o rango de administrador.",
      "entry.confirmRemove": "¿Quitar a {name} ({id}) de la entry list?",
      "entry.removeError": "No se pudo quitar la entrada.",
      "entry.forceError": "No se pudo cambiar la whitelist.",

      // --- Configuración ---
      "config.utf16Title": "Codificación UTF-16 LE protegida",
      "config.utf16Text": "Al guardar, el panel escribe <code>settings.json</code>, <code>configuration.json</code>, <code>assistRules.json</code> y <code>event.json</code> en UTF-16 LE con BOM, como exige ACC. Las contraseñas nunca se envían al navegador.",
      "config.server": "Servidor",
      "config.serverName": "Nombre de la sala",
      "config.adminPassword": "Contraseña de administrador",
      "config.adminPasswordHint": "Déjala vacía para conservar la actual.",
      "config.serverPassword": "Contraseña de acceso",
      "config.clearPassword": "Quitar contraseña (sala pública)",
      "config.unchanged": "Sin cambios",
      "config.passwordSet": "•••••••• (sin cambios)",
      "config.required": "Obligatoria",
      "config.publicRoom": "Sala pública (sin contraseña)",
      "config.maxSlots": "Slots de coches",
      "config.raceLocked": "Cierre en carrera",
      "config.carGroup": "Categoría",
      "config.dumpHint": "Fijo en 1: la rotación lo necesita.",
      "config.sessions": "Sesiones",
      "config.practice": "Práctica (min)",
      "config.qualifying": "Clasificación (min)",
      "config.race": "Carrera (min)",
      "config.weather": "Clima",
      "config.temp": "Temperatura (°C)",
      "config.randomness": "Variabilidad (0–10)",
      "config.clouds": "Nubes (0.0–1.0)",
      "config.rain": "Lluvia (0.0–1.0)",
      "config.assists": "Ayudas de conducción",
      "config.stability": "Control de estabilidad máx. (%)",
      "config.idealLine": "Línea ideal",
      "config.save": "Guardar configuración",
      "config.saveTip": "Los cambios de evento se aplican en el próximo arranque o reinicio del servidor.",
      "config.loadError": "No se pudo cargar la configuración.",
      "config.notLoaded": "La configuración aún no se ha cargado.",
      "config.saved": "Configuración guardada en UTF-16 LE. Se aplicará en el próximo arranque.",
      "config.saveError": "No se pudo guardar la configuración.",
      "opt.locked": "Bloqueado",
      "opt.open": "Abierto",
      "opt.allowed": "Permitida",
      "opt.forbidden": "Prohibida",

      // --- Circuitos ---
      "tracks.heading": "Catálogo y rotación por DLC",
      "tracks.sub": "Elige qué paquetes y circuitos entran en la rotación automática",
      "tracks.inRotationStat": "En rotación",
      "tracks.presets": "Presets",
      "tracks.presetsAria": "Presets de rotación",
      "tracks.presetAll": "Todos (base + DLC)",
      "tracks.presetBase": "Sólo juego base",
      "tracks.presetDlc": "Sólo DLC",
      "tracks.packToggles": "Interruptores por paquete",
      "tracks.packHelper": "Activa o desactiva un paquete completo",
      "tracks.loading": "Cargando circuitos…",
      "tracks.loadError": "No se pudo cargar el catálogo",
      "tracks.loadErrorText": "Se reintentará al volver a abrir la pestaña.",
      "tracks.currentSuffix": " · actual",
      "tracks.inRotationLower": "en rotación",
      "tracks.includeAria": "Incluir {name} en la rotación",
      "tracks.includeAllAria": "Incluir todo {name} en la rotación",
      "tracks.onTrack": "EN PISTA",
      "tracks.temp": "Temp",
      "tracks.rain": "Lluvia",
      "tracks.clouds": "Nubes",
      "tracks.overtime": "Overtime",
      "tracks.inRotation": "En rotación",
      "tracks.excluded": "Excluido",
      "tracks.current": "Pista actual",
      "tracks.load": "Cargar pista",
      "tracks.baseGame": "Juego base",
      "tracks.countOf": "{active} de {total} en rotación",
      "tracks.confirmLoad": "Cargar {file} reinicia accServer y desconecta a los pilotos. ¿Continuar?",
      "tracks.loadingToast": "Cargando {file}…",

      // --- Consola ---
      "logs.live": "EN VIVO",
      "logs.hideSpamTitle": "Oculta las líneas '==ERR: onCarUpdate ... timestamp is N ms in the future'",
      "logs.hideSpam": "Ocultar spam onCarUpdate",
      "logs.lines": "Líneas",
      "logs.refresh": "Refrescar",
      "logs.autoscroll": "Auto-scroll",
      "logs.autoscrollPaused": "Auto-scroll (pausado)",
      "logs.terminalAria": "Contenido de server.log",
      "logs.loading": "Cargando registros del servidor…",
      "logs.hiddenCount": "{n} líneas de spam ocultas",

      // --- Modal de moderación ---
      "modal.driver": "Piloto",
      "modal.closeAria": "Cerrar ventana de moderación",
      "modal.steamProfile": "Perfil de Steam ↗",
      "modal.commands": "Comandos de dirección de carrera",
      "modal.commandsSub": "Haz clic para copiar el comando y pégalo en el chat de ACC (requiere /admin).",
      "cmd.kick": "Expulsar del fin de semana",
      "cmd.ban": "Banear hasta reinicio",
      "cmd.dq": "Descalificar",
      "cmd.dt": "Drive-through",
      "cmd.dtc": "DT por colisión",
      "cmd.sg10": "Stop & Go 10 s",
      "cmd.sg30": "Stop & Go 30 s",
      "cmd.clear": "Limpiar sanciones",
      "modal.ballast": "Lastre (0–100 kg)",
      "modal.copyBallast": "Copiar /ballast",
      "modal.restrictor": "Restrictor (0–20 %)",
      "modal.copyRestrictor": "Copiar /restrictor",
      "modal.permanent": "Acciones permanentes por Steam ID",
      "modal.assignAdmin": "Asignar administrador",
      "modal.removeAdmin": "Quitar administrador",
      "modal.addBan": "Añadir a lista negra",
      "modal.close": "Cerrar",
      "copy.copied": "Copiado «{cmd}». Pégalo en el chat de ACC.",
      "copy.fallback": "Comando: {cmd}",
      "action.invalidData": "La acción contiene datos inválidos."
    },

    en: {
      // --- Page and header ---
      "meta.title": "ACC Race Control — Admin panel",
      "brand.subtitle": "Assetto Corsa Competizione · Dedicated server",
      "header.ports": "UDP / TCP ports",
      "header.uptime": "Uptime",
      "header.panel": "Panel",
      "header.versionBanner": "The running ACC_AdminPanel.exe is older than this interface: some data (live drivers, ports) will not be available. Close it and rebuild it with build_release.bat, or run AdminPanel\\panel_server.py.",
      "lang.groupAria": "Interface language",
      "conn.ok": "Connected",
      "conn.lost": "Disconnected",
      "conn.offlineBanner": "No connection to the panel. Check that ACC_AdminPanel is still open; retrying…",
      "conn.unauthorized": "Unauthorized access: open the panel with the link that opens when it starts (it includes the token).",
      "api.httpError": "HTTP error {status}",
      "api.noConnection": "No connection to the panel.",

      // --- Server status ---
      "status.online": "ONLINE",
      "status.unmanaged": "EXTERNAL",
      "status.offline": "OFFLINE",
      "status.subUnmanaged": "Unmanaged accServer",
      "status.subOffline": "accServer stopped",
      "status.waiting": "Idle",
      "status.querying": "Checking status…",

      // --- Controls ---
      "controls.aria": "Server controls",
      "controls.server": "accServer control",
      "controls.start": "Start",
      "controls.restart": "Restart",
      "controls.stop": "Stop",
      "controls.rotation": "Track rotation",
      "controls.autoRotationTitle": "Automatically rotates to the next track after the event's final race",
      "controls.autoRotation": "Auto-rotation",
      "controls.skipTrack": "Next track",
      "controls.skipTrackTitle": "Stops the server and loads the next track in the pool",
      "controls.selectTrack": "Select track",
      "controls.load": "Load",
      "rotation.active": "ACTIVE",
      "rotation.paused": "PAUSED",
      "rotation.updateError": "Could not update the rotation.",
      "rotation.toggleError": "Could not change auto-rotation.",
      "rotation.confirmSkip": "Skipping the track restarts accServer and disconnects the drivers. Continue?",
      "server.confirmRestart": "Restarting accServer will disconnect all drivers. Continue?",
      "server.restarting": "Restarting server and releasing ports…",
      "server.confirmStop": "Stop accServer? Connected drivers will be disconnected.",

      // --- KPI ---
      "kpi.aria": "Server overview",
      "kpi.process": "Process",
      "kpi.track": "Track",
      "kpi.weekend": "Weekend",
      "kpi.raceLocked": "Race lock:",
      "kpi.grid": "Grid",
      "kpi.weather": "Temp {temp}°C · Clouds {clouds} · Rain {rain}",
      "kpi.weatherEmpty": "Weather: —",
      "kpi.noSessions": "No sessions in event.json",
      "kpi.slots": "{n} SLOTS",
      "kpi.maxConnections": "Max connections: {n}",
      "kpi.maxConnectionsEmpty": "Max conn.: —",

      // --- Tabs ---
      "tabs.aria": "Panel sections",
      "tabs.telemetry": "Telemetry",
      "tabs.players": "Drivers",
      "tabs.playersCounterAria": "connected drivers",
      "tabs.config": "Settings",
      "tabs.tracks": "Tracks",
      "tabs.logs": "Console",

      // --- Columns and common ---
      "common.refresh": "Refresh",
      "col.pos": "Pos",
      "col.driver": "Driver",
      "col.wins": "Wins",
      "col.podiums": "Podiums",
      "col.races": "Races",
      "col.laps": "Laps",
      "col.number": "Number",
      "col.car": "Car",
      "col.connCar": "Connection / Car",
      "col.status": "Status",
      "col.raceControl": "Race control",
      "col.bestLap": "Best lap",
      "col.role": "Role",
      "col.actions": "Actions",
      "col.reason": "Reason",
      "col.action": "Action",
      "col.rank": "Rank",

      // --- Telemetry ---
      "telemetry.records": "Lap records",
      "telemetry.recordsSub": "Best recorded lap per track in results/*.json",
      "telemetry.ranking": "Driver standings",
      "telemetry.rankingTag": "wins · podiums",
      "telemetry.rankingCaption": "Driver standings by wins and podiums",
      "telemetry.sessions": "Recent sessions",
      "telemetry.loadError": "Could not load telemetry",
      "telemetry.loadErrorText": "Use “Refresh” to try again.",
      "telemetry.noRecords": "No records yet",
      "telemetry.noRecordsText": "They will appear once a valid lap is completed in any session.",
      "telemetry.noDrivers": "No drivers recorded",
      "telemetry.noDriversText": "The standings are built from race results.",
      "telemetry.footnote": "Showing the top {limit} of {total} drivers.",
      "telemetry.noClassified": "No classified drivers",
      "telemetry.drivers": "{n} drivers",
      "telemetry.fastestLap": "Fastest lap",
      "telemetry.noSessions": "No sessions in results/",
      "telemetry.noSessionsText": "ACC writes a file at the end of each session (dumpLeaderboards = 1).",

      // --- Drivers ---
      "players.heading": "Drivers and race control",
      "players.sub": "Live connections from server.log, results history, blacklist and entry list",
      "players.live": "On track now",
      "players.liveCaption": "Drivers connected right now",
      "players.recent": "Drivers from recent sessions",
      "players.recentCaption": "Drivers seen in the latest sessions",
      "players.onlineOne": "{n} driver online{session}",
      "players.onlineMany": "{n} drivers online{session}",
      "players.sourceStream": "Real-time data from the accServer console",
      "players.sourceLog": "Data from server.log: accServer writes it buffered, so it may lag behind",
      "players.queryError": "Could not query /api/players",
      "players.queryErrorText": "It will retry automatically.",
      "players.logError": "Could not read server.log",
      "players.outdated": "Outdated backend",
      "players.outdatedText": "Rebuild ACC_AdminPanel.exe (build_release.bat) to see live drivers.",
      "players.stopped": "Server stopped",
      "players.stoppedText": "Start accServer from the panel to see live drivers.",
      "players.empty": "Empty track",
      "players.emptyText": "Waiting for connections in the lobby.",
      "players.connTitle": "connId / carId according to server.log",
      "players.lagTitle": "accServer has not received UDP packets from this driver for {ms} ms",
      "players.lag": "LAG {s} s",
      "players.onTrack": "ON TRACK",
      "players.moderate": "Moderate",
      "players.removeAdmin": "Remove admin",
      "players.makeAdmin": "Make admin",
      "players.ban": "Ban",
      "players.banAria": "Add {name} to the blacklist",
      "players.noHistory": "No history",
      "players.noHistoryText": "There are no drivers in results/ yet.",
      "badge.admin": "ADMIN",
      "badge.banned": "BANNED",
      "role.admin": "Admin",
      "role.banned": "Banned",
      "role.driver": "Driver",

      // --- Blacklist ---
      "ban.title": "Blacklist",
      "ban.note": "Panel record only: accServer does not read this file. To block access permanently, use the entry list with a strict whitelist; <code>/ban</code> in chat only lasts until the server restarts.",
      "ban.formAria": "Add driver to the blacklist",
      "ban.submit": "Ban",
      "ban.caption": "Blacklisted drivers",
      "ban.unknown": "Unknown",
      "ban.noReason": "No reason",
      "ban.unban": "Unban",
      "ban.empty": "Blacklist is empty",
      "ban.promptReason": "Ban reason for {name}:",
      "ban.defaultReason": "Unsporting behaviour",
      "ban.confirmUnban": "Remove {id} from the blacklist?",
      "form.steamIdPlaceholder": "Steam ID (S7656…)",
      "form.driverName": "Driver name",
      "form.reason": "Reason",

      // --- Entry list ---
      "entry.title": "Entry list and administrators",
      "entry.force": "<strong>Strict whitelist (forceEntryList):</strong> only registered drivers can join",
      "entry.formAria": "Register driver in the entry list",
      "entry.adminTitle": "Grants administrator rank without typing /admin",
      "entry.admin": "Admin",
      "entry.submit": "Register",
      "entry.caption": "Drivers registered in the entry list",
      "entry.registered": "Registered driver",
      "entry.authorized": "AUTHORIZED",
      "entry.remove": "Remove",
      "entry.empty": "Entry list is empty",
      "entry.emptyText": "Register drivers to give them a fixed number or administrator rank.",
      "entry.confirmRemove": "Remove {name} ({id}) from the entry list?",
      "entry.removeError": "Could not remove the entry.",
      "entry.forceError": "Could not change the whitelist.",

      // --- Settings ---
      "config.utf16Title": "UTF-16 LE encoding protected",
      "config.utf16Text": "When saving, the panel writes <code>settings.json</code>, <code>configuration.json</code>, <code>assistRules.json</code> and <code>event.json</code> as UTF-16 LE with BOM, as ACC requires. Passwords are never sent to the browser.",
      "config.server": "Server",
      "config.serverName": "Server name",
      "config.adminPassword": "Admin password",
      "config.adminPasswordHint": "Leave it empty to keep the current one.",
      "config.serverPassword": "Join password",
      "config.clearPassword": "Remove password (public server)",
      "config.unchanged": "Unchanged",
      "config.passwordSet": "•••••••• (unchanged)",
      "config.required": "Required",
      "config.publicRoom": "Public server (no password)",
      "config.maxSlots": "Car slots",
      "config.raceLocked": "Race lock",
      "config.carGroup": "Car group",
      "config.dumpHint": "Fixed at 1: the rotation needs it.",
      "config.sessions": "Sessions",
      "config.practice": "Practice (min)",
      "config.qualifying": "Qualifying (min)",
      "config.race": "Race (min)",
      "config.weather": "Weather",
      "config.temp": "Temperature (°C)",
      "config.randomness": "Randomness (0–10)",
      "config.clouds": "Clouds (0.0–1.0)",
      "config.rain": "Rain (0.0–1.0)",
      "config.assists": "Driving aids",
      "config.stability": "Max stability control (%)",
      "config.idealLine": "Ideal line",
      "config.save": "Save settings",
      "config.saveTip": "Event changes apply on the next server start or restart.",
      "config.loadError": "Could not load the settings.",
      "config.notLoaded": "The settings have not loaded yet.",
      "config.saved": "Settings saved as UTF-16 LE. They will apply on the next start.",
      "config.saveError": "Could not save the settings.",
      "opt.locked": "Locked",
      "opt.open": "Open",
      "opt.allowed": "Allowed",
      "opt.forbidden": "Forbidden",

      // --- Tracks ---
      "tracks.heading": "Catalog and rotation by DLC",
      "tracks.sub": "Choose which packs and tracks are part of the automatic rotation",
      "tracks.inRotationStat": "In rotation",
      "tracks.presets": "Presets",
      "tracks.presetsAria": "Rotation presets",
      "tracks.presetAll": "All (base + DLC)",
      "tracks.presetBase": "Base game only",
      "tracks.presetDlc": "DLC only",
      "tracks.packToggles": "Pack switches",
      "tracks.packHelper": "Enable or disable an entire pack",
      "tracks.loading": "Loading tracks…",
      "tracks.loadError": "Could not load the catalog",
      "tracks.loadErrorText": "It will retry when you reopen the tab.",
      "tracks.currentSuffix": " · current",
      "tracks.inRotationLower": "in rotation",
      "tracks.includeAria": "Include {name} in the rotation",
      "tracks.includeAllAria": "Include all of {name} in the rotation",
      "tracks.onTrack": "ON TRACK",
      "tracks.temp": "Temp",
      "tracks.rain": "Rain",
      "tracks.clouds": "Clouds",
      "tracks.overtime": "Overtime",
      "tracks.inRotation": "In rotation",
      "tracks.excluded": "Excluded",
      "tracks.current": "Current track",
      "tracks.load": "Load track",
      "tracks.baseGame": "Base game",
      "tracks.countOf": "{active} of {total} in rotation",
      "tracks.confirmLoad": "Loading {file} restarts accServer and disconnects the drivers. Continue?",
      "tracks.loadingToast": "Loading {file}…",

      // --- Console ---
      "logs.live": "LIVE",
      "logs.hideSpamTitle": "Hides the lines '==ERR: onCarUpdate ... timestamp is N ms in the future'",
      "logs.hideSpam": "Hide onCarUpdate spam",
      "logs.lines": "Lines",
      "logs.refresh": "Refresh",
      "logs.autoscroll": "Auto-scroll",
      "logs.autoscrollPaused": "Auto-scroll (paused)",
      "logs.terminalAria": "server.log contents",
      "logs.loading": "Loading server logs…",
      "logs.hiddenCount": "{n} spam lines hidden",

      // --- Moderation modal ---
      "modal.driver": "Driver",
      "modal.closeAria": "Close moderation window",
      "modal.steamProfile": "Steam profile ↗",
      "modal.commands": "Race direction commands",
      "modal.commandsSub": "Click to copy the command and paste it in the ACC chat (requires /admin).",
      "cmd.kick": "Kick from the weekend",
      "cmd.ban": "Ban until restart",
      "cmd.dq": "Disqualify",
      "cmd.dt": "Drive-through",
      "cmd.dtc": "DT for collision",
      "cmd.sg10": "Stop & Go 10 s",
      "cmd.sg30": "Stop & Go 30 s",
      "cmd.clear": "Clear penalties",
      "modal.ballast": "Ballast (0–100 kg)",
      "modal.copyBallast": "Copy /ballast",
      "modal.restrictor": "Restrictor (0–20 %)",
      "modal.copyRestrictor": "Copy /restrictor",
      "modal.permanent": "Permanent actions by Steam ID",
      "modal.assignAdmin": "Assign administrator",
      "modal.removeAdmin": "Remove administrator",
      "modal.addBan": "Add to blacklist",
      "modal.close": "Close",
      "copy.copied": "Copied “{cmd}”. Paste it in the ACC chat.",
      "copy.fallback": "Command: {cmd}",
      "action.invalidData": "The action contains invalid data."
    }
  };

  // Nombres y descripciones de los paquetes (el backend los envía en español).
  const DLC_EN = {
    base: { name: "Base Game", description: "Blancpain GT Series (11 main European circuits)" },
    igtc: { description: "Worldwide endurance championship (4 circuits)" },
    british_gt: { description: "Traditional British circuits (3 circuits)" },
    usa: { description: "Iconic North American circuits (3 circuits)" },
    gtw_2020: { description: "Imola layout" },
    gtw_2023: { description: "Circuit Ricardo Tormo, Valencia" },
    gt2: { description: "Red Bull Ring Spielberg" },
    nurburgring_24h: { description: "Nürburgring Nordschleife 24h" }
  };
  const DLC_NAME_EN_BY_ES = { "Juego Base": "Base Game" };

  // Mensajes del backend (panel_server.py) → inglés. Se evalúan en orden; la primera coincidencia gana.
  const SERVER_MESSAGES_EN = [
    [/^Servidor inicializado$/, () => "Server initialized"],
    [/^Servidor en línea en pista: (.+)$/, m => `Server online on track: ${m[1]}`],
    [/^Carrera terminada: (.+)\. Esperando 12s para podio\.\.\.$/, m => `Race finished: ${m[1]}. Waiting 12 s for the podium...`],
    [/^Resultado (.+) registrado; no es la carrera final del evento actual\.$/, m => `Result ${m[1]} recorded; it is not the final race of the current event.`],
    [/^Rotación fallida al iniciar (.+?): ([\s\S]*)$/, m => `Rotation failed while starting ${m[1]}: ${translateServerEn(m[2])}`],
    [/^No hay un accServer gestionado por este panel para detener\.$/, () => "There is no accServer managed by this panel to stop."],
    [/^No hay un accServer gestionado para detener\.$/, () => "There is no managed accServer to stop."],
    [/^accServer \(PID (\d+)\) sigue en ejecución tras taskkill; se mantiene como gestionado\.$/, m => `accServer (PID ${m[1]}) is still running after taskkill; it remains managed.`],
    [/^accServer ya se encuentra en ejecución\.$/, () => "accServer is already running."],
    [/^accServer iniciado correctamente\.$/, () => "accServer started successfully."],
    [/^accServer detenido y puertos liberados\.$/, () => "accServer stopped and ports released."],
    [/^accServer reiniciado correctamente\.$/, () => "accServer restarted successfully."],
    [/^El accServer gestionado ya está en ejecución\.$/, () => "The managed accServer is already running."],
    [/^Hay otro accServer\.exe en ejecución\. Deténlo manualmente antes de iniciar este panel\.$/, () => "Another accServer.exe is running. Stop it manually before starting from this panel."],
    [/^No fue posible detener el accServer gestionado\.$/, () => "Could not stop the managed accServer."],
    [/^La plantilla de pista seleccionada no existe o no está permitida\.$/, () => "The selected track template does not exist or is not allowed."],
    [/^La plantilla de pista no contiene un evento ACC válido\.$/, () => "The track template does not contain a valid ACC event."],
    [/^La rotación no contiene pistas\.$/, () => "The rotation contains no tracks."],
    [/^La rotación debe conservar al menos una pista\.$/, () => "The rotation must keep at least one track."],
    [/^Auto-rotación: (Habilitada|Pausada)$/, m => `Auto-rotation: ${m[1] === "Habilitada" ? "Enabled" : "Paused"}`],
    [/^Saltado a (.+)$/, m => `Skipped to ${m[1]}`],
    [/^Pista cambiada a (.+)$/, m => `Track changed to ${m[1]}`],
    [/^DLC no válido$/, () => "Invalid DLC"],
    [/^DLC (.+) (activado|desactivado)$/, m => `DLC ${DLC_NAME_EN_BY_ES[m[1]] || m[1]} ${m[2] === "activado" ? "enabled" : "disabled"}`],
    [/^Pista (.+) (activada|desactivada) en rotación$/, m => `Track ${m[1]} ${m[2] === "activada" ? "enabled" : "disabled"} in rotation`],
    [/^Preset no válido\.$/, () => "Invalid preset."],
    [/^Preset '(.+)' aplicado exitosamente$/, m => `Preset '${m[1]}' applied successfully`],
    [/^track_file no es una plantilla permitida\.$/, () => "track_file is not an allowed template."],
    [/^Piloto (.+) añadido a la lista negra\.$/, m => `Driver ${m[1]} added to the blacklist.`],
    [/^Piloto removido de la lista negra\.$/, () => "Driver removed from the blacklist."],
    [/^(.+) ahora tiene rol de (Administrador Permanente|Piloto Estándar)\.$/, m => `${m[1]} now has the ${m[2] === "Administrador Permanente" ? "Permanent Administrator" : "Standard Driver"} role.`],
    [/^Ese Steam ID no está en la entry list\.$/, () => "That Steam ID is not in the entry list."],
    [/^Entrada removida de entrylist\.$/, () => "Entry removed from the entry list."],
    [/^Whitelist estricta \(forceEntryList\): (ACTIVADA|DESACTIVADA)$/, m => `Strict whitelist (forceEntryList): ${m[1] === "ACTIVADA" ? "ENABLED" : "DISABLED"}`],
    [/^Entry list actualizada en cfg\/entrylist\.json\.$/, () => "Entry list updated in cfg/entrylist.json."],
    [/^No se pudo guardar entrylist\.$/, () => "Could not save the entry list."],
    [/^Configuración validada y guardada\. Los cambios de evento se aplican en el próximo reinicio\.$/, () => "Settings validated and saved. Event changes apply on the next restart."],
    [/^No se pudo guardar la configuración\.$/, () => "Could not save the settings."],
    [/^Error interno del panel\. Revisa la consola\.$/, () => "Internal panel error. Check the console."],
    [/^No autorizado$/, () => "Unauthorized"],
    [/^Endpoint no encontrado$/, () => "Endpoint not found"],
    [/^Content-Length inválido\.$/, () => "Invalid Content-Length."],
    [/^Solicitud demasiado grande\.$/, () => "Request too large."],
    [/^JSON inválido\.$/, () => "Invalid JSON."],
    [/^JSON con codificación o formato no reconocido$/, () => "JSON with unrecognized encoding or format"],
    [/^El cuerpo debe ser un objeto JSON\.$/, () => "The body must be a JSON object."],
    [/^playerId debe ser un Steam ID de ACC válido\.$/, () => "playerId must be a valid ACC Steam ID."],
    [/^La pista del evento no es válida\.$/, () => "The event track is not valid."],
    [/^Selecciona una pista desde el catálogo antes de editar su evento\.$/, () => "Select a track from the catalog before editing its event."],
    [/^sessions debe contener entre (\d+) y (\d+) sesiones\.$/, m => `sessions must contain between ${m[1]} and ${m[2]} sessions.`],
    [/^Hay una sesión con tipo inválido\.$/, () => "There is a session with an invalid type."],
    [/^No se recibió ninguna sección de configuración\.$/, () => "No settings section was received."],
    [/^entrylist supera el máximo de (\d+) entradas\.$/, m => `entrylist exceeds the maximum of ${m[1]} entries.`],
    [/^Cada entrada debe tener al menos un piloto\.$/, () => "Each entry must have at least one driver."],
    [/^Piloto inválido en entrylist\.$/, () => "Invalid driver in entrylist."],
    [/^No fue posible leer server\.log: ([\s\S]*)$/, m => `Could not read server.log: ${m[1]}`],
    [/^No fue posible leer server\.log\.$/, () => "Could not read server.log."],
    [/^El archivo server\.log aún no se ha generado\.$/, () => "The server.log file has not been created yet."],
    [/^Desconocido$/, () => "Unknown"],
    // Validaciones genéricas con nombre de campo
    [/^(\S+) debe ser texto\.$/, m => `${m[1]} must be text.`],
    [/^(\S+) no tiene un formato válido\.$/, m => `${m[1]} does not have a valid format.`],
    [/^(\S+) debe estar entre (\S+) y (\S+)\.$/, m => `${m[1]} must be between ${m[2]} and ${m[3]}.`],
    [/^(\S+) debe ser booleano\.$/, m => `${m[1]} must be a boolean.`],
    [/^(\S+) debe ser un objeto\.$/, m => `${m[1]} must be an object.`],
    [/^(\S+) no es válido\.$/, m => `${m[1]} is not valid.`]
  ];

  function translateServerEn(message) {
    const text = String(message);
    for (const [pattern, build] of SERVER_MESSAGES_EN) {
      const match = pattern.exec(text);
      if (match) return build(match);
    }
    return text;
  }

  function readStoredLang() {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return STRINGS[stored] ? stored : DEFAULT_LANG;
    } catch {
      return DEFAULT_LANG;
    }
  }

  let currentLang = readStoredLang();

  function t(key, params = {}) {
    const template = STRINGS[currentLang][key] ?? STRINGS[DEFAULT_LANG][key] ?? key;
    return template.replace(/\{(\w+)\}/g, (whole, name) => (name in params ? String(params[name]) : whole));
  }

  function translateServer(message) {
    if (message === null || message === undefined || message === "") return message;
    return currentLang === "en" ? translateServerEn(message) : String(message);
  }

  function dlcName(category) {
    if (currentLang !== "en") return category.name;
    return (DLC_EN[category.id] && DLC_EN[category.id].name) || category.name;
  }

  function dlcDescription(category) {
    if (currentLang !== "en") return category.description;
    return (DLC_EN[category.id] && DLC_EN[category.id].description) || category.description;
  }

  function applyStatic(root = document) {
    const fresh = el => el.dataset.loaded !== "1";
    root.querySelectorAll("[data-i18n]").forEach(el => {
      if (fresh(el)) el.textContent = t(el.dataset.i18n);
    });
    root.querySelectorAll("[data-i18n-html]").forEach(el => {
      if (fresh(el)) el.innerHTML = t(el.dataset.i18nHtml);
    });
    root.querySelectorAll("[data-i18n-attr]").forEach(el => {
      el.dataset.i18nAttr.split(";").forEach(pair => {
        const [attr, key] = pair.split(":").map(part => part.trim());
        if (attr && key) el.setAttribute(attr, t(key));
      });
    });
    document.documentElement.lang = currentLang;
    document.querySelectorAll(".lang-btn").forEach(button => {
      const active = button.dataset.lang === currentLang;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
  }

  function setLang(lang) {
    if (!STRINGS[lang] || lang === currentLang) return;
    currentLang = lang;
    try {
      localStorage.setItem(STORAGE_KEY, lang);
    } catch {
      // Sin almacenamiento disponible: el idioma dura hasta recargar.
    }
    applyStatic();
    document.dispatchEvent(new CustomEvent("panel:languagechange", { detail: { lang } }));
  }

  document.addEventListener("click", event => {
    const button = event.target.closest(".lang-btn[data-lang]");
    if (button) setLang(button.dataset.lang);
  });

  window.i18n = {
    t,
    translateServer,
    dlcName,
    dlcDescription,
    setLang,
    applyStatic,
    get lang() { return currentLang; }
  };

  // El script se carga al final del <body>: el DOM ya existe y se traduce antes del primer pintado.
  applyStatic();
})();
