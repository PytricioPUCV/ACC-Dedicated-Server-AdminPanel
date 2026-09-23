import ctypes
import hmac
import json
import mimetypes
import os
import re
import shutil
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from collections import deque
from datetime import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote

# Asegurar codificación utf-8 en la consola de Windows para evitar errores de charmap cp1252
if sys.stdout:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr:
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# --- 1. Elevación UAC en Windows ---
IS_FROZEN = getattr(sys, "frozen", False)
BUNDLE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

def elevate_if_needed():
    if "--no-uac" in sys.argv:
        return
    if not is_admin():
        print("[*] Solicitando permisos de Administrador para gestionar el servidor ACC...")
        if IS_FROZEN:
            exe = sys.executable
            args = " ".join(f'"{arg}"' for arg in sys.argv[1:])
        else:
            exe = sys.executable
            args = " ".join(f'"{arg}"' for arg in sys.argv)
        ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, args, None, 1)
        if ret > 32:
            sys.exit(0)
        else:
            print("[!] Advertencia: No se pudo elevar automáticamente. Continuando con permisos actuales...")

# --- 2. Rutas del Sistema y Detección Automática ---
def find_server_dir():
    # 1. Parámetro de línea de comandos explícito: --server-dir "<ruta>"
    for i, arg in enumerate(sys.argv[:-1]):
        if arg == "--server-dir":
            custom_path = sys.argv[i + 1]
            if os.path.exists(custom_path):
                return os.path.abspath(custom_path)

    base_dir = os.path.dirname(os.path.abspath(sys.executable if IS_FROZEN else __file__))

    # 2. Si accServer.exe está en el mismo directorio que el ejecutable / script
    if os.path.exists(os.path.join(base_dir, "accServer.exe")):
        return base_dir

    # 3. Si accServer.exe está en el directorio padre (ej. ejecutado desde server/AdminPanel)
    parent_dir = os.path.dirname(base_dir)
    if os.path.exists(os.path.join(parent_dir, "accServer.exe")):
        return parent_dir

    # 4. Comprobar ruta estándar de instalación de Steam
    steam_path = r"C:\Program Files (x86)\Steam\steamapps\common\Assetto Corsa Competizione Dedicated Server\server"
    if os.path.exists(os.path.join(steam_path, "accServer.exe")):
        return steam_path

    # 5. Fallback por estructura de carpetas
    if os.path.basename(base_dir).lower() == "adminpanel":
        return parent_dir
    return base_dir

def find_admin_panel_dir(srv_dir):
    base_dir = os.path.dirname(os.path.abspath(sys.executable if IS_FROZEN else __file__))
    if os.path.basename(base_dir).lower() == "adminpanel":
        return base_dir
    candidate = os.path.join(srv_dir, "AdminPanel")
    if os.path.isdir(candidate):
        return candidate
    return base_dir

def find_web_dir(admin_dir):
    # 1. Directorio web adyacente al ejecutable/script (permite personalizaciones del usuario)
    local_web = os.path.join(admin_dir, "web")
    if os.path.isdir(local_web) and os.path.exists(os.path.join(local_web, "index.html")):
        return local_web

    # 2. Directorio web empaquetado en PyInstaller (_MEIPASS)
    if IS_FROZEN:
        bundled_web = os.path.join(BUNDLE_DIR, "web")
        if os.path.isdir(bundled_web) and os.path.exists(os.path.join(bundled_web, "index.html")):
            return bundled_web

    return local_web

def seed_tracks_pool_if_empty(pools_dir):
    """Si la carpeta tracks_pool no existe o está vacía, copia las plantillas de circuitos incluidas."""
    os.makedirs(pools_dir, exist_ok=True)
    try:
        existing = [f for f in os.listdir(pools_dir) if f.endswith(".json")]
        if existing:
            return
    except OSError:
        pass

    candidates = []
    if IS_FROZEN:
        candidates.append(os.path.join(BUNDLE_DIR, "tracks_pool"))
    base_dir = os.path.dirname(os.path.abspath(sys.executable if IS_FROZEN else __file__))
    candidates.append(os.path.join(base_dir, "tracks_pool"))
    candidates.append(os.path.join(os.path.dirname(base_dir), "tracks_pool"))

    for candidate in candidates:
        if os.path.isdir(candidate):
            tracks = [f for f in os.listdir(candidate) if f.endswith(".json")]
            if tracks:
                print(f"[*] Inicializando tracks_pool/ con {len(tracks)} plantillas de circuitos...")
                for t in tracks:
                    try:
                        shutil.copy2(os.path.join(candidate, t), os.path.join(pools_dir, t))
                    except Exception:
                        pass
                break

SERVER_DIR = find_server_dir()
ADMIN_PANEL_DIR = find_admin_panel_dir(SERVER_DIR)
CFG_DIR = os.path.join(SERVER_DIR, "cfg")
RESULTS_DIR = os.path.join(SERVER_DIR, "results")
POOLS_DIR = os.path.join(SERVER_DIR, "tracks_pool")
LOG_DIR = os.path.join(SERVER_DIR, "log")
LOG_FILE = os.path.join(LOG_DIR, "server.log")
WEB_DIR = find_web_dir(ADMIN_PANEL_DIR)
EXE_PATH = os.path.join(SERVER_DIR, "accServer.exe")
BANLIST_FILE = os.path.join(CFG_DIR, "banlist.json")
ENTRYLIST_FILE = os.path.join(CFG_DIR, "entrylist.json")
PID_FILE = os.path.join(ADMIN_PANEL_DIR, "managed_acc_pid.json")
AUTH_FILE = os.path.join(ADMIN_PANEL_DIR, "panel_auth.json")
MAX_REQUEST_BYTES = 1_000_000
MAX_LOG_LINES = 1_000
MAX_RESULT_FILE_BYTES = 5_000_000
PANEL_TOKEN = None

# Diccionario oficial de modelos de coche de ACC (ServerAdminHandbook Apéndice IX.3)
CAR_MODELS = {
    0: "Porsche 991 GT3 R",
    1: "Mercedes-AMG GT3",
    2: "Ferrari 488 GT3",
    3: "Audi R8 LMS",
    4: "Lamborghini Huracan GT3",
    5: "McLaren 650S GT3",
    6: "Nissan GT-R Nismo GT3 2018",
    7: "BMW M6 GT3",
    8: "Bentley Continental GT3 2018",
    9: "Porsche 991II GT3 Cup",
    10: "Nissan GT-R Nismo GT3 2017",
    11: "Bentley Continental GT3 2016",
    12: "Aston Martin V12 Vantage GT3",
    13: "Lamborghini Gallardo R-EX",
    14: "Jaguar G3",
    15: "Lexus RC F GT3",
    16: "Lamborghini Huracan Evo (2019)",
    17: "Honda NSX GT3",
    18: "Lamborghini Huracan SuperTrofeo",
    19: "Audi R8 LMS Evo (2019)",
    20: "AMR V8 Vantage (2019)",
    21: "Honda NSX Evo (2019)",
    22: "McLaren 720S GT3 (2019)",
    23: "Porsche 911II GT3 R (2019)",
    24: "Ferrari 488 GT3 Evo 2020",
    25: "Mercedes-AMG GT3 2020",
    26: "Ferrari 488 Challenge Evo",
    27: "BMW M2 CS Racing",
    28: "Porsche 911 GT3 Cup (Type 992)",
    29: "Lamborghini Huracán Super Trofeo EVO2",
    30: "BMW M4 GT3",
    31: "Audi R8 LMS GT3 evo II",
    32: "Ferrari 296 GT3",
    33: "Lamborghini Huracan Evo2",
    34: "Porsche 992 GT3 R",
    35: "McLaren 720S GT3 Evo 2023",
    36: "Ford Mustang GT3",
    50: "Alpine A110 GT4",
    51: "AMR V8 Vantage GT4",
    52: "Audi R8 LMS GT4",
    53: "BMW M4 GT4",
    55: "Chevrolet Camaro GT4",
    56: "Ginetta G55 GT4",
    57: "KTM X-Bow GT4",
    58: "Maserati MC GT4",
    59: "McLaren 570S GT4",
    60: "Mercedes-AMG GT4",
    61: "Porsche 718 Cayman GT4",
    80: "Audi R8 LMS GT2",
    82: "KTM XBOW GT2",
    83: "Maserati MC20 GT2",
    84: "Mercedes AMG GT2",
    85: "Porsche 911 GT2 RS CS Evo",
    86: "Porsche 935"
}

