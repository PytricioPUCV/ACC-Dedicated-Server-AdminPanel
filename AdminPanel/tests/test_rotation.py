"""Tests de selección de la siguiente pista, parseo de resultados y detección del fin de carrera."""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import panel_server  # noqa: E402

FIXTURES = os.path.join(HERE, "fixtures")
RACE_FIXTURE = os.path.join(FIXTURES, "260911_004721_R.json")
EVENT_PQR = {"track": "spa", "sessions": [{"sessionType": "P"}, {"sessionType": "Q"}, {"sessionType": "R"}]}


class NextTrackTests(unittest.TestCase):
    def test_advances_to_next_track(self):
        self.assertEqual(panel_server.next_track_in_rotation(["monza.json", "spa.json", "zolder.json"], "monza.json"), "spa.json")

    def test_wraps_around_at_the_end(self):
        self.assertEqual(panel_server.next_track_in_rotation(["monza.json", "spa.json"], "spa.json"), "monza.json")

    def test_single_track_rotation_repeats_it(self):
        self.assertEqual(panel_server.next_track_in_rotation(["imola.json"], "imola.json"), "imola.json")

    def test_current_excluded_continues_in_catalog_order(self):
        # Catálogo base: monza, spa, silverstone, nurburgring, ... ; spa fue excluida de la rotación.
        rotation = ["monza.json", "nurburgring.json", "zolder.json"]
        self.assertEqual(panel_server.next_track_in_rotation(rotation, "spa.json"), "nurburgring.json")

    def test_current_excluded_wraps_in_catalog_order(self):
        # nurburgring_24h es la última del catálogo: sigue con la primera pista de la rotación.
        self.assertEqual(panel_server.next_track_in_rotation(["spa.json", "monza.json"], "nurburgring_24h.json"), "monza.json")

    def test_unknown_current_starts_rotation(self):
        self.assertEqual(panel_server.next_track_in_rotation(["spa.json", "monza.json"], None), "spa.json")

    def test_empty_rotation_is_an_error(self):
        with self.assertRaises(ValueError):
            panel_server.next_track_in_rotation([], "spa.json")


class ParseResultTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def write(self, name, data):
        path = os.path.join(self.tmp, name)
        with open(path, "wb") as f:
            f.write(json.dumps(data).encode("utf-16-le"))
        return path

    def test_parses_real_race_result(self):
        result = panel_server.parse_result_file(RACE_FIXTURE)
        self.assertEqual(result, {
            "filename": "260911_004721_R.json",
            "session_type": "R",
            "track": "spa",
            "session_index": 2,
            "driver_count": 3,
            "max_laps": 8,
            "winner": "Piloto 1",
        })

    def test_empty_leaderboard(self):
        path = self.write("x_R.json", {"sessionType": "R", "trackName": "monza", "sessionIndex": 2,
                                       "sessionResult": {"leaderBoardLines": []}})
        result = panel_server.parse_result_file(path)
        self.assertEqual((result["driver_count"], result["max_laps"], result["winner"]), (0, 0, None))

    def test_malformed_fields_do_not_crash(self):
        path = self.write("y_R.json", {"sessionType": "r", "sessionIndex": "2", "sessionResult": {"leaderBoardLines": "x"}})
        result = panel_server.parse_result_file(path)
        self.assertEqual((result["session_type"], result["session_index"], result["driver_count"]), ("R", None, 0))

    def test_invalid_json_returns_none(self):
        path = os.path.join(self.tmp, "z_R.json")
        with open(path, "wb") as f:
            f.write(b"\x00\x01garbage")
        self.assertIsNone(panel_server.parse_result_file(path))


