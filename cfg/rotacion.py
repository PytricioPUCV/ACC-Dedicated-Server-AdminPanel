import ctypes
import os
import shutil
import subprocess
import sys
import time

# --- 1. Elevación UAC ---
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

if not is_admin():
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(f'"{arg}"' for arg in sys.argv), None, 1
    )
    sys.exit()

# --- 2. Rutas ---
SERVER_DIR = r"C:\Program Files (x86)\Steam\steamapps\common\Assetto Corsa Competizione Dedicated Server\server"
CFG_DIR = os.path.join(SERVER_DIR, "cfg")
RESULTS_DIR = os.path.join(SERVER_DIR, "results")
POOLS_DIR = os.path.join(SERVER_DIR, "tracks_pool")
EXE_PATH = os.path.join(SERVER_DIR, "accServer.exe")

TRACK_ROTATION = [
    "valencia.json",
    "spa.json",
    "monza.json",
    "nurburgring.json",
    "silverstone.json"
]
current_track_idx = 0

def kill_acc_server():
    """Mata de forma forzada cualquier instancia de accServer en Windows"""
    print("[*] Forzando cierre completo de accServer.exe...")
    subprocess.run(["taskkill", "/F", "/IM", "accServer.exe", "/T"], 
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)  # Pausa para que Windows libere los puertos 9231/9232

def start_server():
    track_file = TRACK_ROTATION[current_track_idx]
    src_event = os.path.join(POOLS_DIR, track_file)
    dst_event = os.path.join(CFG_DIR, "event.json")

    if not os.path.exists(src_event):
        print(f"[!] ERROR: No existe la plantilla {src_event}")
        return None

    # Reemplazar event.json
    shutil.copyfile(src_event, dst_event)
    
    print("\n" + "=" * 55)
    print(f"[+] Pista activada para esta ronda: {track_file}")
    print(f"[+] Iniciando accServer.exe...")
    print("=" * 55 + "\n")

    return subprocess.Popen([EXE_PATH], cwd=SERVER_DIR)

def get_latest_race_result():
    if not os.path.exists(RESULTS_DIR):
        return None, 0

    race_files = []
    for f in os.listdir(RESULTS_DIR):
        if f.endswith("_R") or f.endswith("_R.json"):
            full_path = os.path.join(RESULTS_DIR, f)
            race_files.append((full_path, os.path.getmtime(full_path)))

    if not race_files:
        return None, 0

    latest_file, mtime = max(race_files, key=lambda x: x[1])
    return latest_file, mtime

def main():
    global current_track_idx

    os.makedirs(RESULTS_DIR, exist_ok=True)
    os.makedirs(POOLS_DIR, exist_ok=True)

    # Asegurar que no haya instancias colgadas antes de empezar
    kill_acc_server()

    _, last_race_mtime = get_latest_race_result()

    process = start_server()
    if not process:
        return

    print("[*] Monitor activo. Esperando finalización de carreras...")

    try:
        while True:
            time.sleep(3)
            latest_file, mtime = get_latest_race_result()

            if latest_file and mtime > last_race_mtime:
                last_race_mtime = mtime
                print(f"\n[🏁] ¡Carrera terminada!: {os.path.basename(latest_file)}")
                print("[*] Pausa de 12 segundos antes del reinicio...")
                time.sleep(12)

                # Forzar muerte del proceso
                kill_acc_server()

                # Siguiente circuito en la lista
                current_track_idx = (current_track_idx + 1) % len(TRACK_ROTATION)
                process = start_server()

    except KeyboardInterrupt:
        print("\n[!] Deteniendo script por teclado...")
        kill_acc_server()

if __name__ == "__main__":
    main()