ROTATION_CONFIG_FILE = os.path.join(CFG_DIR, "rotation_config.json")

# Categorías de DLCs oficiales de Assetto Corsa Competizione
DLC_CATEGORIES = {
    "base": {
        "name": "Juego Base",
        "description": "Blancpain GT Series (11 circuitos europeos principales)",
        "tracks": ["monza", "spa", "silverstone", "nurburgring", "barcelona", "brands_hatch", "misano", "paul_ricard", "zolder", "hungaroring", "zandvoort"]
    },
    "igtc": {
        "name": "Intercontinental GT Pack (IGTC)",
        "description": "Campeonato mundial de resistencia (4 circuitos)",
        "tracks": ["kyalami", "mount_panorama", "suzuka", "laguna_seca"]
    },
    "british_gt": {
        "name": "British GT Pack",
        "description": "Circuitos británicos tradicionales (3 circuitos)",
        "tracks": ["donington", "oulton_park", "snetterton"]
    },
    "usa": {
        "name": "American Track Pack (USA)",
        "description": "Circuitos emblemáticos de Norteamérica (3 circuitos)",
        "tracks": ["cota", "indianapolis", "watkins_glen"]
    },
    "gtw_2020": {
        "name": "2020 GT World Challenge Pack",
        "description": "Trazado de Imola",
        "tracks": ["imola"]
    },
    "gtw_2023": {
        "name": "2023 GT World Challenge Pack",
        "description": "Circuito Ricardo Tormo de Valencia",
        "tracks": ["valencia"]
    },
    "gt2": {
        "name": "GT2 Pack (2024)",
        "description": "Red Bull Ring Spielberg",
        "tracks": ["red_bull_ring"]
    },
    "nurburgring_24h": {
        "name": "24h Nürburgring Pack (2024)",
        "description": "Nürburgring Nordschleife 24h",
        "tracks": ["nurburgring_24h"]
    }
}

TRACK_NAME_MAP = {
    "monza": "Autodromo Nazionale Monza",
    "spa": "Circuit de Spa-Francorchamps",
    "silverstone": "Silverstone Circuit",
    "nurburgring": "Nürburgring GP",
    "barcelona": "Circuit de Barcelona-Catalunya",
    "brands_hatch": "Brands Hatch",
    "misano": "Misano World Circuit",
    "paul_ricard": "Circuit Paul Ricard",
    "zolder": "Circuit Zolder",
    "hungaroring": "Hungaroring",
    "zandvoort": "Circuit Zandvoort",
    "kyalami": "Kyalami Grand Prix Circuit",
    "mount_panorama": "Mount Panorama Circuit (Bathurst)",
    "suzuka": "Suzuka Circuit",
    "laguna_seca": "WeatherTech Raceway Laguna Seca",
    "imola": "Autodromo Enzo e Dino Ferrari (Imola)",
    "donington": "Donington Park",
    "oulton_park": "Oulton Park",
    "snetterton": "Snetterton 300",
    "cota": "Circuit of the Americas (COTA)",
    "indianapolis": "Indianapolis Motor Speedway",
    "watkins_glen": "Watkins Glen International",
    "valencia": "Circuit Ricardo Tormo (Valencia)",
    "red_bull_ring": "Red Bull Ring (Spielberg)",
    "nurburgring_24h": "Nürburgring Nordschleife 24h"
}

VALID_TRACK_FILES = {f"{track_id}.json" for track_id in TRACK_NAME_MAP}
VALID_TRACK_CODES = set(TRACK_NAME_MAP)
PLAYER_ID_RE = re.compile(r"^S\d{5,25}$")

# --- Helpers de Codificación y Archivos ---
def read_json_safe(filepath, default=None):
    if not os.path.exists(filepath):
        return default
    encodings = ["utf-16", "utf-16-le", "utf-8", "latin-1"]
    for enc in encodings:
        try:
            with open(filepath, "r", encoding=enc) as f:
                return json.load(f)
        except Exception:
            continue
    return default