class FinalRaceTests(unittest.TestCase):
    def result(self, **overrides):
        base = {"filename": "a_R.json", "session_type": "R", "track": "spa", "session_index": 2,
                "driver_count": 3, "max_laps": 8, "winner": "Piloto 1"}
        base.update(overrides)
        return base

    def test_last_race_of_pqr_weekend(self):
        self.assertTrue(panel_server.is_final_race_of_weekend(self.result(), EVENT_PQR))

    def test_practice_and_qualifying_never_rotate(self):
        self.assertFalse(panel_server.is_final_race_of_weekend(self.result(session_type="FP", session_index=0), EVENT_PQR))
        self.assertFalse(panel_server.is_final_race_of_weekend(self.result(session_type="Q", session_index=1), EVENT_PQR))

    def test_first_of_two_races_does_not_rotate(self):
        event = {"track": "spa", "sessions": [{"sessionType": "Q"}, {"sessionType": "R"}, {"sessionType": "R"}]}
        self.assertFalse(panel_server.is_final_race_of_weekend(self.result(session_index=1), event))
        self.assertTrue(panel_server.is_final_race_of_weekend(self.result(session_index=2), event))

    def test_result_from_another_track_is_ignored(self):
        self.assertFalse(panel_server.is_final_race_of_weekend(self.result(track="monza"), EVENT_PQR))

    def test_missing_index_or_event_falls_back_to_rotating(self):
        self.assertTrue(panel_server.is_final_race_of_weekend(self.result(session_index=None), EVENT_PQR))
        self.assertTrue(panel_server.is_final_race_of_weekend(self.result(), {}))

    def test_none_result(self):
        self.assertFalse(panel_server.is_final_race_of_weekend(None, EVENT_PQR))


class DetectFinishedRaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.results = os.path.join(self.tmp, "results")
        self.cfg = os.path.join(self.tmp, "cfg")
        os.makedirs(self.results)
        os.makedirs(self.cfg)
        panel_server.write_json_utf16(os.path.join(self.cfg, "event.json"), EVENT_PQR)
        self.running = True
        saved_state = dict(panel_server.app_state)
        self.addCleanup(panel_server.app_state.update, saved_state)
        panel_server.app_state.update({"auto_rotation": True, "last_race_mtime": 0, "rotation_epoch": 7,
                                       "server_start_time": time.time() - 3600, "status_message": ""})
        for patcher in (
            mock.patch.object(panel_server, "RESULTS_DIR", self.results),
            mock.patch.object(panel_server, "CFG_DIR", self.cfg),
            mock.patch.object(panel_server, "is_acc_running", side_effect=lambda: self.running),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def add_result(self, name="260911_004721_R.json", mtime=None, source=RACE_FIXTURE):
        path = os.path.join(self.results, name)
        shutil.copyfile(source, path)
        mtime = mtime or time.time()
        os.utime(path, (mtime, mtime))
        return path

    def test_new_final_race_triggers_rotation(self):
        path = self.add_result()
        self.assertEqual(panel_server.detect_finished_race(), (path, 7))
        # El mismo archivo no vuelve a disparar (sin rotación doble).
        self.assertIsNone(panel_server.detect_finished_race())

    def test_race_seen_while_paused_does_not_rotate_later(self):
        panel_server.app_state["auto_rotation"] = False
        self.add_result()
        self.assertIsNone(panel_server.detect_finished_race())
        panel_server.app_state["auto_rotation"] = True
        self.assertIsNone(panel_server.detect_finished_race())

    def test_race_seen_while_stopped_does_not_rotate_after_start(self):
        self.running = False
        self.add_result()
        self.assertIsNone(panel_server.detect_finished_race())
        self.running = True
        self.assertIsNone(panel_server.detect_finished_race())

    def test_result_older_than_current_server_run_is_ignored(self):
        panel_server.app_state["server_start_time"] = time.time()
        self.add_result(mtime=time.time() - 60)
        self.assertIsNone(panel_server.detect_finished_race())

    def test_race_from_other_track_is_ignored_with_status(self):
        panel_server.write_json_utf16(os.path.join(self.cfg, "event.json"), dict(EVENT_PQR, track="monza"))
        self.add_result()
        self.assertIsNone(panel_server.detect_finished_race())
        self.assertIn("no es la carrera final", panel_server.app_state["status_message"])

    def test_qualifying_file_is_not_a_race(self):
        self.add_result(name="260911_002305_Q.json")
        self.assertIsNone(panel_server.detect_finished_race())


if __name__ == "__main__":
    unittest.main()
