"""Lectura de server.log de accServer.exe: pilotos conectados en vivo y filtro de spam.

accServer escribe log/server.log con líneas "<ms>: <mensaje>" (CRLF); la consola muestra el
mismo mensaje sin el prefijo. Formato real de una conexión y su desconexión:

    New connection request: id 0 Nombre Apellido S7656... on car model 34
    Creating new car connection: carId 1001, carModel 34, raceNumber #97
    Sent handshake response for car 1001 connection 0 with 1286 bytes
    Client 0 closed the connection (10053)
    Removing dead connection 0  (last lastUdpPaketReceived 2017)
    car 1001 has no driving connection anymore, will remove it
    0 client(s) online

El log no informa ping. El seguimiento es incremental (offset en bytes) para que el spam
de "onCarUpdate ... in the future" no desplace las líneas de conexión fuera de la ventana.
"""
import os
import re
import threading

TIMESTAMP_PREFIX_RE = re.compile(r"^\d+:\s?")
SERVER_START_RE = re.compile(r"^Server starting with version\b")
CONNECTION_REQUEST_RE = re.compile(r"^New connection request: id (\d+) (.*?)\s*(\S+) on car model (-?\d+)")
CAR_CREATED_RE = re.compile(r"^Creating new car connection: carId (\d+), carModel (-?\d+), raceNumber #(-?\d+)")
HANDSHAKE_RE = re.compile(r"^Sent handshake response for car (\d+) connection (\d+)")
CLIENT_CLOSED_RE = re.compile(r"^Client (\d+) closed the connection")
DEAD_CONNECTION_RE = re.compile(r"^Removing dead connection (\d+)")
CAR_REMOVED_RE = re.compile(r"^car (\d+) has no driving connection anymore")
CLIENTS_ONLINE_RE = re.compile(r"^(\d+) client\(s\) online")
ALIVE_CONNECTIONS_RE = re.compile(r"^Alive connections: (\d+)")
SESSION_CHANGED_RE = re.compile(r"^Session changed: .*? -> (.+?)\s*$")
SESSION_PHASE_RE = re.compile(r"^Detected sessionPhase <.*?> -> <(.+?)> \((.+?)\)")
CAR_UPDATE_SPAM_RE = re.compile(r"==ERR: onCarUpdate \(\d+\): timestamp is -?\d+ ms in the future")
CAR_UPDATE_SPAM_BYTES_RE = re.compile(CAR_UPDATE_SPAM_RE.pattern.encode("ascii"))

READ_CHUNK_BYTES = 1 << 20
TAIL_BLOCK_BYTES = 64 * 1024


def decode_log_line(raw):
    """accServer no declara codificación: se intenta UTF-8 y se cae a cp1252 (Windows)."""
    raw = raw.rstrip(b"\r\n")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def strip_timestamp(line):
    return TIMESTAMP_PREFIX_RE.sub("", line, count=1).strip()


def is_spam_line(line):
    return bool(CAR_UPDATE_SPAM_RE.search(line))


