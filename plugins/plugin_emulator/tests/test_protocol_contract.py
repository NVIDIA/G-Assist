#!/usr/bin/env python3
"""
Unit and IPC tests for Protocol V2 emulator contract changes.

Covers manifest schema dual-parse, complete/stream text coercion, shutdown
notifications, and request_id routing so late completions cannot steal
in-flight ping/initialize waits.
"""

import json
import queue
import sys
import tempfile
import types
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
EMULATOR_DIR = TESTS_DIR.parent
PLUGINS_DIR = EMULATOR_DIR.parent
if str(PLUGINS_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGINS_DIR))

# Import sibling modules without plugin_emulator/__init__.py, which pulls in
# optional CLI deps (colorama, openai) unused by the protocol contract.
if "plugin_emulator" not in sys.modules:
    _pkg = types.ModuleType("plugin_emulator")
    _pkg.__path__ = [str(EMULATOR_DIR)]
    sys.modules["plugin_emulator"] = _pkg

from plugin_emulator.manifest import FunctionDefinition, PluginManifest
from plugin_emulator.plugin import Plugin, PluginResponse, _as_text
from plugin_emulator.protocol import (
    build_shutdown_notification,
    build_shutdown_request,
)


def _manifest(**overrides) -> PluginManifest:
    fields = dict(
        name="fixture",
        description="test plugin",
        directory=".",
        executable="plugin.py",
        executable_path="plugin.py",
        manifest_version=1,
        protocol_version="2.0",
        persistent=True,
    )
    fields.update(overrides)
    return PluginManifest(**fields)


def _plugin() -> Plugin:
    return Plugin(_manifest())


FIXTURE_PLUGIN = r'''
import json
import os
import struct
import sys

def send(msg):
    payload = json.dumps(msg).encode("utf-8")
    sys.stdout.buffer.write(struct.pack(">I", len(payload)) + payload)
    sys.stdout.buffer.flush()

sys.stderr.write("fixture-stderr\n")
sys.stderr.flush()

buf = bytearray()
while True:
    chunk = os.read(0, 4096)
    if not chunk:
        break
    buf.extend(chunk)
    while len(buf) >= 4:
        length = struct.unpack(">I", buf[:4])[0]
        if len(buf) < 4 + length:
            break
        msg = json.loads(bytes(buf[4:4 + length]).decode("utf-8"))
        del buf[:4 + length]
        method = msg.get("method")
        request_id = msg.get("id")
        sys.stderr.write("got %s id=%s\n" % (method, request_id))
        sys.stderr.flush()
        if method == "initialize":
            send({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"name": "fixture", "protocol_version": "2.0"},
            })
        elif method == "ping":
            send({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"timestamp": 1},
            })
        elif method == "execute":
            send({
                "jsonrpc": "2.0",
                "method": "complete",
                "params": {
                    "request_id": request_id,
                    "success": True,
                    "data": {"results": [1, 2]},
                },
            })
        elif method == "shutdown":
            sys.exit(0)
'''

FIXTURE_MANIFEST = {
    "manifestVersion": 1,
    "protocol_version": "2.0",
    "description": "IPC fixture",
    "executable": "plugin.py",
    "persistent": True,
    "functions": [
        {
            "name": "echo_obj",
            "description": "Return an object payload",
            "properties": {
                "query": {"type": "string", "description": "unused"}
            },
            "required": ["query"],
        }
    ],
}


class TestAsText(unittest.TestCase):
    def test_none_and_string(self):
        self.assertEqual(_as_text(None), "")
        self.assertEqual(_as_text("hello"), "hello")

    def test_object_becomes_json(self):
        self.assertEqual(_as_text({"results": [1]}), '{"results": [1]}')

    def test_non_serializable_falls_back_to_str(self):
        self.assertIn("object", _as_text(object()))


class TestManifestFunctionSchema(unittest.TestCase):
    def test_nested_parameters_schema(self):
        func = FunctionDefinition.from_dict({
            "name": "example_greet",
            "description": "greet",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "who"}
                },
                "required": ["name"],
            },
        })
        self.assertEqual([p.name for p in func.parameters], ["name"])
        self.assertTrue(func.parameters[0].required)

    def test_top_level_properties_schema(self):
        func = FunctionDefinition.from_dict({
            "name": "gassist_echo",
            "description": "echo",
            "properties": {
                "message": {"type": "string", "description": "text"}
            },
            "required": ["message"],
        })
        self.assertEqual([p.name for p in func.parameters], ["message"])
        self.assertTrue(func.parameters[0].required)

    def test_nested_parameters_win_when_both_present(self):
        func = FunctionDefinition.from_dict({
            "name": "both",
            "description": "both schemas",
            "properties": {
                "outer": {"type": "string", "description": "ignored"}
            },
            "required": ["outer"],
            "parameters": {
                "type": "object",
                "properties": {
                    "inner": {"type": "number", "description": "used"}
                },
                "required": ["inner"],
            },
        })
        self.assertEqual([p.name for p in func.parameters], ["inner"])


