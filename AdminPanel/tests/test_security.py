"""Tests de autenticación, secretos, rutas estáticas y endpoints de configuración contra el handler HTTP real."""
import http.client
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ADMIN_DIR = os.path.dirname(HERE)
sys.path.insert(0, ADMIN_DIR)

import panel_server  # noqa: E402

TOKEN = "test-token-0123456789abcdefghijkl"
SETTINGS = {"serverName": "Servidor de Pruebas", "adminPassword": "admin-secreto", "password": "sala-secreta",
            "spectatorPassword": "espectador-secreto", "carGroup": "FreeForAll", "maxCarSlots": 24,
            "isRaceLocked": 1, "dumpLeaderboards": 1, "configVersion": 1}
PLAYER = "S76561190000000001"


class PanelHttpTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        cfg = os.path.join(self.tmp, "cfg")
        pools = os.path.join(self.tmp, "tracks_pool")
        os.makedirs(cfg)
        os.makedirs(pools)
        for track_file in panel_server.CATALOG_TRACK_FILES:
            panel_server.write_json_utf8(os.path.join(pools, track_file), {"track": track_file[:-5]})
        panel_server.write_json_utf16(os.path.join(cfg, "settings.json"), SETTINGS)
        panel_server.write_json_utf16(os.path.join(cfg, "configuration.json"),
                                      {"udpPort": 9231, "tcpPort": 9232, "maxConnections": 85, "configVersion": 1})
        panel_server.write_json_utf16(os.path.join(cfg, "entrylist.json"), {"entries": [
            {"drivers": [{"firstName": "Piloto", "lastName": "Uno", "playerID": PLAYER}], "raceNumber": 7, "isServerAdmin": 1},
            {"drivers": [{"firstName": "Piloto", "lastName": "Dos", "playerID": "S76561190000000002"}], "raceNumber": 8, "isServerAdmin": 0},
        ], "configVersion": 1, "forceEntryList": 0})

        saved_rotation = panel_server.TRACK_ROTATION
        saved_state = dict(panel_server.app_state)
        self.addCleanup(setattr, panel_server, "TRACK_ROTATION", saved_rotation)
        self.addCleanup(panel_server.app_state.update, saved_state)
        for patcher in (
            mock.patch.object(panel_server, "PANEL_TOKEN", TOKEN),
            mock.patch.object(panel_server, "CFG_DIR", cfg),
            mock.patch.object(panel_server, "POOLS_DIR", pools),
            mock.patch.object(panel_server, "ROTATION_CONFIG_FILE", os.path.join(cfg, "rotation_config.json")),
            mock.patch.object(panel_server, "ENTRYLIST_FILE", os.path.join(cfg, "entrylist.json")),
            mock.patch.object(panel_server, "BANLIST_FILE", os.path.join(cfg, "banlist.json")),
            mock.patch.object(panel_server, "WEB_DIR", os.path.join(ADMIN_DIR, "web")),
            mock.patch.object(panel_server, "load_managed_pid", return_value=None),
            mock.patch.object(panel_server, "is_acc_running", return_value=False),
            mock.patch.object(panel_server, "is_any_acc_running", return_value=False),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), panel_server.AdminPanelHandler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, method, path, body=None, token=TOKEN, raw_headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=10)
        conn.putrequest(method, path)
        if token is not None:
            conn.putheader("X-Admin-Token", token)
        for name, value in (raw_headers or []):
            conn.putheader(name, value)
        payload = json.dumps(body).encode("utf-8") if body is not None else b""
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Content-Length", str(len(payload)))
        conn.endheaders(payload)
        response = conn.getresponse()
        data = response.read()
        conn.close()
        try:
            return response.status, json.loads(data.decode("utf-8"))
        except ValueError:
            return response.status, data

    def settings_on_disk(self):
        return panel_server.read_json_safe(os.path.join(panel_server.CFG_DIR, "settings.json"))


class AuthTests(PanelHttpTestCase):
    def test_missing_or_wrong_token_is_rejected(self):
        self.assertEqual(self.request("GET", "/api/status", token=None)[0], 401)
        self.assertEqual(self.request("GET", "/api/status", token="x" * 32)[0], 401)
        self.assertEqual(self.request("POST", "/api/server/stop", {}, token=None)[0], 401)

    def test_non_ascii_token_is_rejected_without_crashing(self):
        status, body = self.request("GET", "/api/status", token=None, raw_headers=[("X-Admin-Token", b"t\xf6k\xe9n\xff")])
        self.assertEqual((status, body), (401, {"error": "No autorizado"}))

    def test_valid_token_is_accepted(self):
        status, body = self.request("GET", "/api/status")
        self.assertEqual(status, 200)
        self.assertEqual((body["udp_port"], body["tcp_port"], body["max_connections"]), (9231, 9232, 85))

    def test_mask_token_never_reveals_full_token(self):
        masked = panel_server.mask_token(TOKEN)
        self.assertNotIn(TOKEN, masked)
        self.assertTrue(masked.startswith(TOKEN[:4]) and masked.endswith(TOKEN[-4:]))
        self.assertEqual(panel_server.mask_token("corto"), "****")

    def test_new_token_replaces_stored_one(self):
        auth_file = os.path.join(self.tmp, "panel_auth.json")
        with mock.patch.object(panel_server, "AUTH_FILE", auth_file), mock.patch.dict(os.environ, {"ACC_PANEL_TOKEN": ""}):
            first = panel_server.load_or_create_panel_token()
            self.assertEqual(panel_server.load_or_create_panel_token(), first)
            second = panel_server.load_or_create_panel_token(force_new=True)
            self.assertNotEqual(second, first)
            self.assertEqual(panel_server.load_or_create_panel_token(), second)


