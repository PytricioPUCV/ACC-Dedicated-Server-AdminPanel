"""Reproduce y cubre la lista de "Pilotos en vivo" a partir de server.log real de accServer.

Las fixtures son el log real del servidor (CRLF, prefijo "<ms>: ") con nombre, SteamID y sala anonimizados.
"""
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import panel_server  # noqa: E402

FIXTURES = os.path.join(HERE, "fixtures")
PLAYER_ID = "S76561190000000001"
SPAM_LINE = b"49469: ==ERR: onCarUpdate (1001): timestamp is 5 ms in the future: 49475 (now: 49469 offset: 35463)\r\n"


def fixture_bytes(name):
    with open(os.path.join(FIXTURES, name), "rb") as f:
        return f.read()


class LivePlayersTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.log_path = os.path.join(self.tmp, "server.log")
        self.running = True
        for patcher in (
            mock.patch.object(panel_server, "LOG_FILE", self.log_path),
            mock.patch.object(panel_server, "RESULTS_DIR", os.path.join(self.tmp, "results")),
            mock.patch.object(panel_server, "is_acc_running", side_effect=lambda: self.running),
            mock.patch.object(panel_server, "get_banlist", return_value=[]),
            mock.patch.object(panel_server, "get_entrylist", return_value={"entries": []}),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def write_log(self, data):
        with open(self.log_path, "wb") as f:
            f.write(data)

    def append_log(self, data):
        with open(self.log_path, "ab") as f:
            f.write(data)

    def players(self):
        return panel_server.parse_active_players()

    def active(self):
        return self.players()["active_players"]


class ConnectionTests(LivePlayersTestCase):
    def test_connected_player_is_listed_with_car_mapping(self):
        self.write_log(fixture_bytes("server_connect.log"))
        active = self.active()
        self.assertEqual(len(active), 1)
        player = active[0]
        self.assertEqual(player["player_id"], PLAYER_ID)
        self.assertEqual(player["driver_name"], "Piloto Prueba")
        self.assertEqual(player["conn_id"], 0)
        self.assertEqual(player["car_id"], 1001)
        self.assertEqual(player["race_number"], 97)
        self.assertEqual(player["car_model_id"], 34)
        self.assertEqual(player["car_model_name"], "Porsche 992 GT3 R")
        self.assertEqual(self.players()["total_active"], 1)

    def test_ping_is_not_invented(self):
        # server.log no informa latencia: no se debe mostrar un valor ficticio.
        self.write_log(fixture_bytes("server_connect.log"))
        self.assertIsNone(self.active()[0]["ping_ms"])

    def test_player_survives_log_spam(self):
        self.write_log(fixture_bytes("server_connect.log"))
        self.assertEqual(len(self.active()), 1)
        self.append_log(SPAM_LINE * 5000)
        self.assertEqual(len(self.active()), 1)

    def test_player_found_even_if_first_read_happens_after_spam(self):
        self.write_log(fixture_bytes("server_connect.log") + SPAM_LINE * 5000)
        self.assertEqual(len(self.active()), 1)

    def test_console_format_without_timestamp_prefix(self):
        self.write_log(
            b"Server starting with version 256\r\n"
            b"New connection request: id 3 Ana Maria Lopez S76561190000000003 on car model 30\r\n"
            b"Creating new car connection: carId 1004, carModel 30, raceNumber #7\r\n"
        )
        active = self.active()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["driver_name"], "Ana Maria Lopez")
        self.assertEqual(active[0]["car_id"], 1004)
        self.assertEqual(active[0]["race_number"], 7)

    def test_utf8_and_cp1252_names_are_decoded(self):
        self.write_log(
            b"0: Server starting with version 256\r\n"
            + "10: New connection request: id 0 José Pérez S76561190000000001 on car model 34\r\n".encode("utf-8")
            + b"10: Creating new car connection: carId 1001, carModel 34, raceNumber #97\r\n"
            + "20: New connection request: id 1 Müller Núñez S76561190000000002 on car model 30\r\n".encode("cp1252")
            + b"20: Creating new car connection: carId 1002, carModel 30, raceNumber #12\r\n"
        )
        names = sorted(p["driver_name"] for p in self.active())
        self.assertEqual(names, ["José Pérez", "Müller Núñez"])