class TestShutdownProtocol(unittest.TestCase):
    def test_v2_shutdown_is_notification(self):
        note = build_shutdown_notification()
        self.assertTrue(note.is_notification())
        self.assertNotIn("id", note.to_dict())
        self.assertEqual(note.to_dict()["method"], "shutdown")

    def test_legacy_shutdown_request_keeps_id(self):
        req = build_shutdown_request(7)
        self.assertFalse(req.is_notification())
        self.assertEqual(req.to_dict()["id"], 7)

    def test_shutdown_when_stopped_is_success(self):
        response = _plugin().shutdown()
        self.assertTrue(response.success)
        self.assertEqual(response.message, "Plugin already stopped")

    def test_shutdown_returns_stop_failure(self):
        plugin = _plugin()

        class FakeProcess:
            def poll(self):
                return None

            def wait(self, timeout=None):
                return 0

        plugin._process = FakeProcess()
        sent = []
        plugin._send_request = lambda req: sent.append(req) or True
        plugin.stop = lambda: False

        response = plugin.shutdown()
        self.assertFalse(response.success)
        self.assertEqual(response.message, "Failed to stop plugin")
        self.assertEqual(len(sent), 1)
        self.assertTrue(sent[0].is_notification())

    def test_shutdown_returns_stop_success(self):
        plugin = _plugin()

        class FakeProcess:
            def poll(self):
                return None

            def wait(self, timeout=None):
                return 0

        plugin._process = FakeProcess()
        plugin._send_request = lambda req: True
        plugin.stop = lambda: True

        response = plugin.shutdown()
        self.assertTrue(response.success)
        self.assertEqual(response.message, "Plugin stopped")


class TestNotificationRouting(unittest.TestCase):
    def test_known_request_id_goes_only_to_that_queue(self):
        plugin = _plugin()
        q1 = queue.Queue()
        q2 = queue.Queue()
        plugin._pending_responses[1] = q1
        plugin._pending_responses[2] = q2
        payload = PluginResponse(success=True, message="one")
        plugin._queue_notification(1, payload)
        self.assertEqual(q1.get_nowait().message, "one")
        self.assertTrue(q2.empty())

    def test_unknown_request_id_does_not_broadcast(self):
        plugin = _plugin()
        pending = queue.Queue()
        plugin._pending_responses[10] = pending
        plugin._queue_notification(99, PluginResponse(success=True, message="late"))
        self.assertTrue(pending.empty())

    def test_missing_request_id_broadcasts(self):
        plugin = _plugin()
        q1 = queue.Queue()
        q2 = queue.Queue()
        plugin._pending_responses[1] = q1
        plugin._pending_responses[2] = q2
        plugin._queue_notification(None, PluginResponse(success=True, message="all"))
        self.assertEqual(q1.get_nowait().message, "all")
        self.assertEqual(q2.get_nowait().message, "all")

    def test_complete_object_data_does_not_crash_reader(self):
        plugin = _plugin()
        pending = queue.Queue()
        plugin._pending_responses[3] = pending
        plugin._handle_notification({
            "jsonrpc": "2.0",
            "method": "complete",
            "params": {
                "request_id": 3,
                "success": True,
                "data": {"results": ["ok"]},
            },
        })
        response = pending.get_nowait()
        self.assertTrue(response.success)
        self.assertEqual(response.message, '{"results": ["ok"]}')


class TestLiveIpc(unittest.TestCase):
    def test_initialize_ping_object_complete_and_shutdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "fixture"
            plugin_dir.mkdir()
            (plugin_dir / "plugin.py").write_text(FIXTURE_PLUGIN, encoding="utf-8")
            (plugin_dir / "manifest.json").write_text(
                json.dumps(FIXTURE_MANIFEST), encoding="utf-8"
            )
            from plugin_emulator.manifest import ManifestParser

            manifest = ManifestParser.parse_directory(str(plugin_dir))
            self.assertEqual([f.name for f in manifest.functions], ["echo_obj"])
            self.assertEqual(manifest.functions[0].parameters[0].name, "query")

            plugin = Plugin(manifest)
            self.assertTrue(plugin.start())
            try:
                init = plugin.initialize()
                self.assertTrue(init.success, init.message)
                self.assertTrue(plugin.ping_and_wait(timeout_ms=2000))
                result = plugin.execute("echo_obj", {"query": "hi"}, timeout_ms=5000)
                self.assertTrue(result.success, result.message)
                self.assertIn("results", result.message)
                shutdown = plugin.shutdown()
                self.assertTrue(shutdown.success, shutdown.message)
            finally:
                plugin.stop()


if __name__ == "__main__":
    unittest.main()
