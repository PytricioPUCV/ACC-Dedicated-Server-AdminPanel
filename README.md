# 🏎️ Assetto Corsa Competizione — Dedicated Server Admin Control Panel & Hot Track Rotator

[![Python Version](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011%20%7C%20Server-0078D6.svg)](https://www.microsoft.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![ACC Compatible](https://img.shields.io/badge/ACC%20Dedicated%20Server-Steam-red.svg)](https://store.steampowered.com/app/805550/Assetto_Corsa_Competizione/)
[![Release](https://img.shields.io/badge/Release-v1.0-brightgreen.svg)](https://github.com/)

Suite integral de administración web, telemetría en tiempo real y **orquestador inteligente de rotación automática de circuitos** para el servidor dedicado oficial (`accServer.exe`) de **Assetto Corsa Competizione**.

Disponible tanto como **código fuente** en Python como en un **ejecutable standalone `.exe` (Release 1.0)** listo para usar con doble clic, sin necesidad de instalar Python ni librerías externas.

---

## ⚡ Planteamiento del Problema y Solución

El binario oficial de Kunos Simulazioni (`accServer.exe`) posee una limitación estructural: **carece de rotación dinámica de pistas en caliente**. Al concluir una carrera, el servidor reinicia indefinidamente el mismo circuito fijado en `cfg/event.json`.

Este orquestador actúa como un **wrapper desacoplado e inteligente** que:
1. Intercepta asíncronamente el término de carrera en tiempo real mediante la detección de volcados de resultados (`dumpLeaderboards` con sufijo `_R.json`).
2. Concede una pausa calibrada de **12 segundos** para visualización de podios a los pilotos.
3. Termina de forma limpia y forzada el proceso con liberación garantizada de sockets y puertos de red (UDP 9231 / TCP 9232).
4. Aplica la siguiente plantilla del repositorio de circuitos (`tracks_pool/`) en `cfg/event.json`.
5. Relanza el servidor automáticamente, logrando una rotación continua sin intervención humana.

---

## ✨ Características Principales

* 🔄 **Rotación Dinámica de Circuitos:** Catálogo calibrado con los **25 circuitos oficiales** de ACC agrupados en sus DLCs.
* 🌐 **Panel de Control Web Moderno:** Interfaz responsiva con estética *Motorsport Dark Glassmorphism* accesible localmente o en LAN (`http://127.0.0.1:8080`).
* 📦 **Ejecutable Standalone (.exe):** Cero dependencias externas. El `.exe` incluye internamente la interfaz web y auto-inicializa las 25 pistas en servidores limpios.
* ⏱️ **Telemetría e Historial de Carreras:** Cálculo de récords de vuelta por circuito, estadísticas de victorias y podios históricos calculados desde los volcados de carrera.
* 📜 **Visor de Consola en Tiempo Real:** Monitor de conexiones, pings de pilotos y eventos de sala directo en la interfaz web.
* 🛡️ **Moderación y Lista de Pilotos:** Lista en vivo de pilotos conectados, asignación de administradores permanentes (`cfg/entrylist.json`) y sistema de baneo (`cfg/banlist.json`).
* ⚙️ **Editor de Configuración Seguro:** Permite editar parámetros de sala, contraseñas y asistencias garantizando la codificación estricta **UTF-16 LE con BOM** requerida por el motor de ACC.
* 🔐 **Seguridad Integrada:** Generación automática de tokens criptográficos de sesión en `panel_auth.json` y prevención contra vulnerabilidades de path traversal.

---

## 🚀 Guía de Uso Rápido (Para Administradores / Usuarios Finales)

No necesitas instalar Python ni compilar nada.

1. Ve a la sección **[Releases](https://github.com/)** y descarga `ACC_Server_AdminPanel_v1.0.zip` (o directamente `ACC_AdminPanel.exe`).
2. Coloca `ACC_AdminPanel.exe` dentro de la carpeta `server` de tu servidor dedicado de Steam:
   ```text
   C:\Program Files (x86)\Steam\steamapps\common\Assetto Corsa Competizione Dedicated Server\server
   ```
3. Haz doble clic en `ACC_AdminPanel.exe`:
   * Windows solicitará permisos de Administrador (UAC) para gestionar `accServer.exe` en `Program Files`.
   * Tu navegador web se abrirá automáticamente con el panel autenticado: `http://127.0.0.1:8080/?token=...`
4. ¡Listo! Puedes encender el servidor, activar la rotación automática o saltar a cualquier pista con un clic.

---

## 🛠️ Guía para Desarrolladores (Código Fuente)

### Requisitos Previos
* Windows 10 / 11 / Windows Server
* Python 3.10 o superior (solo estándar de Python, sin dependencias obligatorias de terceros para ejecutar el servidor)
* Assetto Corsa Competizione Dedicated Server (instalado via Steam)

### Ejecutar desde Código Fuente
1. Clona este repositorio dentro de tu carpeta `server` de ACC:
   ```bash
   git clone https://github.com/TU_USUARIO/ACC-Dedicated-Server-AdminPanel.git .
   ```
2. Ejecuta el lanzador por lotes:
   ```cmd
   Iniciar_Admin_Panel.bat
   ```
   o directamente con Python:
   ```bash
   python AdminPanel/panel_server.py
   ```

### Opciones de Línea de Comandos
```text
python AdminPanel/panel_server.py [PUERTO] [OPCIONES]

Opciones:
  --lan                Permitir conexiones desde cualquier IP local en la red (0.0.0.0)
  --no-open            No abrir el navegador automáticamente al iniciar
  --no-uac             Omitir la comprobación/solicitud de elevación UAC
  --server-dir <ruta>  Especificar manualmente la ruta a la carpeta 'server'
  --help, -h           Mostrar ayuda
```

---

## 🔨 Cómo Compilar el Ejecutable (.exe) Release

Para generar el archivo ejecutable `.exe` standalone con PyInstaller:

1. Asegúrate de tener Python 3.10+ en tu PATH.
2. Haz doble clic en `AdminPanel/build_release.bat` o ejecuta:
   ```bash
   python AdminPanel/build_exe.py
   ```
3. El script automáticamente:
   * Instala PyInstaller si no está presente.
   * Empaqueta el frontend web (`web/`) y las plantillas de circuitos (`tracks_pool/`) dentro del binario.
   * Inserta el manifiesto UAC (`--uac-admin`).
   * Genera el ejecutable listo en `ACC_AdminPanel.exe` y el paquete `release/ACC_Server_AdminPanel_v1.0.zip`.

---

## 🗺️ Catálogo de los 25 Circuitos Incluidos

El repositorio incluye plantillas calibradas en `tracks_pool/` para la totalidad de circuitos existentes en Assetto Corsa Competizione:

| DLC / Categoría | Circuitos Incluidos | Archivos de Plantilla |
| :--- | :--- | :--- |
| **Juego Base** (11) | Monza, Spa-Francorchamps, Silverstone, Nürburgring GP, Barcelona, Brands Hatch, Misano, Paul Ricard, Zolder, Hungaroring, Zandvoort | `monza.json`, `spa.json`, `silverstone.json`, `nurburgring.json`, `barcelona.json`, `brands_hatch.json`, `misano.json`, `paul_ricard.json`, `zolder.json`, `hungaroring.json`, `zandvoort.json` |
| **Intercontinental GT Pack** (4) | Kyalami, Mount Panorama (Bathurst), Suzuka, Laguna Seca | `kyalami.json`, `mount_panorama.json`, `suzuka.json`, `laguna_seca.json` |
| **British GT Pack** (3) | Donington Park, Oulton Park, Snetterton 300 | `donington.json`, `oulton_park.json`, `snetterton.json` |
| **American Track Pack (USA)** (3) | Circuit of the Americas (COTA), Indianapolis, Watkins Glen | `cota.json`, `indianapolis.json`, `watkins_glen.json` |
| **2020 GT World Challenge** (1) | Autodromo Enzo e Dino Ferrari (Imola) | `imola.json` |
| **2023 GT World Challenge** (1) | Circuit Ricardo Tormo (Valencia) | `valencia.json` |
| **GT2 Pack (2024)** (1) | Red Bull Ring (Spielberg) | `red_bull_ring.json` |
| **24h Nürburgring Pack (2024)** (1) | Nürburgring Nordschleife 24h | `nurburgring_24h.json` |

---

## 📁 Arquitectura del Repositorio

```text
server/
│
├── Iniciar_Admin_Panel.bat            # Lanzador inteligente (prioriza .exe sobre python)
├── README.md                          # Documentación del proyecto
├── LICENSE                            # Licencia MIT
├── .gitignore                         # Exclusiones de seguridad y binarios de Steam
│
├── AdminPanel/                        # Módulo del panel de control
│   ├── panel_server.py                # Backend HTTP, REST API y Orquestador en segundo plano
│   ├── build_exe.py                   # Script de compilación y empaquetado de Release 1.0
│   ├── build_release.bat              # Compilador en un solo clic
│   ├── Iniciar_Admin_Panel.bat        # Lanzador local
│   └── web/                           # Frontend web (HTML5 / Vanilla CSS / Vanilla JS)
│       ├── index.html                 # Tableros KPI, centro de mandos, telemetría y consola
│       ├── css/style.css              # Sistema de diseño GT3 Motorsport Glassmorphism
│       └── js/app.js                  # Lógica reactiva y llamadas a la REST API
│
├── tracks_pool/                       # Depósito con las 25 plantillas oficiales de circuitos
│   └── *.json
│
└── cfg/                               # Plantillas de configuración
    ├── rotation_config.json           # Estado de rotación y DLCs activos
    ├── settings.json.example          # Plantilla sanitizada de settings
    ├── configuration.json.example     # Plantilla de puertos de red
    └── assistRules.json.example       # Plantilla de ayudas de conducción
```

---

## 📄 Licencia

Este proyecto está bajo la Licencia **MIT**. Consulta el archivo [LICENSE](LICENSE) para más detalles.

*Assetto Corsa Competizione es una marca registrada de Kunos Simulazioni Srl y Digital Bros Group. Este proyecto es una herramienta independiente desarrollada por la comunidad y no está afiliada oficialmente con Kunos Simulazioni.*
