# Arquitectura e Ingeniería del Sistema: Servidor Dedicado ACC con Rotación Automática

## 1. Planteamiento del Problema
**Assetto Corsa Competizione (ACC)** es un simulador de carreras de alto rendimiento enfocado en la categoría GT World Challenge. Aunque Kunos Simulazioni provee una herramienta de servidor dedicado oficial (`accServer.exe`), esta cuenta con una limitación estructural crítica: **carece de un sistema de rotación de circuitos dinámica o en caliente**.

Al concluir una sesión de Carrera (`sessionType: "R"`), el servidor no avanza hacia un trazado nuevo. En su lugar, ejecuta una rutina de reinicio del fin de semana volviendo a cargar de manera indefinida la configuración estática fijada en `cfg/event.json`. Para alternar circuitos en una liga o servidor comunitario, un administrador humano se veía forzado a detener manualmente el proceso, editar a mano los archivos de configuración JSON y reiniciar el servidor.

---

## 2. Visión y Objetivo de la Solución Diseñada
El objetivo fue diseñar e implementar una arquitectura de automatización desacoplada alrededor del binario oficial de ACC. Esta solución actúa como un **orquestador inteligente (wrapper)** capaz de:
1. Administrar el ciclo de vida del proceso `accServer.exe`.
2. Interceptar el evento de término de carrera en tiempo real sin requerir APIs propietarias de terceros.
3. Rotar ordenadamente la pista activa leyendo desde un repositorio local de plantillas (`tracks_pool`).
4. Reconstruir `cfg/event.json` y relanzar el servidor con tiempos de inactividad (*downtime*) mínimos para los pilotos.

---

## 3. Retos Técnicos y Diagnóstico Forense

Durante el desarrollo e integración en el entorno de Windows, se identificaron y resolvieron 4 obstáculos técnicos mayores:

### A. Restricciones de Permisos (UAC en `Program Files (x86)`)
* **Reto:** El servidor de ACC por defecto se aloja en la ruta protegida de Steam:
  `C:\Program Files (x86)\Steam\steamapps\common\Assetto Corsa Competizione Dedicated Server\server`
* **Impacto:** Cualquier script o proceso estándar que intentara sobrescribir `event.json` o crear directorios generaba excepciones de denegación de acceso (`PermissionError: [Errno 13]`).
* **Solución:** Se implementó una rutina de auto-elevación UAC nativa mediante `ctypes.windll.shell32.IsUserAnAdmin()` y `ShellExecuteW(..., "runas", ...)`. Si el script no corre con permisos elevados, solicita confirmación administrativa de Windows y se relanza a sí mismo automáticamente.

### B. Detección Asíncrona del Fin de Carrera
* **Reto:** Se necesitaba una señal confiable emitida por el simulador para determinar con precisión de segundos cuándo terminó la carrera.
* **Solución:** Se habilitó el parámetro `"dumpLeaderboards": 1` en `cfg/settings.json`. Esto instruye al motor a exportar la telemetría y tabla de tiempos final hacia la carpeta `server/results/`.
* **Hallazgo Forense:** El motor de ACC nombra estos archivos con la estructura temporal `AAMMDD_HHMMSS_R` o `AAMMDD_HHMMSS_R.json` (ejemplo real capturado durante las pruebas: `260911_002200_R.json`). El sufijo `_R` discrimina inequívocamente las sesiones de Carrera frente a Prácticas (`_P`) o Clasificaciones (`_Q`).

### C. La Carrera contra el Bucle Interno de ACC
* **Reto:** El servidor dedicado espera aproximadamente 15 a 20 segundos tras la bandera a cuadros antes de emitir:
  `Session aftercare over, advancing to next session` -> `Session changed: Race -> Practice 0`.
* **Impacto:** Si la ventana de espera del monitor era muy larga (por ejemplo, 35 segundos), el servidor ya había entrado a la sesión de práctica del mapa viejo antes del reinicio.
* **Solución:** Se ajustó la ventana de tolerancia a **12 segundos exactos**. Este lapso permite que el cliente del juego despliegue el podio y los resultados en pantalla a los pilotos, e interrumpe el ciclo del servidor antes de que salte a la siguiente práctica.

