"""Tests del flujo en vivo de accServer: pseudoconsola (ConPTY), modo stream del tracker y lag UDP."""
import os
import sys
import threading
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import acc_log  # noqa: E402
import conpty  # noqa: E402
import panel_server  # noqa: E402

FIXTURES = os.path.join(HERE, "fixtures")


def console_lines(name):
    """Líneas de una fixture tal como salen por consola (sin el prefijo "<ms>: ")."""
    with open(os.path.join(FIXTURES, name), "rb") as f:
        return [acc_log.strip_timestamp(acc_log.decode_log_line(raw)) for raw in f.read().split(b"\n")]


class SplitConsoleOutputTests(unittest.TestCase):
    def test_crlf_lines_and_pending_rest(self):
        lines, rest = conpty.split_console_output("", "1 client(s) online\r\nNew connection req")
        self.assertEqual((lines, rest), (["1 client(s) online"], "New connection req"))
        lines, rest = conpty.split_console_output(rest, "uest: id 0 Ana S7656 on car model 34\r\n")
        self.assertEqual(lines, ["New connection request: id 0 Ana S7656 on car model 34"])

    def test_cursor_position_acts_as_line_break(self):
        # ConPTY sustituyó una línea vacía por un salto de cursor y pegaba dos mensajes.
        chunk = "Translated realtime interval hzToMiliseconds(18)=54\x1b[5;1HSessionManager::randomize\r\n"
        lines, _ = conpty.split_console_output("", chunk)
        self.assertEqual(lines, ["Translated realtime interval hzToMiliseconds(18)=54", "SessionManager::randomize"])

    def test_escape_sequences_and_blank_lines_are_removed(self):
        chunk = "\x1b[?25l\x1b[2J\x1b[m\x1b]0;accServer.exe\x07Server starting with version 256\x1b[K\r\n\r\n   \r\n"
        lines, rest = conpty.split_console_output("", chunk)
        self.assertEqual((lines, rest), (["Server starting with version 256"], ""))


class TrackerStreamModeTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000.0
        self.tracker = acc_log.LiveLogTracker(clock=lambda: self.now)

    def feed(self, generation, lines):
        for line in lines:
            self.tracker.feed_line(generation, line)

    def test_real_console_session_connect_and_disconnect(self):
        generation = self.tracker.start_stream()
        self.feed(generation, console_lines("server_connect.log"))
        players = self.tracker.poll("no-se-usa-en-modo-stream.log")["players"]
        self.assertEqual([(p["driver_name"], p["car_id"], p["race_number"]) for p in players],
                         [("Piloto Prueba", 1001, 97)])
        self.feed(generation, console_lines("server_disconnect.log"))
        self.assertEqual(self.tracker.poll("x.log")["players"], [])

    def test_stream_ignores_buffered_server_log(self):
        generation = self.tracker.start_stream()
        self.feed(generation, console_lines("server_connect.log"))
        # Aunque server.log no exista o esté atrasado, manda el flujo en vivo.
        self.assertEqual(len(self.tracker.poll(os.path.join(HERE, "no-existe.log"))["players"]), 1)

    def test_lines_from_previous_process_are_ignored(self):
        old = self.tracker.start_stream()
        new = self.tracker.start_stream()
        self.feed(old, console_lines("server_connect.log"))
        self.assertEqual(self.tracker.poll("x.log")["players"], [])
        self.feed(new, console_lines("server_connect.log"))
        self.assertEqual(len(self.tracker.poll("x.log")["players"]), 1)

    def test_end_stream_clears_players_and_returns_to_file_mode(self):
        generation = self.tracker.start_stream()
        self.feed(generation, console_lines("server_connect.log"))
        self.tracker.end_stream(generation)
        self.assertFalse(self.tracker.streaming)
        self.assertIsNone(self.tracker.stream_lines())
        self.assertEqual(self.tracker.poll(os.path.join(HERE, "no-existe.log"))["players"], [])

    def test_stream_history_for_console_tab(self):
        generation = self.tracker.start_stream()
        self.feed(generation, console_lines("server_connect.log"))
        lines, hidden = acc_log.filter_recent_lines(self.tracker.stream_lines(), 5, hide_spam=True)
        self.assertEqual(len(lines), 5)
        self.assertGreater(hidden, 10)
        self.assertFalse(any("onCarUpdate" in line for line in lines))
        self.assertTrue(all(line.endswith("\n") for line in lines))

    def test_late_udp_warning_reports_lag_until_it_expires(self):
        generation = self.tracker.start_stream()
        self.feed(generation, console_lines("server_connect.log"))
        self.feed(generation, ["Late lastUdpPaketReceived for connId 0: 2479 ms (Piloto Prueba)",
                               "Late lastUdpPaketReceived for connId 0: 3491 ms (Piloto Prueba)"])
        self.assertEqual(self.tracker.poll("x.log")["players"][0]["lag_ms"], 3491)
        self.now += acc_log.LAG_WINDOW_SECONDS + 1
        self.assertIsNone(self.tracker.poll("x.log")["players"][0]["lag_ms"])
        self.assertNotIn("_lag_at", self.tracker.poll("x.log")["players"][0])


