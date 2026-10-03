"""Lanza un proceso dentro de una pseudoconsola de Windows (ConPTY) y entrega su salida línea a línea.

accServer.exe usa buffer completo del runtime de C cuando su salida no es una consola: tanto
log/server.log como un pipe reciben las líneas en bloques de varios KB, con minutos de retraso
cuando el servidor está tranquilo (p. ej. la desconexión del último piloto). Dentro de una
pseudoconsola el proceso cree escribir en una terminal y vuelca cada línea al instante.

Requiere Windows 10 1809+; si no está disponible, start() lanza OSError y el panel usa server.log.
"""
import ctypes
import re
import subprocess
import sys
import threading
from ctypes import wintypes as wt

EXTENDED_STARTUPINFO_PRESENT = 0x00080000
STARTF_USESTDHANDLES = 0x00000100
PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE = 0x00020016
INFINITE = 0xFFFFFFFF

# Posicionamiento de cursor (CUP): ConPTY lo usa a veces en lugar de un salto de línea.
CURSOR_POSITION_RE = re.compile(r"\x1b\[\d*(?:;\d*)?H")
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[=>()][0-9A-Za-z]?")


def split_console_output(pending, chunk):
    """Convierte el flujo VT de ConPTY en líneas de texto. Devuelve (líneas completas, resto pendiente)."""
    text = pending + ANSI_ESCAPE_RE.sub("", CURSOR_POSITION_RE.sub("\n", chunk))
    parts = re.split(r"\r?\n", text)
    rest = parts.pop()
    lines = [part.replace("\r", "").rstrip() for part in parts]
    return [line for line in lines if line.strip()], rest


def is_supported():
    return sys.platform == "win32" and hasattr(ctypes, "WinDLL") and hasattr(_kernel32(), "CreatePseudoConsole")


def _kernel32():
    return ctypes.WinDLL("kernel32", use_last_error=True)


class _COORD(ctypes.Structure):
    _fields_ = [("X", wt.SHORT), ("Y", wt.SHORT)]


class _STARTUPINFOW(ctypes.Structure):
    _fields_ = [("cb", wt.DWORD), ("lpReserved", wt.LPWSTR), ("lpDesktop", wt.LPWSTR), ("lpTitle", wt.LPWSTR),
                ("dwX", wt.DWORD), ("dwY", wt.DWORD), ("dwXSize", wt.DWORD), ("dwYSize", wt.DWORD),
                ("dwXCountChars", wt.DWORD), ("dwYCountChars", wt.DWORD), ("dwFillAttribute", wt.DWORD),
                ("dwFlags", wt.DWORD), ("wShowWindow", wt.WORD), ("cbReserved2", wt.WORD),
                ("lpReserved2", ctypes.c_void_p), ("hStdInput", wt.HANDLE), ("hStdOutput", wt.HANDLE),
                ("hStdError", wt.HANDLE)]


class _STARTUPINFOEXW(ctypes.Structure):
    _fields_ = [("StartupInfo", _STARTUPINFOW), ("lpAttributeList", ctypes.c_void_p)]


class _PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [("hProcess", wt.HANDLE), ("hThread", wt.HANDLE), ("dwProcessId", wt.DWORD), ("dwThreadId", wt.DWORD)]


def _bind(k32):
    k32.CreatePseudoConsole.argtypes = [_COORD, wt.HANDLE, wt.HANDLE, wt.DWORD, ctypes.POINTER(wt.HANDLE)]
    k32.CreatePseudoConsole.restype = ctypes.c_long
    k32.ClosePseudoConsole.argtypes = [wt.HANDLE]
    k32.ClosePseudoConsole.restype = None
    k32.CreatePipe.argtypes = [ctypes.POINTER(wt.HANDLE), ctypes.POINTER(wt.HANDLE), ctypes.c_void_p, wt.DWORD]
    k32.InitializeProcThreadAttributeList.argtypes = [ctypes.c_void_p, wt.DWORD, wt.DWORD, ctypes.POINTER(ctypes.c_size_t)]
    k32.UpdateProcThreadAttribute.argtypes = [ctypes.c_void_p, wt.DWORD, ctypes.c_size_t, ctypes.c_void_p,
                                              ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p]
    k32.DeleteProcThreadAttributeList.argtypes = [ctypes.c_void_p]
    k32.CreateProcessW.argtypes = [wt.LPCWSTR, wt.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, wt.BOOL, wt.DWORD,
                                   ctypes.c_void_p, wt.LPCWSTR, ctypes.POINTER(_STARTUPINFOW),
                                   ctypes.POINTER(_PROCESS_INFORMATION)]
    k32.ReadFile.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD), ctypes.c_void_p]
    k32.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
    k32.CloseHandle.argtypes = [wt.HANDLE]
    return k32