### D. Bloqueo de Sockets y Procesos Zombies en C++
* **Reto:** El método nativo de Python `process.terminate()` (equivalente a SIGTERM) resultaba ineficaz. El binario `accServer.exe` ignoraba la señal de apagado debido a conexiones de red e hilos de simulación en curso, manteniendo ocupados los puertos de comunicación (UDP 9231 / TCP 9232).
* **Solución:** Se diseñó una rutina forzada de terminación a nivel de sistema operativo invocando `taskkill /F /IM accServer.exe /T`. Esto destruye el árbol de subprocesos y garantiza la liberación inmediata de los sockets de red.

---

## 4. Arquitectura de Componentes

El ecosistema final quedó estructurado modularmente en el directorio del servidor:

```text
server/
│
├── accServer.exe                      # Binario nativo del servidor dedicado de ACC
├── rotator.py                         # Orquestador y monitor en tiempo real (Python)
│
├── cfg/                               # Archivos de configuración activos
│   ├── configuration.json             # Enrutamiento de red (UDP 9231 / TCP 9232)
│   ├── settings.json                  # Nombre del server, flags de auditoría y admin
│   └── event.json                     # Configuración del circuito actualmente en juego
│
├── results/                           # Salida del motor (dumpLeaderboards)
│   ├── 260911_001337_R.json           # Telemetría de carrera en Valencia (Histórico)
│   └── 260911_002200_R.json           # Telemetría de carrera que detonó la rotación
│
└── tracks_pool/                       # Depósito de plantillas de circuitos
    ├── valencia.json                  # Circuito Ricardo Tormo
    ├── spa.json                       # Circuit de Spa-Francorchamps
    ├── monza.json                     # Autodromo Nazionale Monza
    ├── nurburgring.json               # Nürburgring Grand Prix
    └── silverstone.json               # Silverstone Circuit
```

---

## 5. Ciclo de Ejecución (Flujo Lógico del Orquestador)

```text
[Inicio: rotator.py (UAC Admin)]
       │
       ▼
[Limpieza preventiva: taskkill accServer.exe]
       │
       ▼
[Lectura de tracks_pool[idx] -> Sobrescritura en cfg/event.json]
       │
       ▼
[Lanzamiento de subproceso accServer.exe]
       │
       ▼
[Bucle de monitoreo continuo en server/results/]
       │
       ├─► ¿Aparece archivo nuevo terminado en _R / _R.json?
       │        │
       │        ├─► NO  ──► Pausa 3s y reintentar.
       │        │
       │        └─► SÍ  ──► [1] Pausa de 12s (visibilidad de podio).
       │                    [2] Ejecución de taskkill /F /IM accServer.exe /T.
       │                    [3] Liberación de puertos y memoria (3s).
       │                    [4] idx = (idx + 1) % Total_Tracks.
       │                    [5] Reiniciar ciclo con la siguiente pista.
```

---

