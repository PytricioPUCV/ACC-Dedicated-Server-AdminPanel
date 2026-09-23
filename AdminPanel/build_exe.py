import os
import shutil
import subprocess
import sys
import zipfile

def main():
    print("=" * 68)
    print("  ASSETTO CORSA COMPETIZIONE - GENERADOR DE EJECUTABLE RELEASE 1.0")
    print("=" * 68)

    admin_panel_dir = os.path.dirname(os.path.abspath(__file__))
    server_dir = os.path.dirname(admin_panel_dir)
    web_dir = os.path.join(admin_panel_dir, "web")
    tracks_pool_dir = os.path.join(server_dir, "tracks_pool")
    dist_dir = os.path.join(admin_panel_dir, "dist")
    build_dir = os.path.join(admin_panel_dir, "build")
    release_dir = os.path.join(server_dir, "release")

    # 1. Comprobar / instalar PyInstaller
    try:
        import PyInstaller
        print("[+] PyInstaller ya se encuentra instalado.")
    except ImportError:
        print("[*] Instalando PyInstaller mediante pip...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # 2. Verificar existencia de recursos esenciales
    if not os.path.isdir(web_dir):
        raise SystemExit(f"[!] Error: No se encontró la carpeta web en {web_dir}")
    if not os.path.isdir(tracks_pool_dir):
        raise SystemExit(f"[!] Error: No se encontró tracks_pool en {tracks_pool_dir}")

    # Separador de add-data en Windows es ';'
    add_web = f"{web_dir};web"
    add_tracks = f"{tracks_pool_dir};tracks_pool"

    pyinstaller_cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name", "ACC_AdminPanel",
        "--uac-admin",
        "--console",
        "--add-data", add_web,
        "--add-data", add_tracks,
        "panel_server.py"
    ]

    print("\n[*] Compilando binario con PyInstaller...")
    print(f"[*] Comando: {' '.join(pyinstaller_cmd)}\n")

    subprocess.check_call(pyinstaller_cmd, cwd=admin_panel_dir)

    built_exe = os.path.join(dist_dir, "ACC_AdminPanel.exe")
    if not os.path.exists(built_exe):
        raise SystemExit("[!] Error: No se generó el ejecutable en dist/ACC_AdminPanel.exe")

    size_mb = os.path.getsize(built_exe) / (1024 * 1024)
    print(f"\n[+] ¡Compilación exitosa!: {built_exe} ({size_mb:.2f} MB)")

    # 3. Copiar a la carpeta raíz del servidor para ejecución inmediata
    target_server_exe = os.path.join(server_dir, "ACC_AdminPanel.exe")
    shutil.copy2(built_exe, target_server_exe)
    print(f"[+] Copiado a la raíz del servidor: {target_server_exe}")

    # 4. Crear carpeta Release 1.0 para distribución en GitHub
    os.makedirs(release_dir, exist_ok=True)
    release_exe = os.path.join(release_dir, "ACC_AdminPanel.exe")
    shutil.copy2(built_exe, release_exe)

    # Copiar tracks_pool al release
    release_tracks_dir = os.path.join(release_dir, "tracks_pool")
    os.makedirs(release_tracks_dir, exist_ok=True)
    for track_file in os.listdir(tracks_pool_dir):
        if track_file.endswith(".json"):
            shutil.copy2(os.path.join(tracks_pool_dir, track_file), os.path.join(release_tracks_dir, track_file))

    # Crear LEEME_INSTALACION.txt
    readme_content = """======================================================================
  ASSETTO CORSA COMPETIZIONE - DEDICATED SERVER ADMIN PANEL v1.0
======================================================================

¡Gracias por descargar el Admin Panel y Rotador Dinámico para ACC!

INSTRUCCIONES DE USO RÁPIDO:
----------------------------
1. Copia el archivo 'ACC_AdminPanel.exe' dentro de la carpeta 'server' de tu
   servidor dedicado de Assetto Corsa Competizione:
   (Por defecto: C:\\Program Files (x86)\\Steam\\steamapps\\common\\Assetto Corsa Competizione Dedicated Server\\server)

2. Haz doble clic en 'ACC_AdminPanel.exe'.
   - Windows te solicitará permisos de Administrador (necesarios para gestionar
     accServer.exe y las configuraciones en Program Files).
   - Se abrirá automáticamente tu navegador web con tu sesión segura activa:
     http://127.0.0.1:8080/?token=...

3. ¡Listo! Ya puedes encender el servidor, rotar circuitos automáticamente,
   modificar slots/asistencias, ver telemetría de carrera y moderar pilotos.

CARACTERÍSTICAS INCLUIDAS:
--------------------------
* Rotación de circuitos 100% automática tras el podio de cada carrera.
* Catálogo oficial de los 25 circuitos de ACC agrupados por DLCs (Base, IGTC, British GT, USA, etc.).
* Telemetría en vivo, mejores vueltas, historial y podios.
* Consola de registros (logs) en tiempo real.
* Editor en caliente de configuraciones (garantiza UTF-16 LE con BOM para evitar errores de ACC).
* Cero dependencias externas requeridas (Python viene incrustado en el .exe).

Desarrollado con pasión para la comunidad de simracing.
"""
    readme_path = os.path.join(release_dir, "LEEME_INSTALACION.txt")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme_content)

    # 5. Generar archivo comprimido ZIP para subir a GitHub Releases
    zip_path = os.path.join(release_dir, "ACC_Server_AdminPanel_v1.0.zip")
    print(f"[*] Creando archivo comprimido para GitHub Release: {zip_path}...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(release_exe, arcname="ACC_AdminPanel.exe")
        zf.write(readme_path, arcname="LEEME_INSTALACION.txt")
        for track_file in os.listdir(tracks_pool_dir):
            if track_file.endswith(".json"):
                zf.write(
                    os.path.join(tracks_pool_dir, track_file),
                    arcname=os.path.join("tracks_pool", track_file)
                )

    zip_size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print("\n" + "=" * 68)
    print("  ¡RELEASE 1.0 EMPAQUETADO CON ÉXITO!")
    print(f"  Ejecutable standalone : {release_exe}")
    print(f"  Paquete ZIP de Release: {zip_path} ({zip_size_mb:.2f} MB)")
    print("=" * 68)

if __name__ == "__main__":
    main()
