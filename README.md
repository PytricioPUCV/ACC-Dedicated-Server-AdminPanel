# 🏎️ Assetto Corsa Competizione — Dedicated Server Admin Control Panel & Hot Track Rotator

[![Python Version](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011%20%7C%20Server-0078D6.svg)](https://www.microsoft.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![ACC Compatible](https://img.shields.io/badge/ACC%20Dedicated%20Server-Steam-red.svg)](https://store.steampowered.com/app/805550/Assetto_Corsa_Competizione/)
[![Release](https://img.shields.io/badge/Release-v1.0-brightgreen.svg)](https://github.com/)

Comprehensive web administration suite, real-time telemetry, and **smart automatic track rotation orchestrator** for the official **Assetto Corsa Competizione** dedicated server (`accServer.exe`).

Available both as Python **source code** and as a ready-to-use **standalone `.exe` executable (Release 1.0)** that requires just a double-click, with no need to install Python or external libraries.

---

## ⚡ Problem Statement and Solution

The official Kunos Simulazioni binary (`accServer.exe`) has a structural limitation: **it lacks dynamic hot track rotation**. When a race concludes, the server indefinitely restarts the same circuit set in `cfg/event.json`.

This orchestrator acts as a **decoupled and smart wrapper** that:
1. Asynchronously intercepts the end of the race in real-time by detecting result dumps (`dumpLeaderboards` with the `_R.json` suffix).
2. Grants a calibrated **12-second** pause for drivers to view the podium.
3. Cleanly and forcefully terminates the process, guaranteeing the release of network sockets and ports (UDP 9231 / TCP 9232).
4. Applies the next template from the track repository (`tracks_pool/`) to `cfg/event.json`.
5. Automatically relaunches the server, achieving continuous rotation without human intervention.

---

## ✨ Main Features

* 🔄 **Dynamic Track Rotation:** Calibrated catalog featuring all **25 official ACC circuits** grouped by their DLCs.
* 🌐 **Modern Web Control Panel:** Responsive interface with a *Motorsport Dark Glassmorphism* aesthetic, accessible locally or over LAN (`http://127.0.0.1:8080`).
* 📦 **Standalone Executable (.exe):** Zero external dependencies. The `.exe` internally bundles the web interface and auto-initializes the 25 tracks on clean servers.
* ⏱️ **Telemetry and Race History:** Calculation of lap records per circuit, win statistics, and historical podiums computed from race dumps.
* 📜 **Real-Time Console Viewer:** Monitor connections, driver pings, and lobby events directly in the web interface.
* 🛡️ **Moderation and Driver List:** Live list of connected drivers, permanent administrator assignment (`cfg/entrylist.json`), and ban system (`cfg/banlist.json`).
* ⚙️ **Secure Configuration Editor:** Allows editing lobby parameters, passwords, and assists, ensuring the strict **UTF-16 LE with BOM** encoding required by the ACC engine.
* 🔐 **Integrated Security:** Automatic generation of cryptographic session tokens in `panel_auth.json` and prevention against path traversal vulnerabilities.

---

## 🚀 Quick Start Guide (For Admins / End Users)

You do not need to install Python or compile anything.

1. Go to the **[Releases](https://github.com/)** section and download `ACC_Server_AdminPanel_v1.0.zip` (or directly `ACC_AdminPanel.exe`).
2. Place `ACC_AdminPanel.exe` inside the `server` folder of your Steam dedicated server:
   ```text
   C:\Program Files (x86)\Steam\steamapps\common\Assetto Corsa Competizione Dedicated Server\server
   ```
3. Double-click `ACC_AdminPanel.exe`:
   * Windows will request Administrator (UAC) permissions to manage `accServer.exe` in `Program Files`.
   * Your web browser will open automatically with the authenticated panel: `http://127.0.0.1:8080/?token=...`
4. That's it! You can now start the server, enable automatic rotation, or jump to any track with a single click.

---

## 🛠️ Developer Guide (Source Code)

### Prerequisites
* Windows 10 / 11 / Windows Server
* Python 3.10 or higher (standard Python only, no mandatory third-party dependencies to run the server)
* Assetto Corsa Competizione Dedicated Server (installed via Steam)

### Run from Source Code
1. Clone this repository inside your ACC `server` folder:
   ```bash
   git clone https://github.com/YOUR_USERNAME/ACC-Dedicated-Server-AdminPanel.git .
   ```
2. Run the batch launcher:
   ```cmd
   Iniciar_Admin_Panel.bat
   ```
   or directly with Python:
   ```bash
   python AdminPanel/panel_server.py
   ```

### Command Line Options
```text
python AdminPanel/panel_server.py [PORT] [OPTIONS]

Options:
  --lan              Allow connections from any local IP on the network (0.0.0.0)
  --no-open          Do not open the browser automatically on startup
  --no-uac           Skip the UAC elevation check/prompt
  --server-dir <dir> Manually specify the path to the 'server' folder
  --help, -h         Show help
```

---

## 🔨 How to Build the Release Executable (.exe)

To generate the standalone `.exe` executable file with PyInstaller:

1. Ensure you have Python 3.10+ in your PATH.
2. Double-click `AdminPanel/build_release.bat` or run:
   ```bash
   python AdminPanel/build_exe.py
   ```
3. The script will automatically:
   * Install PyInstaller if it is not present.
   * Package the web frontend (`web/`) and track templates (`tracks_pool/`) into the binary.
   * Insert the UAC manifest (`--uac-admin`).
   * Generate the ready-to-use executable at `ACC_AdminPanel.exe` and the `release/ACC_Server_AdminPanel_v1.0.zip` package.

---

## 🗺️ Catalog of the 25 Included Circuits

The repository includes calibrated templates in `tracks_pool/` for all existing circuits in Assetto Corsa Competizione:

| DLC / Category | Included Circuits | Template Files |
| :--- | :--- | :--- |
| **Base Game** (11) | Monza, Spa-Francorchamps, Silverstone, Nürburgring GP, Barcelona, Brands Hatch, Misano, Paul Ricard, Zolder, Hungaroring, Zandvoort | `monza.json`, `spa.json`, `silverstone.json`, `nurburgring.json`, `barcelona.json`, `brands_hatch.json`, `misano.json`, `paul_ricard.json`, `zolder.json`, `hungaroring.json`, `zandvoort.json` |
| **Intercontinental GT Pack** (4) | Kyalami, Mount Panorama (Bathurst), Suzuka, Laguna Seca | `kyalami.json`, `mount_panorama.json`, `suzuka.json`, `laguna_seca.json` |
| **British GT Pack** (3) | Donington Park, Oulton Park, Snetterton 300 | `donington.json`, `oulton_park.json`, `snetterton.json` |
| **American Track Pack (USA)** (3) | Circuit of the Americas (COTA), Indianapolis, Watkins Glen | `cota.json`, `indianapolis.json`, `watkins_glen.json` |
| **2020 GT World Challenge** (1) | Autodromo Enzo e Dino Ferrari (Imola) | `imola.json` |
| **2023 GT World Challenge** (1) | Circuit Ricardo Tormo (Valencia) | `valencia.json` |
| **GT2 Pack (2024)** (1) | Red Bull Ring (Spielberg) | `red_bull_ring.json` |
| **24h Nürburgring Pack (2024)** (1) | Nürburgring Nordschleife 24h | `nurburgring_24h.json` |

---

## 📁 Repository Architecture

```text
server/
│
├── Iniciar_Admin_Panel.bat            # Smart launcher (prioritizes .exe over python)
├── README.md                          # Project documentation
├── LICENSE                            # MIT License
├── .gitignore                         # Security and Steam binaries exclusions
│
├── AdminPanel/                        # Control panel module
│   ├── panel_server.py                # HTTP Backend, REST API, and Background Orchestrator
│   ├── build_exe.py                   # Compilation and Release 1.0 packaging script
│   ├── build_release.bat              # One-click compiler
│   ├── Iniciar_Admin_Panel.bat        # Local launcher
│   └── web/                           # Web frontend (HTML5 / Vanilla CSS / Vanilla JS)
│       ├── index.html                 # KPI dashboards, command center, telemetry, and console
│       ├── css/style.css              # GT3 Motorsport Glassmorphism design system
│       └── js/app.js                  # Reactive logic and REST API calls
│
├── tracks_pool/                       # Repository with the 25 official circuit templates
│   └── *.json
│
└── cfg/                               # Configuration templates
    ├── rotation_config.json           # Rotation state and active DLCs
    ├── settings.json.example          # Sanitized settings template
    ├── configuration.json.example     # Network ports template
    └── assistRules.json.example       # Driving assists template
```

---

## 📄 License

This project is licensed under the **MIT** License. See the [LICENSE](LICENSE) file for more details.

*Assetto Corsa Competizione is a registered trademark of Kunos Simulazioni Srl and Digital Bros Group. This project is an independent community-developed tool and is not officially affiliated with Kunos Simulazioni.*