## 6. Resultados y Validación en Pruebas
Durante la sesión de pruebas en vivo, se validó la efectividad de la arquitectura:
1. Se corrió la primera carrera oficial en **Valencia** (ganada por Patricio Schumacher, coche #97 con 13 vueltas).
2. Se capturó y parseó la generación del volcado `260911_002200_R.json`.
3. El orquestador intervino a los 12 segundos, terminó el servidor de Valencia y sobrescribió `event.json` con la plantilla de `spa.json`.
4. El servidor levantó exitosamente la sesión en **Spa-Francorchamps**, confirmando el registro en el lobby oficial de Kunos:
   ```text
   Track spa was set and updated
   RegisterToLobby succeeded
   Sent lobby registration request for spa
   Lobby accepted connection
   ```

Este diseño entrega una infraestructura 100% autónoma y escalable para albergar campeonatos y servidores comunitarios de ACC sin intervención manual.

---

## 7. Panel de Control Visual (Frontend Web & REST API)

Para facilitar la supervisión en vivo, ejecución de comandos y edición de parámetros sin tocar archivos JSON manualmente, se integró una suite visual desacoplada:

```text
server/
│
├── accServer.exe                      # Binario nativo del servidor dedicado de ACC
├── Iniciar_Admin_Panel.bat            # Lanzador raíz directo (apunta a AdminPanel/)
├── ServerAdminHandbook.pdf            # Manual oficial de administración
│
├── AdminPanel/                        # SUITE MODULAR DEL PANEL DE CONTROL
│   ├── panel_server.py                # Backend HTTP + Orquestador de rotación unificado
│   ├── Iniciar_Admin_Panel.bat        # Lanzador local con auto-elevación UAC
│   ├── AdminPanel.md                  # Especificación técnica y manual
│   └── web/                           # Frontend Web (Motorsport Dark Glassmorphism)
│       ├── index.html                 # Tableros KPI, centro de mandos, telemetría y consola
│       ├── css/style.css              # Sistema de diseño con estética GT3 Motorsport
│       └── js/app.js                  # Sincronización reactiva mediante sondeo a la API REST
│
├── cfg/                               # Archivos de configuración de ACC
│   ├── configuration.json             # Red (UTF-16 LE con BOM)
│   ├── settings.json                  # Datos de sala, slots y contraseñas (UTF-16 LE con BOM)
│   ├── assistRules.json               # Ayudas y asistencias (UTF-16 LE con BOM)
│   ├── event.json                     # Circuito en juego y sesiones (UTF-8)
│   └── rotacion.py                    # Script de rotación original
│
├── results/                           # Salida del motor (dumpLeaderboards, UTF-16 LE sin BOM)
│   └── *.json                         # Historial de telemetría, tiempos por vuelta y podios
│
├── log/
│   └── server.log                     # Registro de ejecución y conexiones
│
└── tracks_pool/                       # Depósito de plantillas de circuitos (UTF-8)
```

### Endpoints de la REST API Local (`http://localhost:8080`)

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/api/status` | Devuelve estado del proceso (`accServer.exe`), PID, Uptime, pista actual, rotación y slots. |
| `POST` | `/api/server/start` | Inicia el subproceso `accServer.exe`. |
| `POST` | `/api/server/restart`| Mata procesos huérfanos con `taskkill`, libera sockets (3s) y relanza el servidor. |
| `POST` | `/api/server/stop` | Detiene forzosamente el servidor y libera los puertos UDP 9231 / TCP 9232. |
| `POST` | `/api/rotation/toggle` | Activa o pausa la auto-rotación de pistas tras el final de carrera. |
| `POST` | `/api/rotation/skip` | Salta inmediatamente al siguiente circuito del pool. |
| `POST` | `/api/rotation/select` | Carga y aplica inmediatamente una pista seleccionada (`{"track_file": "spa.json"}`). |
| `GET` | `/api/tracks` | Lista el catálogo de 25 circuitos clasificados por categorías DLC y estado de rotación. |
| `POST` | `/api/rotation/dlc-toggle` | Activa o desactiva en bloque todos los mapas de un DLC (`{"dlc_id": "british_gt", "enabled": true}`). |
| `POST` | `/api/rotation/track-toggle` | Activa o desactiva un circuito individual (`{"track_file": "cota.json", "enabled": false}`). |
| `POST` | `/api/rotation/preset` | Aplica un preset de rotación rápida (`"all"`, `"base_only"`, `"dlc_only"`). |
| `GET` | `/api/config` | Obtiene los archivos de configuración decodificados adecuadamente. |
| `POST` | `/api/config` | Guarda modificaciones asegurando la escritura con **UTF-16 LE con BOM** en `settings.json`, `configuration.json` y `assistRules.json`. |
| `GET` | `/api/players` | Lista de pilotos activos y recientes, con detección de admin y bans. |
| `POST` | `/api/moderation/ban` | Añade un piloto a la lista de baneados persistente en `cfg/banlist.json`. |
| `POST` | `/api/moderation/unban` | Remueve a un piloto de la lista de baneados. |
| `POST` | `/api/moderation/admin` | Asigna o remueve permisos de administrador permanente en `cfg/entrylist.json`. |
| `GET` | `/api/telemetry` | Parsea `results/*.json` generando récords de vuelta, podios y ranking de pilotos. |
| `GET` | `/api/logs?lines=N` | Stream de las últimas `N` líneas de `log/server.log`. |

---

## 9. Catálogo Oficial de los 25 Circuitos y Expansiones DLC

El servidor dispone de plantillas completas y calibradas en `server/tracks_pool/` para todos los 25 circuitos existentes en Assetto Corsa Competizione:

### 1. Juego Base (11 Circuitos)
* **Autodromo Nazionale Monza** (`monza.json`)
* **Circuit de Spa-Francorchamps** (`spa.json`)
* **Silverstone Circuit** (`silverstone.json`)
* **Nürburgring GP** (`nurburgring.json`)
* **Circuit de Barcelona-Catalunya** (`barcelona.json`)
* **Brands Hatch** (`brands_hatch.json`)
* **Misano World Circuit** (`misano.json`)
* **Circuit Paul Ricard** (`paul_ricard.json`)
* **Circuit Zolder** (`zolder.json`)
* **Hungaroring** (`hungaroring.json`)
* **Circuit Zandvoort** (`zandvoort.json`)

### 2. Intercontinental GT Pack (4 Circuitos)
* **Kyalami Grand Prix Circuit** (`kyalami.json`)
* **Mount Panorama Circuit (Bathurst)** (`mount_panorama.json`)
* **Suzuka Circuit** (`suzuka.json`)
* **WeatherTech Raceway Laguna Seca** (`laguna_seca.json`)

### 3. British GT Pack (3 Circuitos)
* **Donington Park** (`donington.json`)
* **Oulton Park** (`oulton_park.json`)
* **Snetterton 300** (`snetterton.json`)

### 4. American Track Pack (USA) (3 Circuitos)
* **Circuit of the Americas (COTA)** (`cota.json`)
* **Indianapolis Motor Speedway** (`indianapolis.json`)
* **Watkins Glen International** (`watkins_glen.json`)

### 5. 2020 GT World Challenge Pack (1 Circuito)
* **Autodromo Enzo e Dino Ferrari (Imola)** (`imola.json`)

### 6. 2023 GT World Challenge Pack (1 Circuito)
* **Circuit Ricardo Tormo (Valencia)** (`valencia.json`)

### 7. GT2 Pack (2024) (1 Circuito)
* **Red Bull Ring (Spielberg)** (`red_bull_ring.json`)

### 8. 24h Nürburgring Pack (2024) (1 Circuito)
* **Nürburgring Nordschleife 24h** (`nurburgring_24h.json`, con `sessionOverTimeSeconds: 600` para vueltas de 8+ minutos).

---

## 10. Gestor de Rotación y Configuración Persistente

La selección de DLCs y circuitos activos se almacena en `cfg/rotation_config.json`:
```json
{
  "active_dlcs": ["base", "igtc", "british_gt", "usa", "gtw_2020", "gtw_2023", "gt2", "nurburgring_24h"],
  "disabled_tracks": []
}
```

* **Presets de Rotación Rápida:**
  * **Todos (Base + DLCs):** Los 25 circuitos activos en rotación cíclica.
  * **Solo Juego Base:** 11 circuitos tradicionales incluidos de serie.
  * **Solo Expansiones DLC:** 14 circuitos de paquetes adicionales.
* **Interruptores por DLC:** Permite encender o apagar cualquier paquete con 1 clic en la interfaz web o mediante la API REST.
* **Exclusiones Quirúrgicas:** Posibilidad de desactivar circuitos individuales dentro de un DLC activo.

---

## 11. Guía Rápida de Operación

1. **Lanzamiento:**
   Hacer doble clic en `Iniciar_Admin_Panel.bat` (o ejecutar `python panel_server.py`).
2. **Acceso:**
   Abrir en cualquier navegador: `http://localhost:8080` (también accesible desde dispositivos en la misma red LAN).
3. **Control Total:**
   * **KPIs en Vivo:** Visualización en tiempo real del estado (ONLINE/OFFLINE), PID y Uptime.
   * **Gestión de DLCs:** Activar/desactivar paquetes enteros con un solo toggle.
   * **Mandos:** Iniciar, reiniciar o detener el servidor a un clic.
   * **Edición en Caliente:** Modificar nombres, slots, contraseñas o duraciones sin riesgo de corrupción binaria.
   * **Moderación:** Lista de pilotos en vivo, comandos oficiales (`/kick`, `/ban`, `/dq`, `/dt`) y gestión de administradores.
   * **Telemetría:** Consultar victorias, vueltas completadas y podios históricos calculados desde los volcados de carrera.