class SecretsTests(PanelHttpTestCase):
    def test_get_config_never_returns_passwords(self):
        status, body = self.request("GET", "/api/config")
        self.assertEqual(status, 200)
        raw = json.dumps(body)
        for secret in ("admin-secreto", "sala-secreta", "espectador-secreto"):
            self.assertNotIn(secret, raw)
        self.assertEqual(body["secrets_set"], {"adminPassword": True, "password": True, "spectatorPassword": True})
        self.assertEqual(body["settings"]["serverName"], "Servidor de Pruebas")

    def test_saving_without_passwords_keeps_current_ones(self):
        _, body = self.request("GET", "/api/config")
        settings = dict(body["settings"], serverName="Nombre Nuevo")
        status, result = self.request("POST", "/api/config", {"settings": settings})
        self.assertEqual(status, 200, result)
        saved = self.settings_on_disk()
        self.assertEqual(saved["serverName"], "Nombre Nuevo")
        self.assertEqual((saved["adminPassword"], saved["password"], saved["spectatorPassword"]),
                         ("admin-secreto", "sala-secreta", "espectador-secreto"))

    def test_explicit_empty_join_password_makes_room_public(self):
        status, _ = self.request("POST", "/api/config", {"settings": {"password": ""}})
        self.assertEqual(status, 200)
        self.assertEqual(self.settings_on_disk()["password"], "")
        self.assertEqual(self.settings_on_disk()["adminPassword"], "admin-secreto")

    def test_empty_admin_password_is_rejected(self):
        status, _ = self.request("POST", "/api/config", {"settings": {"adminPassword": ""}})
        self.assertEqual(status, 400)
        self.assertEqual(self.settings_on_disk()["adminPassword"], "admin-secreto")


class RobustnessTests(PanelHttpTestCase):
    def test_internal_error_returns_json_500(self):
        with mock.patch.object(panel_server, "parse_active_players", side_effect=RuntimeError("boom")), \
                mock.patch("traceback.print_exc"), mock.patch("builtins.print"):
            status, body = self.request("GET", "/api/players")
        self.assertEqual(status, 500)
        self.assertFalse(body["success"])

    def test_static_path_traversal_is_blocked(self):
        for path in ("/../panel_server.py", "/%2e%2e/panel_server.py", "/..%5cpanel_server.py", "/css/%00x"):
            self.assertEqual(self.request("GET", path, token=None)[0], 404, path)
        self.assertEqual(self.request("GET", "/", token=None)[0], 200)


class RotationAndEntrylistTests(PanelHttpTestCase):
    def test_auto_rotation_explicit_value_is_idempotent(self):
        for _ in range(2):
            status, body = self.request("POST", "/api/rotation/toggle", {"enabled": False})
            self.assertEqual((status, body["auto_rotation"]), (200, False))
        self.assertEqual(self.request("POST", "/api/rotation/toggle", {"enabled": "no"})[0], 400)

    def test_concurrent_track_toggles_are_not_lost(self):
        tracks = [f"{t}.json" for t in panel_server.DLC_CATEGORIES["base"]["tracks"][:8]]
        threads = [threading.Thread(target=self.request, args=("POST", "/api/rotation/track-toggle",
                                                                {"track_file": t, "enabled": False})) for t in tracks]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(panel_server.get_rotation_config()["disabled_tracks"]), sorted(tracks))

    def test_remove_entry_by_steam_id(self):
        status, body = self.request("POST", "/api/entrylist/remove", {"playerId": PLAYER})
        self.assertEqual(status, 200, body)
        remaining = [e["drivers"][0]["playerID"] for e in panel_server.get_entrylist()["entries"]]
        self.assertEqual(remaining, ["S76561190000000002"])
        self.assertEqual(self.request("POST", "/api/entrylist/remove", {"playerId": PLAYER})[0], 404)

    def test_force_entrylist_toggle(self):
        status, _ = self.request("POST", "/api/entrylist/force", {"enabled": True})
        self.assertEqual(status, 200)
        self.assertEqual(panel_server.get_entrylist()["forceEntryList"], 1)
        self.assertEqual(self.request("POST", "/api/entrylist/force", {"enabled": 1})[0], 400)


class KillServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.pid_file = os.path.join(self.tmp, "managed_acc_pid.json")
        panel_server.atomic_write_json(self.pid_file, {"pid": 4321, "started_at": 1}, "utf-8")
        saved_state = dict(panel_server.app_state)
        self.addCleanup(panel_server.app_state.update, saved_state)
        for patcher in (
            mock.patch.object(panel_server, "PID_FILE", self.pid_file),
            mock.patch.object(panel_server, "load_managed_pid", return_value=4321),
            mock.patch.object(panel_server.subprocess, "run"),
            mock.patch.object(panel_server.time, "sleep"),
            mock.patch("builtins.print"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_waits_until_process_exits_then_clears_pid(self):
        with mock.patch.object(panel_server, "is_pid_acc_running", side_effect=[True, True, False]):
            self.assertTrue(panel_server.kill_acc_server())
        self.assertFalse(os.path.exists(self.pid_file))

    def test_keeps_pid_when_process_survives_taskkill(self):
        with mock.patch.object(panel_server, "is_pid_acc_running", return_value=True), \
                mock.patch.object(panel_server, "KILL_WAIT_SECONDS", 0):
            self.assertFalse(panel_server.kill_acc_server())
        self.assertTrue(os.path.exists(self.pid_file))
        self.assertIn("sigue en ejecución", panel_server.app_state["status_message"])


if __name__ == "__main__":
    unittest.main()