class LivePlayersState:
    """Máquina de estados de conexiones a partir de mensajes del log (sin prefijo de tiempo)."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.connections = {}
        self.cars = {}
        self.pending_conn_id = None
        self.clients_online = None
        self.session = {"name": None, "phase": None}

    def clear_connections(self):
        self.connections.clear()
        self.cars.clear()
        self.pending_conn_id = None

    def feed(self, line):
        message = strip_timestamp(line)
        if not message or is_spam_line(message):
            return

        if SERVER_START_RE.match(message):
            self.reset()
            return

        match = CONNECTION_REQUEST_RE.match(message)
        if match:
            conn_id = int(match.group(1))
            self.connections[conn_id] = {
                "conn_id": conn_id,
                "player_id": match.group(3),
                "driver_name": match.group(2).strip(),
                "car_model_id": int(match.group(4)),
                "car_id": None,
                "race_number": None,
            }
            self.pending_conn_id = conn_id
            return

        match = CAR_CREATED_RE.match(message)
        if match:
            car_id, car_model, race_number = (int(value) for value in match.groups())
            self.cars[car_id] = {"car_model_id": car_model, "race_number": race_number}
            # La línea no trae connId: corresponde a la última solicitud de conexión.
            if self.pending_conn_id in self.connections:
                self._assign_car(self.pending_conn_id, car_id)
            self.pending_conn_id = None
            return

        match = HANDSHAKE_RE.match(message)
        if match:
            car_id, conn_id = int(match.group(1)), int(match.group(2))
            if conn_id in self.connections:
                self._assign_car(conn_id, car_id)
            return

        match = CLIENT_CLOSED_RE.match(message) or DEAD_CONNECTION_RE.match(message)
        if match:
            self.connections.pop(int(match.group(1)), None)
            return

        match = CAR_REMOVED_RE.match(message)
        if match:
            car_id = int(match.group(1))
            self.cars.pop(car_id, None)
            for conn_id in [c for c, info in self.connections.items() if info["car_id"] == car_id]:
                del self.connections[conn_id]
            return

        match = CLIENTS_ONLINE_RE.match(message)
        if match:
            self.clients_online = int(match.group(1))
            if self.clients_online == 0:
                self.clear_connections()
            return

        match = ALIVE_CONNECTIONS_RE.match(message)
        if match:
            if int(match.group(1)) == 0:
                self.clear_connections()
            return

        match = SESSION_CHANGED_RE.match(message)
        if match:
            # "Practice -> Qualifying 1": el número final es el índice de sesión.
            self.session["name"] = re.sub(r"\s+\d+$", "", match.group(1))
            return

        match = SESSION_PHASE_RE.match(message)
        if match:
            self.session["phase"] = match.group(1)
            self.session["name"] = match.group(2)

    def _assign_car(self, conn_id, car_id):
        conn = self.connections[conn_id]
        conn["car_id"] = car_id
        car = self.cars.get(car_id)
        if car:
            conn["car_model_id"] = car["car_model_id"]
            conn["race_number"] = car["race_number"]

    def players(self):
        """Sólo conexiones con coche asignado: una solicitud rechazada nunca crea coche."""
        return [dict(conn) for _, conn in sorted(self.connections.items()) if conn["car_id"] is not None]


class LiveLogTracker:
    """Sigue server.log por offset; reinicia el estado si el archivo cambia, se trunca o desaparece."""

    def __init__(self):
        self._lock = threading.Lock()
        self._state = LivePlayersState()
        self._path = None
        self._file_id = None
        self._offset = 0
        self._partial = b""

    def reset(self):
        with self._lock:
            self._reset_locked()

    def skip_to_end(self, path):
        """Ignora el contenido actual (ejecución anterior); se leerá lo que accServer escriba después.

        Si accServer trunca o recrea el archivo al arrancar, poll() lo detecta y lee desde el inicio.
        """
        with self._lock:
            self._path = path
            self._reset_locked()
            try:
                stat = os.stat(path)
            except FileNotFoundError:
                return
            self._file_id = (stat.st_dev, stat.st_ino)
            self._offset = stat.st_size

    def _reset_locked(self):
        self._state.reset()
        self._file_id = None
        self._offset = 0
        self._partial = b""

    def poll(self, path):
        with self._lock:
            if path != self._path:
                self._path = path
                self._reset_locked()
            try:
                stat = os.stat(path)
            except FileNotFoundError:
                self._reset_locked()
                return self._snapshot_locked()

            file_id = (stat.st_dev, stat.st_ino)
            if stat.st_size < self._offset or (self._file_id is not None and file_id != self._file_id):
                self._reset_locked()
            self._file_id = file_id

            if stat.st_size > self._offset:
                with open(path, "rb") as f:
                    f.seek(self._offset)
                    while True:
                        chunk = f.read(READ_CHUNK_BYTES)
                        if not chunk:
                            break
                        self._offset += len(chunk)
                        self._consume(chunk)
            return self._snapshot_locked()

    def _consume(self, chunk):
        lines = (self._partial + chunk).split(b"\n")
        self._partial = lines.pop()
        for raw in lines:
            self._state.feed(decode_log_line(raw))

    def _snapshot_locked(self):
        return {
            "players": self._state.players(),
            "clients_online": self._state.clients_online,
            "session": dict(self._state.session),
        }


def tail_log_lines(path, count, hide_spam=False, max_bytes=4 << 20):
    """Últimas `count` líneas (con salto final) leyendo desde el final; filtra el spam antes de limitar."""
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        position = f.tell()
        blocks = []
        found = read = 0
        while position > 0 and found <= count and read < max_bytes:
            step = min(TAIL_BLOCK_BYTES, position)
            position -= step
            f.seek(position)
            block = f.read(step)
            blocks.append(block)
            read += step
            found += block.count(b"\n")
            if hide_spam:
                found -= len(CAR_UPDATE_SPAM_BYTES_RE.findall(block))
    data = b"".join(reversed(blocks))

    raw_lines = data.split(b"\n")
    if position > 0:
        raw_lines = raw_lines[1:]
    if raw_lines and raw_lines[-1] == b"":
        raw_lines.pop()

    lines = []
    hidden = 0
    for raw in raw_lines:
        line = decode_log_line(raw)
        if hide_spam and is_spam_line(line):
            hidden += 1
            continue
        lines.append(line + "\n")
    return lines[-count:], hidden
