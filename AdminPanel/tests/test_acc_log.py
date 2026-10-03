"""Tests del seguimiento incremental de server.log y del filtro de spam de la consola."""
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import acc_log  # noqa: E402

FIXTURES = os.path.join(HERE, "fixtures")
SPAM_LINE = b"49469: ==ERR: onCarUpdate (1001): timestamp is 5 ms in the future: 49475 (now: 49469 offset: 35463)\r\n"


def fixture_bytes(name):
    with open(os.path.join(FIXTURES, name), "rb") as f:
        return f.read()


class TempLogTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.path = os.path.join(self.tmp, "server.log")

    def write(self, data, mode="wb"):
        with open(self.path, mode) as f:
            f.write(data)


class LiveLogTrackerTests(TempLogTestCase):
    def test_partial_line_waits_for_newline(self):
        tracker = acc_log.LiveLogTracker()
        self.write(b"0: Server starting with version 256\r\n10: New connection request: id 0 Ana S76561190000000001 on car model 34\r\n"
                   b"10: Creating new car connection: carId 1001, carModel 34, raceNum")
        self.assertEqual(tracker.poll(self.path)["players"], [])
        self.write(b"ber #97\r\n", mode="ab")
        players = tracker.poll(self.path)["players"]
        self.assertEqual([(p["car_id"], p["race_number"]) for p in players], [(1001, 97)])

    def test_skip_to_end_ignores_previous_run_until_server_appends(self):
        tracker = acc_log.LiveLogTracker()
        self.write(fixture_bytes("server_connect.log"))
        tracker.skip_to_end(self.path)
        self.assertEqual(tracker.poll(self.path)["players"], [])
        # accServer vuelve a arrancar escribiendo al final del mismo archivo.
        self.write(fixture_bytes("server_connect.log"), mode="ab")
        self.assertEqual(len(tracker.poll(self.path)["players"]), 1)

    def test_skip_to_end_reads_rewritten_log_from_start(self):
        tracker = acc_log.LiveLogTracker()
        self.write(fixture_bytes("server_connect.log") + SPAM_LINE * 100)
        tracker.skip_to_end(self.path)
        self.assertEqual(tracker.poll(self.path)["players"], [])
        # accServer trunca server.log al arrancar: el archivo nuevo es más corto que el offset previo.
        self.write(fixture_bytes("server_connect.log"))
        self.assertEqual(len(tracker.poll(self.path)["players"]), 1)

    def test_handshake_fills_car_for_reused_car(self):
        state = acc_log.LivePlayersState()
        for line in (
            "Creating new car connection: carId 1001, carModel 34, raceNumber #97",
            "New connection request: id 2 Ana S76561190000000001 on car model 34",
            "Sent handshake response for car 1001 connection 2 with 1286 bytes",
        ):
            state.feed(line)
        self.assertEqual([(p["conn_id"], p["car_id"], p["race_number"]) for p in state.players()], [(2, 1001, 97)])

    def test_rejected_request_without_car_is_not_listed(self):
        state = acc_log.LivePlayersState()
        state.feed("New connection request: id 4 Ana S76561190000000001 on car model 34")
        self.assertEqual(state.players(), [])

    def test_spam_lines_are_detected(self):
        self.assertTrue(acc_log.is_spam_line(SPAM_LINE.decode()))
        self.assertTrue(acc_log.is_spam_line("==ERR: onCarUpdate (1001): timestamp is 12 ms in the future: 1 (now: 0 offset: 0)"))
        self.assertFalse(acc_log.is_spam_line("51805: ==ERR: TCP socket error detected 10053"))


class TailLogLinesTests(TempLogTestCase):
    def test_hides_spam_before_applying_line_limit(self):
        self.write(fixture_bytes("server_connect.log") + SPAM_LINE * 20000 + fixture_bytes("server_disconnect.log"))
        lines, hidden = acc_log.tail_log_lines(self.path, 40, hide_spam=True)
        self.assertEqual(len(lines), 40)
        self.assertFalse(any("onCarUpdate" in line for line in lines))
        self.assertGreater(hidden, 20000)
        self.assertIn("Sent handshake response for car 1001", "".join(lines))
        self.assertTrue(lines[-1].startswith("60407: Udp message count"))

    def test_without_filter_returns_raw_tail(self):
        self.write(fixture_bytes("server_connect.log") + SPAM_LINE * 50)
        lines, hidden = acc_log.tail_log_lines(self.path, 10)
        self.assertEqual(hidden, 0)
        self.assertEqual(len(lines), 10)
        self.assertTrue(all("onCarUpdate" in line and line.endswith("\n") and "\r" not in line for line in lines))

    def test_short_file_returns_all_lines(self):
        self.write(b"0: Server starting with version 256\r\n0: Event changed\r\n")
        lines, _ = acc_log.tail_log_lines(self.path, 100, hide_spam=True)
        self.assertEqual(lines, ["0: Server starting with version 256\n", "0: Event changed\n"])


if __name__ == "__main__":
    unittest.main()