def atomic_write_json(filepath, data, encoding):
    """Escribe JSON de forma atómica y conserva el último archivo válido como .bak."""
    directory = os.path.dirname(filepath)
    os.makedirs(directory, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2).encode(encoding)
    fd, tmp_path = tempfile.mkstemp(prefix=f".{os.path.basename(filepath)}.", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        if os.path.exists(filepath):
            shutil.copy2(filepath, f"{filepath}.bak")
        os.replace(tmp_path, filepath)
    except Exception:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise

def write_json_utf16(filepath, data):
    """Guarda JSON con codificación UTF-16 LE y BOM (estrictamente requerido por ACC para settings/configuration/assistRules)"""
    atomic_write_json(filepath, data, "utf-16")

def get_rotation_config():
    default_config = {
        "active_dlcs": list(DLC_CATEGORIES.keys()),
        "disabled_tracks": []
    }
    data = read_json_safe(ROTATION_CONFIG_FILE, default_config)
    if not isinstance(data, dict):
        data = default_config
    data["active_dlcs"] = [
        dlc_id for dlc_id in data.get("active_dlcs", default_config["active_dlcs"])
        if dlc_id in DLC_CATEGORIES
    ]
    data["disabled_tracks"] = [
        track_file for track_file in data.get("disabled_tracks", [])
        if track_file in VALID_TRACK_FILES
    ]
    if not data["active_dlcs"]:
        data["active_dlcs"] = ["base"]
    return data

def save_rotation_config(cfg):
    atomic_write_json(ROTATION_CONFIG_FILE, cfg, "utf-8")

def compute_active_track_rotation(rotation_cfg=None, fallback=True):
    cfg = rotation_cfg if rotation_cfg is not None else get_rotation_config()
    active_dlcs = set(cfg.get("active_dlcs", list(DLC_CATEGORIES.keys())))
    disabled_tracks = set(cfg.get("disabled_tracks", []))

    rotation = []
    for dlc_id, dlc_info in DLC_CATEGORIES.items():
        if dlc_id in active_dlcs:
            for t_id in dlc_info["tracks"]:
                filename = f"{t_id}.json"
                if filename not in disabled_tracks:
                    rotation.append(filename)

    if not rotation and fallback:
        # Nunca dejar un orquestador sin una pista arrancable.
        rotation = ["monza.json"]
    return rotation

TRACK_ROTATION = compute_active_track_rotation()

# --- 3. Estado Global del Servidor y Orquestador ---
lifecycle_lock = threading.RLock()
state_lock = threading.RLock()
config_lock = threading.RLock()
app_state = {
    "auto_rotation": True,
    "current_track_idx": -1,
    "current_track_file": None,
    "last_race_mtime": 0,
    "server_start_time": 0,
    "status_message": "Servidor inicializado",
    "server_process_pid": None,
    "rotation_epoch": 0
}

def write_json_utf8(filepath, data):
    """Guarda JSON con codificación UTF-8 estándar (para event.json y tracks_pool)"""
    atomic_write_json(filepath, data, "utf-8")

def get_banlist():
    data = read_json_safe(BANLIST_FILE, [])
    if isinstance(data, list):
        return data
    return []

def save_banlist(banlist):
    write_json_utf8(BANLIST_FILE, banlist)

def get_entrylist():
    data = read_json_safe(ENTRYLIST_FILE, None)
    if not data or not isinstance(data, dict):
        data = {
            "entries": [],
            "configVersion": 1,
            "forceEntryList": 0
        }
    return data

def save_entrylist(entrylist):
    write_json_utf16(ENTRYLIST_FILE, entrylist)


class ValidationError(ValueError):
    pass


def clean_text(value, field, max_length, allow_empty=False):
    if not isinstance(value, str):
        raise ValidationError(f"{field} debe ser texto.")
    value = value.strip()
    if (not value and not allow_empty) or len(value) > max_length or any(ord(char) < 32 for char in value):
        raise ValidationError(f"{field} no tiene un formato válido.")
    return value


def bounded_int(value, field, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValidationError(f"{field} debe estar entre {minimum} y {maximum}.")
    return value


def bounded_number(value, field, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not minimum <= value <= maximum:
        raise ValidationError(f"{field} debe estar entre {minimum} y {maximum}.")
    return value


def validate_player_id(value):
    value = clean_text(value, "playerId", 26)
    if not PLAYER_ID_RE.fullmatch(value):
        raise ValidationError("playerId debe ser un Steam ID de ACC válido.")
    return value


def validate_config_payload(post_data):
    if not isinstance(post_data, dict):
        raise ValidationError("El cuerpo debe ser un objeto JSON.")

    current = {
        "settings": read_json_safe(os.path.join(CFG_DIR, "settings.json"), {}),
        "configuration": read_json_safe(os.path.join(CFG_DIR, "configuration.json"), {}),
        "event": read_json_safe(os.path.join(CFG_DIR, "event.json"), {}),
        "assistRules": read_json_safe(os.path.join(CFG_DIR, "assistRules.json"), {})
    }
    validated = {}

    if "settings" in post_data:
        incoming = post_data["settings"]
        if not isinstance(incoming, dict):
            raise ValidationError("settings debe ser un objeto.")
        settings = {**current["settings"], **incoming}
        settings["serverName"] = clean_text(settings.get("serverName", ""), "serverName", 128)
        settings["adminPassword"] = clean_text(settings.get("adminPassword", ""), "adminPassword", 128)
        settings["password"] = clean_text(settings.get("password", ""), "password", 128, allow_empty=True)
        settings["maxCarSlots"] = bounded_int(settings.get("maxCarSlots"), "maxCarSlots", 1, 100)
        settings["isRaceLocked"] = bounded_int(settings.get("isRaceLocked"), "isRaceLocked", 0, 1)
        if settings.get("carGroup") not in {"FreeForAll", "GT3", "GT4", "Cup", "ST"}:
            raise ValidationError("carGroup no es válido.")
        settings["dumpLeaderboards"] = 1
        settings["configVersion"] = 1
        validated["settings"] = settings

    if "configuration" in post_data:
        incoming = post_data["configuration"]
        if not isinstance(incoming, dict):
            raise ValidationError("configuration debe ser un objeto.")
        configuration = {**current["configuration"], **incoming}
        for key in ("udpPort", "tcpPort"):
            configuration[key] = bounded_int(configuration.get(key), key, 1, 65535)
        configuration["maxConnections"] = bounded_int(configuration.get("maxConnections"), "maxConnections", 1, 100)
        configuration["configVersion"] = 1
        validated["configuration"] = configuration

    if "event" in post_data:
        incoming = post_data["event"]
        if not isinstance(incoming, dict):
            raise ValidationError("event debe ser un objeto.")
        event = {**current["event"], **incoming}
        if event.get("track") not in VALID_TRACK_CODES:
            raise ValidationError("La pista del evento no es válida.")
        if current["event"].get("track") and event["track"] != current["event"]["track"]:
            raise ValidationError("Selecciona una pista desde el catálogo antes de editar su evento.")
        for key, minimum, maximum in (
            ("preRaceWaitingTimeSeconds", 0, 3600),
            ("sessionOverTimeSeconds", 0, 3600),
            ("ambientTemp", -10, 60),
            ("weatherRandomness", 0, 10)
        ):
            event[key] = bounded_int(event.get(key), key, minimum, maximum)
        for key in ("cloudLevel", "rain"):
            event[key] = bounded_number(event.get(key), key, 0, 1)
        sessions = event.get("sessions")
        if not isinstance(sessions, list) or not 1 <= len(sessions) <= 10:
            raise ValidationError("sessions debe contener entre 1 y 10 sesiones.")
        for session in sessions:
            if not isinstance(session, dict) or session.get("sessionType") not in {"P", "FP", "Q", "R"}:
                raise ValidationError("Hay una sesión con tipo inválido.")
            session["sessionDurationMinutes"] = bounded_int(
                session.get("sessionDurationMinutes"), "sessionDurationMinutes", 1, 1440
            )
        event["configVersion"] = 1
        validated["event"] = event

    if "assistRules" in post_data:
        incoming = post_data["assistRules"]
        if not isinstance(incoming, dict):
            raise ValidationError("assistRules debe ser un objeto.")
        assist = {**current["assistRules"], **incoming}
        assist["stabilityControlLevelMax"] = bounded_int(
            assist.get("stabilityControlLevelMax"), "stabilityControlLevelMax", 0, 100
        )
        for key in (
            "disableIdealLine", "disableAutosteer", "disableAutoPitLimiter", "disableAutoGear",
            "disableAutoClutch", "disableAutoEngineStart", "disableAutoWiper", "disableAutoLights"
        ):
            assist[key] = bounded_int(assist.get(key), key, 0, 1)
        validated["assistRules"] = assist

    if not validated:
        raise ValidationError("No se recibió ninguna sección de configuración.")
    return validated


def validate_entrylist(entrylist):
    if not isinstance(entrylist, dict) or not isinstance(entrylist.get("entries", []), list):
        raise ValidationError("entrylist no tiene un formato válido.")
    if len(entrylist["entries"]) > 200:
        raise ValidationError("entrylist supera el máximo de 200 entradas.")
    entrylist = dict(entrylist)
    entrylist["configVersion"] = 1
    entrylist["forceEntryList"] = bounded_int(entrylist.get("forceEntryList", 0), "forceEntryList", 0, 1)
    for entry in entrylist["entries"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("drivers"), list) or not entry["drivers"]:
            raise ValidationError("Cada entrada debe tener al menos un piloto.")
        entry["raceNumber"] = bounded_int(entry.get("raceNumber", 99), "raceNumber", 1, 998)
        entry["isServerAdmin"] = bounded_int(entry.get("isServerAdmin", 0), "isServerAdmin", 0, 1)
        for driver in entry["drivers"]:
            if not isinstance(driver, dict):
                raise ValidationError("Piloto inválido en entrylist.")
            driver["playerID"] = validate_player_id(driver.get("playerID", ""))
            driver["firstName"] = clean_text(driver.get("firstName", ""), "firstName", 64)
            driver["lastName"] = clean_text(driver.get("lastName", ""), "lastName", 64, allow_empty=True)
    return entrylist

def parse_active_players():
    active = {}
    banlist = get_banlist()
    banned_ids = {b.get("playerId") for b in banlist}
    entrylist = get_entrylist()
    admin_ids = set()
    for entry in entrylist.get("entries", []):
        if entry.get("isServerAdmin") == 1:
            for d in entry.get("drivers", []):
                if d.get("playerID"):
                    admin_ids.add(d.get("playerID"))

    # 1. Parsear server.log si accServer está corriendo
    if os.path.exists(LOG_FILE) and is_acc_running():
        try:
            with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                lines = deque(f, maxlen=800)
            for line in lines:
                # Detectar connId y playerID
                if "has playerID" in line and "Client" in line:
                    m = re.search(r"Client\s+(\d+)\s+has\s+playerID\s+(S\w+)\s+name\s+(.*)", line)
                    if m:
                        cid, pid, name = m.group(1), m.group(2), m.group(3).strip()
                        active[cid] = {
                            "conn_id": int(cid),
                            "player_id": pid,
                            "driver_name": name,
                            "car_id": None,
                            "race_number": None,
                            "car_model_id": None,
                            "car_model_name": "GT3",
                            "ping_ms": 28,
                            "is_connected": True
                        }
                # Asignación de coche
                if "assigned to connection" in line:
                    m = re.search(r"car\s+(\d+)\s+\(raceNumber\s+(\d+)\)\s+assigned\s+to\s+connection\s+(\d+)", line)
                    if m:
                        car_id, r_num, cid = m.group(1), m.group(2), m.group(3)
                        if cid in active:
                            active[cid]["car_id"] = int(car_id)
                            active[cid]["race_number"] = int(r_num)
                # Latencia / ping
                if "lastUdpPaketReceived for connId" in line:
                    m = re.search(r"for\s+connId\s+(\d+):\s+(\d+)\s+ms", line)
                    if m:
                        cid, ping = m.group(1), m.group(2)
                        if cid in active:
                            active[cid]["ping_ms"] = min(int(ping), 999)
                # Desconexión
                if "closed the connection" in line or "Removing dead connection" in line or "disco to connection" in line:
                    m = re.search(r"(?:Client|connection)\s+(\d+)", line)
                    if m:
                        cid = m.group(1)
                        if cid in active:
                            del active[cid]
        except Exception as e:
            print(f"[!] Error parsing server.log for players: {e}")

    # 2. Extraer pilotos recientes de results/*.json
    recent = []
    seen_pids = set()
    if os.path.exists(RESULTS_DIR):
        r_files = sorted([f for f in os.listdir(RESULTS_DIR) if f.endswith(".json")], reverse=True)
        for rf in r_files[:10]:
            fp = os.path.join(RESULTS_DIR, rf)
            try:
                if os.path.getsize(fp) > MAX_RESULT_FILE_BYTES:
                    continue
            except OSError:
                continue
            data = read_json_safe(fp)
            if not data:
                continue
            sr = data.get("sessionResult", {})
            for line in sr.get("leaderBoardLines", []):
                driver = line.get("currentDriver", {})
                pid = driver.get("playerId", "")
                if not pid or pid in seen_pids:
                    continue
                seen_pids.add(pid)
                fn = driver.get("firstName", "")
                ln = driver.get("lastName", "")
                name = f"{fn} {ln}".strip() or "Piloto"
                car = line.get("car", {})
                c_model = car.get("carModel", 0)
                r_num = car.get("raceNumber", 0)
                timing = line.get("timing", {})
                recent.append({
                    "player_id": pid,
                    "driver_name": name,
                    "race_number": r_num,
                    "car_model_id": c_model,
                    "car_model_name": CAR_MODELS.get(c_model, f"Car #{c_model}"),
                    "car_group": car.get("carGroup", "GT3"),
                    "best_lap_ms": timing.get("bestLap", 0),
                    "total_laps": timing.get("lapCount", 0),
                    "is_admin": pid in admin_ids,
                    "is_banned": pid in banned_ids,
                    "last_session": rf
                })

    active_list = []
    for cid, p in active.items():
        pid = p["player_id"]
        p["is_admin"] = pid in admin_ids
        p["is_banned"] = pid in banned_ids
        if p.get("car_model_id") is not None:
            p["car_model_name"] = CAR_MODELS.get(p["car_model_id"], "GT3")
        active_list.append(p)

    return {
        "active_players": active_list,
        "recent_players": recent,
        "total_active": len(active_list),
        "banlist": banlist,
        "entrylist": entrylist
    }

def is_pid_acc_running(pid):
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
        )
        return "accServer.exe" in result.stdout
    except Exception:
        return False


def is_any_acc_running():
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq accServer.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
        )
        return "accServer.exe" in result.stdout
    except Exception:
        return False


def load_managed_pid():
    with state_lock:
        pid = app_state.get("server_process_pid")
    if is_pid_acc_running(pid):
        return pid

    persisted = read_json_safe(PID_FILE, {})
    candidate = persisted.get("pid") if isinstance(persisted, dict) else None
    if is_pid_acc_running(candidate):
        with state_lock:
            app_state["server_process_pid"] = candidate
            started_at = persisted.get("started_at") if isinstance(persisted, dict) else None
            if isinstance(started_at, (int, float)):
                app_state["server_start_time"] = started_at
        return candidate

    with state_lock:
        app_state["server_process_pid"] = None
        app_state["server_start_time"] = 0
    return None


def clear_managed_pid_file():
    if os.path.isfile(PID_FILE):
        os.unlink(PID_FILE)


def is_acc_running():
    """Indica únicamente el accServer lanzado o adoptado por este panel."""
    return load_managed_pid() is not None


def is_valid_track_file(track_file):
    return (
        isinstance(track_file, str)
        and track_file in VALID_TRACK_FILES
        and os.path.isfile(os.path.join(POOLS_DIR, track_file))
    )


def sync_state_from_event():
    """Alinea el orquestador con cfg/event.json antes de controlar ACC."""
    event_cfg = read_json_safe(os.path.join(CFG_DIR, "event.json"), {})
    candidate = f"{event_cfg.get('track', '')}.json"
    if not is_valid_track_file(candidate):
        candidate = TRACK_ROTATION[0]
    with state_lock:
        app_state["current_track_file"] = candidate
        app_state["current_track_idx"] = TRACK_ROTATION.index(candidate) if candidate in TRACK_ROTATION else -1
    return candidate

def kill_acc_server():
    """Detiene sólo el proceso ACC gestionado por este panel, nunca por imagen global."""
    with lifecycle_lock:
        pid = load_managed_pid()
        if pid is None:
            with state_lock:
                app_state["status_message"] = "No hay un accServer gestionado por este panel para detener."
            return False

        print(f"[*] Terminando accServer.exe gestionado (PID {pid}) y liberando sockets...")
        subprocess.run(["taskkill", "/F", "/PID", str(pid), "/T"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2.5)
        clear_managed_pid_file()
        with state_lock:
            app_state["server_process_pid"] = None
            app_state["server_start_time"] = 0
        return True

def start_acc_server(track_file=None):
    with lifecycle_lock:
        if is_acc_running():
            raise RuntimeError("El accServer gestionado ya está en ejecución.")
        if is_any_acc_running():
            raise RuntimeError("Hay otro accServer.exe en ejecución. Deténlo manualmente antes de iniciar este panel.")

        if track_file is None:
            with state_lock:
                track_file = app_state.get("current_track_file")
            if not is_valid_track_file(track_file):
                track_file = sync_state_from_event()
        if not is_valid_track_file(track_file):
            raise ValidationError("La plantilla de pista seleccionada no existe o no está permitida.")

        template = read_json_safe(os.path.join(POOLS_DIR, track_file), None)
        if not isinstance(template, dict) or template.get("track") not in VALID_TRACK_CODES:
            raise RuntimeError("La plantilla de pista no contiene un evento ACC válido.")

        write_json_utf8(os.path.join(CFG_DIR, "event.json"), template)
        print(f"[+] Pista aplicada desde la plantilla: {track_file}")
        print(f"[+] Lanzando accServer.exe en {SERVER_DIR}...")
        proc = subprocess.Popen([EXE_PATH], cwd=SERVER_DIR)
        atomic_write_json(PID_FILE, {"pid": proc.pid, "started_at": time.time()}, "utf-8")

        with state_lock:
            app_state["current_track_file"] = track_file
            app_state["current_track_idx"] = TRACK_ROTATION.index(track_file) if track_file in TRACK_ROTATION else -1
            app_state["server_process_pid"] = proc.pid
            app_state["server_start_time"] = time.time()
            app_state["status_message"] = f"Servidor en línea en pista: {track_file}"
        return proc

def get_latest_race_result():
    if not os.path.exists(RESULTS_DIR):
        return None, 0
    race_files = []
    for f in os.listdir(RESULTS_DIR):
        if f.endswith("_R") or f.endswith("_R.json"):
            full_path = os.path.join(RESULTS_DIR, f)
            try:
                race_files.append((full_path, os.path.getmtime(full_path)))
            except Exception:
                pass
    if not race_files:
        return None, 0
    return max(race_files, key=lambda x: x[1])

# --- 5. Hilo de Auto-Rotación de Circuitos ---
def rotation_worker():
    _, last_mtime = get_latest_race_result()
    with state_lock:
        app_state["last_race_mtime"] = last_mtime

    print("[*] Hilo orquestador de rotación activo.")
    while True:
        try:
            time.sleep(3)
            with state_lock:
                auto_rot = app_state["auto_rotation"]
                prev_mtime = app_state["last_race_mtime"]
                epoch = app_state["rotation_epoch"]

            latest_file, mtime = get_latest_race_result()

            if auto_rot and is_acc_running() and latest_file and mtime > prev_mtime:
                with state_lock:
                    app_state["last_race_mtime"] = mtime
                    app_state["status_message"] = f"Carrera terminada: {os.path.basename(latest_file)}. Esperando 12s para podio..."

                print(f"\n[🏁] ¡Carrera terminada detectada!: {os.path.basename(latest_file)}")
                print("[*] Esperando 12 segundos de cortesía para pantalla de podio...")
                time.sleep(12)

                with lifecycle_lock:
                    with state_lock:
                        still_valid = (
                            app_state["auto_rotation"]
                            and app_state["rotation_epoch"] == epoch
                            and is_acc_running()
                        )
                    if not still_valid:
                        continue
                    print("[*] Rotando a la siguiente pista...")
                    if not kill_acc_server():
                        continue
                    with state_lock:
                        app_state["current_track_idx"] = (app_state["current_track_idx"] + 1) % len(TRACK_ROTATION)
                        next_track = TRACK_ROTATION[app_state["current_track_idx"]]
                    start_acc_server(next_track)

        except Exception as e:
            print(f"[!] Excepción en rotation_worker: {e}")
            time.sleep(5)


def refresh_rotation_state():
    """Recarga la rotación manteniendo la pista actual cuando siga disponible."""
    global TRACK_ROTATION
    new_rotation = compute_active_track_rotation()
    with state_lock:
        current_track = app_state.get("current_track_file")
        TRACK_ROTATION = new_rotation
        app_state["current_track_idx"] = new_rotation.index(current_track) if current_track in new_rotation else -1
        app_state["rotation_epoch"] += 1
    return list(new_rotation)


def load_or_create_panel_token():
    environment_token = os.environ.get("ACC_PANEL_TOKEN", "").strip()
    if environment_token:
        if len(environment_token) < 24:
            raise RuntimeError("ACC_PANEL_TOKEN debe contener al menos 24 caracteres.")
        return environment_token

    stored = read_json_safe(AUTH_FILE, {})
    token = stored.get("token") if isinstance(stored, dict) else None
    if isinstance(token, str) and len(token) >= 24:
        return token

    token = secrets.token_urlsafe(32)
    atomic_write_json(AUTH_FILE, {"token": token, "created_at": datetime.now().isoformat(timespec="seconds")}, "utf-8")
    return token


def is_authorized(handler):
    supplied = handler.headers.get("X-Admin-Token", "")
    return bool(PANEL_TOKEN and supplied and hmac.compare_digest(supplied, PANEL_TOKEN))


def safe_web_file_path(url_path):
    decoded_path = unquote(url_path)
    if "\x00" in decoded_path:
        return None
    relative_path = decoded_path.lstrip("/\\").replace("/", os.sep).replace("\\", os.sep)
    base = os.path.realpath(WEB_DIR)
    candidate = os.path.realpath(os.path.join(base, relative_path))
    try:
        if os.path.commonpath([base, candidate]) != base:
            return None
    except ValueError:
        return None
    return candidate


# --- 6. Manejador de Solicitudes HTTP (REST API + Web GUI) ---
class AdminPanelHandler(BaseHTTPRequestHandler):
    def send_json(self, data, status_code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_error(405, "Método no permitido")

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/") and not is_authorized(self):
            self.send_json({"error": "No autorizado"}, 401)
            return

        if path == "/api/status":
            self.handle_api_status()
        elif path == "/api/tracks":
            self.handle_api_tracks()
        elif path == "/api/config":
            self.handle_api_get_config()
        elif path == "/api/telemetry":
            self.handle_api_telemetry()
        elif path == "/api/players":
            self.send_json(parse_active_players())
        elif path == "/api/entrylist":
            self.send_json(get_entrylist())
        elif path == "/api/banlist":
            self.send_json(get_banlist())
        elif path == "/api/logs":
            self.handle_api_logs(parse_qs(parsed.query))
        else:
            self.handle_static_files(path)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if not path.startswith("/api/") or not is_authorized(self):
            self.send_json({"error": "No autorizado"}, 401)
            return
        try:
            content_len = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_json({"success": False, "message": "Content-Length inválido."}, 400)
            return
        if content_len < 0 or content_len > MAX_REQUEST_BYTES:
            self.send_json({"success": False, "message": "Solicitud demasiado grande."}, 413)
            return
        post_data = {}
        if content_len > 0:
            try:
                raw_body = self.rfile.read(content_len).decode("utf-8")
                post_data = json.loads(raw_body)
            except (UnicodeDecodeError, json.JSONDecodeError):
                self.send_json({"success": False, "message": "JSON inválido."}, 400)
                return
        if not isinstance(post_data, dict):
            self.send_json({"success": False, "message": "El cuerpo debe ser un objeto JSON."}, 400)
            return

        if path == "/api/server/start":
            try:
                if is_acc_running():
                    self.send_json({"success": True, "message": "accServer ya se encuentra en ejecución."})
                else:
                    start_acc_server()
                    self.send_json({"success": True, "message": "accServer iniciado correctamente."})
            except (RuntimeError, OSError, ValidationError) as error:
                self.send_json({"success": False, "message": str(error)}, 409)

        elif path == "/api/server/stop":
            with state_lock:
                app_state["rotation_epoch"] += 1
            if kill_acc_server():
                self.send_json({"success": True, "message": "accServer detenido y puertos liberados."})
            else:
                self.send_json({"success": False, "message": "No hay un accServer gestionado para detener."}, 409)

        elif path == "/api/server/restart":
            try:
                with lifecycle_lock:
                    with state_lock:
                        app_state["rotation_epoch"] += 1
                    if is_acc_running() and not kill_acc_server():
                        raise RuntimeError("No fue posible detener el accServer gestionado.")
                    start_acc_server()
                self.send_json({"success": True, "message": "accServer reiniciado correctamente."})
            except (RuntimeError, OSError, ValidationError) as error:
                self.send_json({"success": False, "message": str(error)}, 409)

        elif path == "/api/rotation/toggle":
            with state_lock:
                app_state["auto_rotation"] = not app_state["auto_rotation"]
                val = app_state["auto_rotation"]
                app_state["rotation_epoch"] += 1
            self.send_json({"success": True, "auto_rotation": val, "message": f"Auto-rotación: {'Habilitada' if val else 'Pausada'}"})

        elif path == "/api/rotation/skip":
            try:
                with lifecycle_lock:
                    with state_lock:
                        app_state["rotation_epoch"] += 1
                    if is_acc_running() and not kill_acc_server():
                        raise RuntimeError("No fue posible detener el accServer gestionado.")
                    with state_lock:
                        app_state["current_track_idx"] = (app_state["current_track_idx"] + 1) % len(TRACK_ROTATION)
                        next_track = TRACK_ROTATION[app_state["current_track_idx"]]
                    start_acc_server(next_track)
                self.send_json({"success": True, "track": next_track, "message": f"Saltado a {next_track}"})
            except (RuntimeError, OSError, ValidationError) as error:
                self.send_json({"success": False, "message": str(error)}, 409)

        elif path == "/api/rotation/select":
            track_file = post_data.get("track_file")
            if not is_valid_track_file(track_file):
                self.send_json({"success": False, "message": "track_file no es una plantilla permitida."}, 400)
                return
            try:
                with lifecycle_lock:
                    with state_lock:
                        app_state["rotation_epoch"] += 1
                    if is_acc_running() and not kill_acc_server():
                        raise RuntimeError("No fue posible detener el accServer gestionado.")
                    start_acc_server(track_file)
                self.send_json({"success": True, "track": track_file, "message": f"Pista cambiada a {track_file}"})
            except (RuntimeError, OSError, ValidationError) as error:
                self.send_json({"success": False, "message": str(error)}, 409)

        elif path == "/api/rotation/dlc-toggle":
            dlc_id = post_data.get("dlc_id")
            enabled = post_data.get("enabled", True)
            if not dlc_id or dlc_id not in DLC_CATEGORIES or not isinstance(enabled, bool):
                self.send_json({"success": False, "message": "DLC no válido"}, 400)
                return
            
            cfg = get_rotation_config()
            active = set(cfg.get("active_dlcs", list(DLC_CATEGORIES.keys())))
            if enabled:
                active.add(dlc_id)
            else:
                active.discard(dlc_id)
            if not active:
                active.add("base")
            
            cfg["active_dlcs"] = [item for item in DLC_CATEGORIES if item in active]
            if not compute_active_track_rotation(cfg, fallback=False):
                self.send_json({"success": False, "message": "La rotación debe conservar al menos una pista."}, 400)
                return
            save_rotation_config(cfg)
            rotation_pool = refresh_rotation_state()
            
            self.send_json({
                "success": True,
                "message": f"DLC {DLC_CATEGORIES[dlc_id]['name']} {'activado' if enabled else 'desactivado'}",
                "active_dlcs": cfg["active_dlcs"],
                "rotation_pool": rotation_pool
            })

        elif path == "/api/rotation/track-toggle":
            track_file = post_data.get("track_file")
            enabled = post_data.get("enabled", True)
            if not is_valid_track_file(track_file) or not isinstance(enabled, bool):
                self.send_json({"success": False, "message": "track_file no es una plantilla permitida."}, 400)
                return
            
            cfg = get_rotation_config()
            disabled = set(cfg.get("disabled_tracks", []))
            if enabled:
                disabled.discard(track_file)
            else:
                disabled.add(track_file)
            
            cfg["disabled_tracks"] = list(disabled)
            if not compute_active_track_rotation(cfg, fallback=False):
                self.send_json({"success": False, "message": "La rotación debe conservar al menos una pista."}, 400)
                return
            save_rotation_config(cfg)
            rotation_pool = refresh_rotation_state()
            
            self.send_json({
                "success": True,
                "message": f"Pista {track_file} {'activada' if enabled else 'desactivada'} en rotación",
                "disabled_tracks": cfg["disabled_tracks"],
                "rotation_pool": rotation_pool
            })

        elif path == "/api/rotation/preset":
            preset = post_data.get("preset", "all")
            cfg = get_rotation_config()
            if preset == "all":
                cfg["active_dlcs"] = list(DLC_CATEGORIES.keys())
                cfg["disabled_tracks"] = []
            elif preset == "base_only":
                cfg["active_dlcs"] = ["base"]
                cfg["disabled_tracks"] = []
            elif preset == "dlc_only":
                cfg["active_dlcs"] = [k for k in DLC_CATEGORIES.keys() if k != "base"]
                cfg["disabled_tracks"] = []
            else:
                self.send_json({"success": False, "message": "Preset no válido."}, 400)
                return
            save_rotation_config(cfg)
            rotation_pool = refresh_rotation_state()
            
            self.send_json({
                "success": True,
                "message": f"Preset '{preset}' aplicado exitosamente",
                "active_dlcs": cfg["active_dlcs"],
                "rotation_pool": rotation_pool
            })

        elif path == "/api/config":
            self.handle_api_save_config(post_data)

        elif path == "/api/moderation/ban":
            try:
                player_id = validate_player_id(post_data.get("playerId", ""))
                driver_name = clean_text(post_data.get("driverName", "Desconocido"), "driverName", 128)
                car_number = bounded_int(post_data.get("carNumber", 0), "carNumber", 0, 998)
                reason = clean_text(post_data.get("reason", "Infracción de normas"), "reason", 256)
                with config_lock:
                    banlist = get_banlist()
                    existing = next((b for b in banlist if b.get("playerId") == player_id), None)
                    if existing:
                        existing.update({"driverName": driver_name, "carNumber": car_number, "reason": reason})
                        existing["date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        banlist.append({
                            "playerId": player_id, "driverName": driver_name, "carNumber": car_number,
                            "reason": reason, "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })
                    save_banlist(banlist)
                self.send_json({"success": True, "message": f"Piloto {driver_name} añadido a la lista negra."})
            except ValidationError as error:
                self.send_json({"success": False, "message": str(error)}, 400)

        elif path == "/api/moderation/unban":
            try:
                player_id = validate_player_id(post_data.get("playerId", ""))
                with config_lock:
                    banlist = [b for b in get_banlist() if b.get("playerId") != player_id]
                    save_banlist(banlist)
                self.send_json({"success": True, "message": "Piloto removido de la lista negra."})
            except ValidationError as error:
                self.send_json({"success": False, "message": str(error)}, 400)

        elif path == "/api/moderation/admin":
            try:
                player_id = validate_player_id(post_data.get("playerId", ""))
                driver_name = clean_text(post_data.get("driverName", "Piloto"), "driverName", 128)
                car_number = bounded_int(post_data.get("carNumber", 88), "carNumber", 1, 998)
                is_admin_req = post_data.get("isAdmin", True)
                if not isinstance(is_admin_req, bool):
                    raise ValidationError("isAdmin debe ser booleano.")
                with config_lock:
                    entrylist = get_entrylist()
                    entries = entrylist.setdefault("entries", [])
                    target = next(
                        (entry for entry in entries if any(d.get("playerID") == player_id for d in entry.get("drivers", []))), None
                    )
                    if target:
                        target["isServerAdmin"] = 1 if is_admin_req else 0
                    else:
                        first_n, _, last_n = driver_name.partition(" ")
                        entries.append({
                            "drivers": [{"firstName": first_n, "lastName": last_n, "shortName": first_n[:3].upper(),
                                         "driverCategory": 3, "playerID": player_id}],
                            "raceNumber": car_number, "forcedCarModel": -1, "overrideDriverInfo": 0,
                            "isServerAdmin": 1 if is_admin_req else 0
                        })
                    save_entrylist(validate_entrylist(entrylist))
                status_text = "Administrador Permanente" if is_admin_req else "Piloto Estándar"
                self.send_json({"success": True, "message": f"{driver_name} ahora tiene rol de {status_text}."})
            except ValidationError as error:
                self.send_json({"success": False, "message": str(error)}, 400)

        elif path == "/api/entrylist":
            try:
                with config_lock:
                    save_entrylist(validate_entrylist(post_data))
                self.send_json({"success": True, "message": "Entry list actualizada en cfg/entrylist.json."})
            except ValidationError as error:
                self.send_json({"success": False, "message": str(error)}, 400)
            except OSError:
                self.send_json({"success": False, "message": "No se pudo guardar entrylist."}, 500)

        else:
            self.send_json({"error": "Endpoint no encontrado"}, 404)

    # --- Métodos de Control de API ---
    def handle_api_status(self):
        running = is_acc_running()
        pid = load_managed_pid() if running else None
        event_cfg = read_json_safe(os.path.join(CFG_DIR, "event.json"), {})
        settings_cfg = read_json_safe(os.path.join(CFG_DIR, "settings.json"), {})

        uptime = 0
        with state_lock:
            if running and app_state["server_start_time"] > 0:
                uptime = int(time.time() - app_state["server_start_time"])
            auto_rot = app_state["auto_rotation"]
            cur_idx = app_state["current_track_idx"]
            cur_file = app_state["current_track_file"]
            msg = app_state["status_message"]

        self.send_json({
            "is_running": running,
            "unmanaged_acc_detected": is_any_acc_running() and not running,
            "pid": pid,
            "uptime_seconds": uptime,
            "auto_rotation": auto_rot,
            "current_track_index": cur_idx,
            "current_track_file": cur_file,
            "rotation_pool": TRACK_ROTATION,
            "status_message": msg,
            "track_name": event_cfg.get("track", "Desconocido"),
            "server_name": settings_cfg.get("serverName", "ACC Dedicated Server"),
            "max_car_slots": settings_cfg.get("maxCarSlots", 24),
            "sessions": event_cfg.get("sessions", [])
        })

    def handle_api_tracks(self):
        rot_cfg = get_rotation_config()
        active_dlcs_set = set(rot_cfg.get("active_dlcs", list(DLC_CATEGORIES.keys())))
        disabled_tracks_set = set(rot_cfg.get("disabled_tracks", []))

        with state_lock:
            current_active_rotation = list(TRACK_ROTATION)
            current_track = app_state["current_track_file"]

        # Cache file configs
        file_configs = {}
        if os.path.exists(POOLS_DIR):
            for f in os.listdir(POOLS_DIR):
                if f.endswith(".json"):
                    full_p = os.path.join(POOLS_DIR, f)
                    file_configs[f] = read_json_safe(full_p, {})

        categories_data = []
        all_tracks_flat = []

        for cat_id, cat_info in DLC_CATEGORIES.items():
            is_dlc_active = cat_id in active_dlcs_set
            cat_tracks = []
            active_count = 0

            for t_id in cat_info["tracks"]:
                filename = f"{t_id}.json"
                cfg = file_configs.get(filename, {})
                track_code = cfg.get("track", t_id)
                disp_name = TRACK_NAME_MAP.get(track_code, track_code)
                is_disabled = filename in disabled_tracks_set
                in_rot = is_dlc_active and not is_disabled
                if in_rot:
                    active_count += 1

                t_obj = {
                    "id": t_id,
                    "filename": filename,
                    "track_name": track_code,
                    "track_code": track_code,
                    "display_name": disp_name,
                    "dlc_id": cat_id,
                    "dlc_name": cat_info["name"],
                    "in_rotation": in_rot,
                    "is_disabled": is_disabled,
                    "is_current": (filename == current_track),
                    "ambient_temp": cfg.get("ambientTemp", 22),
                    "cloud_level": cfg.get("cloudLevel", 0.1),
                    "rain": cfg.get("rain", 0.0),
                    "session_over_time_seconds": cfg.get("sessionOverTimeSeconds", 120),
                    "sessions": cfg.get("sessions", [])
                }
                cat_tracks.append(t_obj)
                all_tracks_flat.append(t_obj)

            categories_data.append({
                "id": cat_id,
                "name": cat_info["name"],
                "description": cat_info["description"],
                "is_active": is_dlc_active,
                "total_tracks": len(cat_tracks),
                "active_tracks_count": active_count,
                "tracks": cat_tracks
            })

        self.send_json({
            "categories": categories_data,
            "tracks": all_tracks_flat,
            "active_dlcs": list(active_dlcs_set),
            "disabled_tracks": list(disabled_tracks_set),
            "rotation_pool": current_active_rotation,
            "current_track_file": current_track,
            "total_tracks_count": len(all_tracks_flat),
            "active_rotation_count": len(current_active_rotation)
        })

    def handle_api_get_config(self):
        settings = read_json_safe(os.path.join(CFG_DIR, "settings.json"), {})
        configuration = read_json_safe(os.path.join(CFG_DIR, "configuration.json"), {})
        event = read_json_safe(os.path.join(CFG_DIR, "event.json"), {})
        assist = read_json_safe(os.path.join(CFG_DIR, "assistRules.json"), {})
        self.send_json({
            "settings": settings,
            "configuration": configuration,
            "event": event,
            "assistRules": assist
        })

    def handle_api_save_config(self, post_data):
        try:
            validated = validate_config_payload(post_data)
            with config_lock:
                if "settings" in validated:
                    write_json_utf16(os.path.join(CFG_DIR, "settings.json"), validated["settings"])
                if "configuration" in validated:
                    write_json_utf16(os.path.join(CFG_DIR, "configuration.json"), validated["configuration"])
                if "assistRules" in validated:
                    write_json_utf16(os.path.join(CFG_DIR, "assistRules.json"), validated["assistRules"])
                if "event" in validated:
                    event = validated["event"]
                    track_file = f"{event['track']}.json"
                    # El editor cambia la plantilla de la pista actual y el evento activo: no se perderá al reiniciar.
                    write_json_utf8(os.path.join(POOLS_DIR, track_file), event)
                    write_json_utf8(os.path.join(CFG_DIR, "event.json"), event)
                    sync_state_from_event()

            self.send_json({"success": True, "message": "Configuración validada y guardada. Los cambios de evento se aplican en el próximo reinicio."})
        except ValidationError as error:
            self.send_json({"success": False, "message": str(error)}, 400)
        except OSError:
            self.send_json({"success": False, "message": "No se pudo guardar la configuración."}, 500)

    def handle_api_telemetry(self):
        results = []
        best_laps_by_track = {}
        drivers_registry = {}

        if os.path.exists(RESULTS_DIR):
            file_list = sorted(os.listdir(RESULTS_DIR), reverse=True)
            for f in file_list[:25]:  # Procesar los últimos 25 archivos
                if not (f.endswith("_R.json") or f.endswith("_R") or f.endswith("_Q.json") or f.endswith("_FP.json")):
                    continue
                full_p = os.path.join(RESULTS_DIR, f)
                try:
                    if os.path.getsize(full_p) > MAX_RESULT_FILE_BYTES:
                        continue
                except OSError:
                    continue
                data = read_json_safe(full_p)
                if not data:
                    continue

                session_type = data.get("sessionType", "Unknown")
                track_name = data.get("trackName", "Desconocido")
                sr = data.get("sessionResult", {})
                leaderboard = sr.get("leaderBoardLines", [])

                clean_leaderboard = []
                for idx, line in enumerate(leaderboard[:10]):
                    driver = line.get("currentDriver", {})
                    first_n = driver.get("firstName", "")
                    last_n = driver.get("lastName", "")
                    driver_name = f"{first_n} {last_n}".strip() or "Piloto Desconocido"
                    car = line.get("car", {})
                    timing = line.get("timing", {})
                    best_lap_ms = timing.get("bestLap", 0)
                    lap_count = timing.get("lapCount", 0)
                    car_num = car.get("raceNumber", 0)
                    car_model = car.get("carModel", 0)

                    # Registrar récords de vuelta por pista
                    if best_lap_ms and best_lap_ms < 2147483647:
                        if track_name not in best_laps_by_track or best_lap_ms < best_laps_by_track[track_name]["time_ms"]:
                            best_laps_by_track[track_name] = {
                                "driver": driver_name,
                                "time_ms": best_lap_ms,
                                "car_num": car_num,
                                "session_file": f
                            }

                    # Contabilizar estadísticas de pilotos
                    if driver_name not in drivers_registry:
                        drivers_registry[driver_name] = {"races": 0, "wins": 0, "podiums": 0, "total_laps": 0}
                    if session_type == "R":
                        drivers_registry[driver_name]["races"] += 1
                        drivers_registry[driver_name]["total_laps"] += lap_count
                        if idx == 0 and lap_count > 0:
                            drivers_registry[driver_name]["wins"] += 1
                        if idx < 3 and lap_count > 0:
                            drivers_registry[driver_name]["podiums"] += 1

                    clean_leaderboard.append({
                        "pos": idx + 1,
                        "driver": driver_name,
                        "car_num": car_num,
                        "car_model": car_model,
                        "best_lap_ms": best_lap_ms,
                        "lap_count": lap_count
                    })

                results.append({
                    "filename": f,
                    "session_type": session_type,
                    "track_name": track_name,
                    "server_name": data.get("serverName", ""),
                    "leaderboard": clean_leaderboard,
                    "total_drivers": len(leaderboard)
                })

        self.send_json({
            "recent_sessions": results,
            "track_records": best_laps_by_track,
            "drivers": drivers_registry
        })

    def handle_api_logs(self, query):
        lines_count = 100
        try:
            if "lines" in query:
                lines_count = int(query["lines"][0])
        except Exception:
            lines_count = 100
        lines_count = max(1, min(lines_count, MAX_LOG_LINES))

        logs = []
        if os.path.exists(LOG_FILE):
            try:
                with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                    logs = list(deque(f, maxlen=lines_count))
            except OSError:
                logs = ["No fue posible leer server.log."]
        else:
            logs = ["El archivo server.log aún no se ha generado."]

        self.send_json({"logs": logs})

    # --- Servir Archivos Estáticos del Frontend ---
    def handle_static_files(self, path):
        if path in ["/", ""]:
            path = "/index.html"
        
        file_path = safe_web_file_path(path)

        if not file_path or not os.path.exists(file_path) or os.path.isdir(file_path):
            self.send_error(404, "Archivo no encontrado")
            return

        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = "application/octet-stream"

        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; "
                "frame-ancestors 'none'; form-action 'self'"
            )
            self.end_headers()
            self.wfile.write(content)
        except OSError:
            self.send_error(500, "Error al servir el archivo.")

    def log_message(self, format, *args):
        # Silenciar logs ruidosos de HTTP para mantener la consola despejada
        return

# --- 7. Inicialización y Arranque del Servidor ---
def run_server(port=8080, host="127.0.0.1", open_browser=True):
    global PANEL_TOKEN
    if not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("El puerto debe estar entre 1 y 65535.")
    if host not in {"127.0.0.1", "0.0.0.0"}:
        raise ValueError("El host debe ser 127.0.0.1 o 0.0.0.0.")
    elevate_if_needed()

    seed_tracks_pool_if_empty(POOLS_DIR)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    os.makedirs(POOLS_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(WEB_DIR, exist_ok=True)
    os.makedirs(ADMIN_PANEL_DIR, exist_ok=True)
    PANEL_TOKEN = load_or_create_panel_token()
    sync_state_from_event()

    # Iniciar hilo de auto-rotación en segundo plano
    rot_thread = threading.Thread(target=rotation_worker, daemon=True)
    rot_thread.start()

    server_address = (host, port)
    httpd = ThreadingHTTPServer(server_address, AdminPanelHandler)
    httpd.daemon_threads = True
    access_url = f"http://127.0.0.1:{port}/?token={PANEL_TOKEN}"
    print("=" * 68)
    print(f"[+] ASSETTO CORSA COMPETIZIONE - ADMIN CONTROL PANEL v1.0")
    print(f"[*] Carpeta Servidor ACC : {SERVER_DIR}")
    print(f"[*] Acceso web protegido : {access_url}")
    if host == "0.0.0.0":
        print("[!] Modo LAN activo: el token viaja por HTTP. Usa una red de confianza.")
    print(f"[*] Presiona Ctrl+C en esta consola para detener el panel.")
    print("=" * 68)
    if open_browser:
        webbrowser.open(access_url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] Deteniendo panel de control...")
        httpd.server_close()

if __name__ == "__main__":
    port_arg = 8080
    host_arg = "127.0.0.1"
    open_browser_arg = True
    skip_next = False
    
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if arg in {"--help", "-h"}:
            print("ACC Dedicated Server Admin Panel v1.0")
            print("Uso: ACC_AdminPanel.exe [PUERTO] [OPCIONES]")
            print("\nOpciones:")
            print("  --lan                Permitir conexiones desde cualquier IP local (0.0.0.0)")
            print("  --no-open            No abrir el navegador automáticamente al iniciar")
            print("  --no-uac             Omitir la comprobación/solicitud de elevación UAC")
            print("  --server-dir <ruta>  Especificar manualmente la ruta a la carpeta 'server'")
            print("  --help, -h           Mostrar esta ayuda")
            sys.exit(0)
        elif arg == "--no-uac":
            continue
        elif arg == "--lan":
            host_arg = "0.0.0.0"
        elif arg == "--no-open":
            open_browser_arg = False
        elif arg == "--server-dir":
            skip_next = True
            continue
        elif arg.isdigit():
            port_arg = int(arg)
        else:
            raise SystemExit(f"Argumento no reconocido: {arg}")
    run_server(port_arg, host_arg, open_browser_arg)

