"""Tests de lectura/escritura JSON con las codificaciones que usa ACC."""
import codecs
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import panel_server  # noqa: E402

SAMPLE = {"serverName": "Señor Ñandú · Café", "maxCarSlots": 24, "sessions": [{"sessionType": "R"}]}


class JsonIoTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def path(self, name):
        return os.path.join(self.tmp, name)

    def raw(self, name):
        with open(self.path(name), "rb") as f:
            return f.read()


class WriteUtf16Tests(JsonIoTestCase):
    def test_starts_with_single_utf16_le_bom(self):
        panel_server.write_json_utf16(self.path("settings.json"), SAMPLE)
        raw = self.raw("settings.json")
        self.assertEqual(raw[:2], codecs.BOM_UTF16_LE)
        self.assertNotEqual(raw[2:4], codecs.BOM_UTF16_LE)
        self.assertEqual(raw[2:4], "{".encode("utf-16-le"))

    def test_body_is_little_endian_and_round_trips(self):
        panel_server.write_json_utf16(self.path("settings.json"), SAMPLE)
        raw = self.raw("settings.json")
        self.assertEqual(len(raw) % 2, 0)
        self.assertEqual(json.loads(raw[2:].decode("utf-16-le")), SAMPLE)
        self.assertEqual(panel_server.read_json_safe(self.path("settings.json")), SAMPLE)

    def test_non_ascii_is_written_literally(self):
        panel_server.write_json_utf16(self.path("settings.json"), SAMPLE)
        text = self.raw("settings.json")[2:].decode("utf-16-le")
        self.assertIn("Señor Ñandú · Café", text)

    def test_overwrite_keeps_previous_version_as_bak(self):
        target = self.path("event.json")
        panel_server.write_json_utf16(target, {"track": "monza"})
        panel_server.write_json_utf16(target, {"track": "spa"})
        self.assertEqual(panel_server.read_json_safe(target), {"track": "spa"})
        self.assertEqual(panel_server.read_json_safe(target + ".bak"), {"track": "monza"})
        self.assertEqual([n for n in os.listdir(self.tmp) if n.endswith(".tmp")], [])

    def test_failed_serialization_leaves_original_untouched(self):
        target = self.path("event.json")
        panel_server.write_json_utf16(target, {"track": "monza"})
        with self.assertRaises(TypeError):
            panel_server.write_json_utf16(target, {"bad": object()})
        self.assertEqual(panel_server.read_json_safe(target), {"track": "monza"})


class ReadJsonTests(JsonIoTestCase):
    def write_bytes(self, name, data):
        with open(self.path(name), "wb") as f:
            f.write(data)
        return self.path(name)

    def test_reads_utf16_le_without_bom_like_results(self):
        path = self.write_bytes("r.json", json.dumps(SAMPLE, ensure_ascii=False).encode("utf-16-le"))
        self.assertEqual(panel_server.read_json_safe(path), SAMPLE)

    def test_reads_utf16_be_with_bom(self):
        body = json.dumps(SAMPLE, ensure_ascii=False).encode("utf-16-be")
        path = self.write_bytes("be.json", codecs.BOM_UTF16_BE + body)
        self.assertEqual(panel_server.read_json_safe(path), SAMPLE)

    def test_reads_utf8_with_and_without_bom(self):
        body = json.dumps(SAMPLE, ensure_ascii=False).encode("utf-8")
        self.assertEqual(panel_server.read_json_safe(self.write_bytes("a.json", body)), SAMPLE)
        self.assertEqual(panel_server.read_json_safe(self.write_bytes("b.json", codecs.BOM_UTF8 + body)), SAMPLE)

    def test_reads_legacy_cp1252(self):
        path = self.write_bytes("c.json", json.dumps(SAMPLE, ensure_ascii=False).encode("cp1252"))
        self.assertEqual(panel_server.read_json_safe(path), SAMPLE)

    def test_corrupt_or_missing_returns_default(self):
        path = self.write_bytes("bad.json", b"{ no es json")
        self.assertEqual(panel_server.read_json_safe(path, {"x": 1}), {"x": 1})
        self.assertIsNone(panel_server.read_json_safe(self.path("missing.json")))


if __name__ == "__main__":
    unittest.main()