class DisconnectionTests(LivePlayersTestCase):
    def test_real_disconnect_block_removes_player(self):
        self.write_log(fixture_bytes("server_connect.log"))
        self.assertEqual(len(self.active()), 1)
        self.append_log(fixture_bytes("server_disconnect.log"))
        self.assertEqual(self.active(), [])

    def test_full_log_in_single_read_has_no_players(self):
        self.write_log(fixture_bytes("server_connect.log") + fixture_bytes("server_disconnect.log"))
        self.assertEqual(self.active(), [])

    def test_dead_connection_timeout_alone_removes_player(self):
        self.write_log(fixture_bytes("server_connect.log"))
        self.append_log(b"60000: Removing dead connection 0  (last lastUdpPaketReceived 5012)\r\n")
        self.assertEqual(self.active(), [])

    def test_car_removed_alone_removes_player(self):
        self.write_log(fixture_bytes("server_connect.log"))
        self.append_log(b"60000: car 1001 has no driving connection anymore, will remove it\r\n")
        self.assertEqual(self.active(), [])

    def test_zero_clients_online_clears_list(self):
        self.write_log(fixture_bytes("server_connect.log"))
        self.append_log(b"60000: 0 client(s) online\r\n")
        self.assertEqual(self.active(), [])

    def test_only_the_disconnected_player_is_removed(self):
        self.write_log(
            fixture_bytes("server_connect.log")
            + b"40000: New connection received 380\r\n"
            + b"40000: 2 client(s) online\r\n"
            + b"40000: New connection request: id 1 Segundo Piloto S76561190000000002 on car model 30\r\n"
            + b"40000: Creating new car connection: carId 1002, carModel 30, raceNumber #12\r\n"
            + b"40000: Sent handshake response for car 1002 connection 1 with 1286 bytes\r\n"
        )
        self.assertEqual(len(self.active()), 2)
        self.append_log(
            b"50000: Client 1 closed the connection (10053)\r\n"
            b"50000: Removing dead connection 1  (last lastUdpPaketReceived 2017)\r\n"
            b"50000: car 1002 has no driving connection anymore, will remove it\r\n"
            b"50000: 1 client(s) online\r\n"
        )
        active = self.active()
        self.assertEqual([p["player_id"] for p in active], [PLAYER_ID])

    def test_reconnect_after_disconnect_lists_player_again(self):
        self.write_log(fixture_bytes("server_connect.log") + fixture_bytes("server_disconnect.log"))
        self.assertEqual(self.active(), [])
        self.append_log(
            b"70000: 1 client(s) online\r\n"
            b"70000: New connection request: id 1 Piloto Prueba S76561190000000001 on car model 34\r\n"
            b"70000: Creating new car connection: carId 1002, carModel 34, raceNumber #97\r\n"
        )
        active = self.active()
        self.assertEqual(len(active), 1)
        self.assertEqual((active[0]["conn_id"], active[0]["car_id"]), (1, 1002))


class SessionAndRestartTests(LivePlayersTestCase):
    def test_session_change_keeps_connected_players(self):
        self.write_log(fixture_bytes("server_connect.log"))
        self.append_log(
            b"60000: Session changed: Practice -> Qualifying 1\r\n"
            b"60000: Detected sessionPhase <waiting for drivers> -> <pre session> (Qualifying)\r\n"
        )
        data = self.players()
        self.assertEqual(len(data["active_players"]), 1)
        self.assertEqual(data["session"]["name"], "Qualifying")
        self.assertEqual(data["session"]["phase"], "pre session")

    def test_server_restart_with_new_log_file_clears_list(self):
        self.write_log(fixture_bytes("server_connect.log"))
        self.assertEqual(len(self.active()), 1)
        self.write_log(b"0: Server starting with version 256\r\n0: Listening to TCP 9232 | UDP 9231\r\n")
        self.assertEqual(self.active(), [])

    def test_server_restart_appended_to_same_file_clears_list(self):
        self.write_log(fixture_bytes("server_connect.log"))
        self.assertEqual(len(self.active()), 1)
        self.append_log(b"0: Server starting with version 256\r\n")
        self.assertEqual(self.active(), [])

    def test_stopped_server_reports_no_players(self):
        self.write_log(fixture_bytes("server_connect.log"))
        self.assertEqual(len(self.active()), 1)
        self.running = False
        self.assertEqual(self.active(), [])

    def test_missing_log_reports_no_players(self):
        self.assertEqual(self.active(), [])


if __name__ == "__main__":
    unittest.main()