class ConPtyProcess:
    """Proceso hijo en una pseudoconsola. on_line(texto) se llama desde un hilo por cada línea."""

    def __init__(self, exe_path, cwd, on_line, on_exit=None, args=(), width=512, height=60):
        self.exe_path = exe_path
        self.args = list(args)
        self.cwd = cwd
        self.on_line = on_line
        self.on_exit = on_exit
        self.size = _COORD(width, height)
        self.pid = None
        self._k32 = None

    def start(self):
        if not is_supported():
            raise OSError("ConPTY no está disponible en este sistema.")
        k32 = self._k32 = _bind(_kernel32())
        in_read, in_write, out_read, out_write = wt.HANDLE(), wt.HANDLE(), wt.HANDLE(), wt.HANDLE()
        if not k32.CreatePipe(ctypes.byref(in_read), ctypes.byref(in_write), None, 0):
            raise ctypes.WinError(ctypes.get_last_error())
        if not k32.CreatePipe(ctypes.byref(out_read), ctypes.byref(out_write), None, 0):
            raise ctypes.WinError(ctypes.get_last_error())

        hpc = wt.HANDLE()
        result = k32.CreatePseudoConsole(self.size, in_read, out_write, 0, ctypes.byref(hpc))
        # La pseudoconsola duplica estos extremos; cerrarlos permite detectar el fin del flujo.
        k32.CloseHandle(in_read)
        k32.CloseHandle(out_write)
        if result != 0:
            k32.CloseHandle(in_write)
            k32.CloseHandle(out_read)
            raise OSError(f"CreatePseudoConsole falló (HRESULT {result & 0xFFFFFFFF:#010x}).")

        size = ctypes.c_size_t()
        k32.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
        attributes = ctypes.create_string_buffer(size.value)
        try:
            if not k32.InitializeProcThreadAttributeList(attributes, 1, 0, ctypes.byref(size)):
                raise ctypes.WinError(ctypes.get_last_error())
            if not k32.UpdateProcThreadAttribute(attributes, 0, PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE, hpc,
                                                 ctypes.sizeof(wt.HANDLE), None, None):
                raise ctypes.WinError(ctypes.get_last_error())

            startup = _STARTUPINFOEXW()
            startup.StartupInfo.cb = ctypes.sizeof(_STARTUPINFOEXW)
            # Handles estándar nulos: obliga al hijo a usar la pseudoconsola aunque el panel tenga stdout redirigido.
            startup.StartupInfo.dwFlags = STARTF_USESTDHANDLES
            startup.lpAttributeList = ctypes.cast(attributes, ctypes.c_void_p)
            info = _PROCESS_INFORMATION()
            command = ctypes.create_unicode_buffer(subprocess.list2cmdline([self.exe_path, *self.args]))
            if not k32.CreateProcessW(None, command, None, None, False, EXTENDED_STARTUPINFO_PRESENT, None,
                                      self.cwd, ctypes.byref(startup.StartupInfo), ctypes.byref(info)):
                raise ctypes.WinError(ctypes.get_last_error())
        except OSError:
            k32.ClosePseudoConsole(hpc)
            k32.CloseHandle(in_write)
            k32.CloseHandle(out_read)
            raise
        finally:
            k32.DeleteProcThreadAttributeList(attributes)

        k32.CloseHandle(info.hThread)
        self.pid = info.dwProcessId
        threading.Thread(target=self._read_output, args=(out_read,), daemon=True, name="accServer-conpty-reader").start()
        threading.Thread(target=self._wait_exit, args=(info.hProcess, hpc, in_write), daemon=True,
                         name="accServer-conpty-waiter").start()
        return self.pid

    def _read_output(self, out_read):
        k32 = self._k32
        buffer = ctypes.create_string_buffer(65536)
        read = wt.DWORD()
        pending = ""
        decoder_rest = b""
        try:
            while k32.ReadFile(out_read, buffer, len(buffer), ctypes.byref(read), None) and read.value:
                data = decoder_rest + buffer.raw[:read.value]
                try:
                    chunk = data.decode("utf-8")
                    decoder_rest = b""
                except UnicodeDecodeError as error:
                    # Un carácter multibyte puede quedar partido entre dos lecturas.
                    if error.start >= len(data) - 3:
                        chunk, decoder_rest = data[:error.start].decode("utf-8", "replace"), data[error.start:]
                    else:
                        chunk, decoder_rest = data.decode("utf-8", "replace"), b""
                lines, pending = split_console_output(pending, chunk)
                for line in lines:
                    try:
                        self.on_line(line)
                    except Exception as error:  # Un fallo del consumidor no debe cortar la lectura.
                        print(f"[!] Error procesando salida de accServer: {error}")
        finally:
            k32.CloseHandle(out_read)

    def _wait_exit(self, process_handle, hpc, in_write):
        k32 = self._k32
        k32.WaitForSingleObject(process_handle, INFINITE)
        k32.CloseHandle(process_handle)
        # Cerrar la pseudoconsola termina el flujo de salida y libera el hilo lector.
        k32.ClosePseudoConsole(hpc)
        k32.CloseHandle(in_write)
        if self.on_exit:
            self.on_exit()