@unittest.skipUnless(conpty.is_supported(), "ConPTY sólo existe en Windows 10 1809+")
class ConPtyProcessTests(unittest.TestCase):
    def test_lines_arrive_while_process_is_still_running(self):
        received = []
        exited = threading.Event()
        script = "import time; print('linea uno', flush=False); time.sleep(1.5); print('linea dos')"
        process = conpty.ConPtyProcess(sys.executable, HERE, lambda line: received.append((time.monotonic(), line)),
                                       on_exit=exited.set, args=["-c", script])
        started = time.monotonic()
        self.assertGreater(process.start(), 0)
        self.assertTrue(exited.wait(15))
        deadline = time.monotonic() + 5
        while len(received) < 2 and time.monotonic() < deadline:
            time.sleep(0.05)
        texts = [line for _, line in received]
        self.assertIn("linea uno", texts)
        self.assertIn("linea dos", texts)
        # La primera línea llega antes de que termine la pausa: no hay buffer de bloque como en un pipe.
        first_at = next(t for t, line in received if line == "linea uno")
        self.assertLess(first_at - started, 1.4)


class PanelLaunchTests(unittest.TestCase):
    def setUp(self):
        saved = panel_server.LIVE_LOG
        panel_server.LIVE_LOG = acc_log.LiveLogTracker()
        self.addCleanup(setattr, panel_server, "LIVE_LOG", saved)

    def test_falls_back_to_server_log_without_conpty(self):
        fake = mock.Mock(pid=4321)
        with mock.patch.object(panel_server.conpty.ConPtyProcess, "start", side_effect=OSError("sin ConPTY")), \
                mock.patch.object(panel_server.subprocess, "Popen", return_value=fake) as popen, \
                mock.patch("builtins.print"):
            self.assertEqual(panel_server.launch_acc_process(), 4321)
        popen.assert_called_once()
        self.assertFalse(panel_server.LIVE_LOG.streaming)

    def test_conpty_launch_streams_lines_to_tracker(self):
        captured = {}

        def fake_init(instance, exe_path, cwd, on_line, on_exit=None, **kwargs):
            captured["on_line"] = on_line
            captured["on_exit"] = on_exit

        with mock.patch.object(panel_server.conpty.ConPtyProcess, "__init__", fake_init), \
                mock.patch.object(panel_server.conpty.ConPtyProcess, "start", return_value=9876), \
                mock.patch("builtins.print"):
            self.assertEqual(panel_server.launch_acc_process(), 9876)
            for line in console_lines("server_connect.log"):
                captured["on_line"](line)
        self.assertTrue(panel_server.LIVE_LOG.streaming)
        self.assertEqual(len(panel_server.LIVE_LOG.poll("x.log")["players"]), 1)
        captured["on_exit"]()
        self.assertFalse(panel_server.LIVE_LOG.streaming)

    def test_echo_skips_spam(self):
        with mock.patch("builtins.print") as printed:
            panel_server.echo_server_line("==ERR: onCarUpdate (1001): timestamp is 5 ms in the future: 1 (now: 0 offset: 0)")
            panel_server.echo_server_line("1 client(s) online")
        printed.assert_called_once_with("1 client(s) online", flush=True)


if __name__ == "__main__":
    unittest.main()
