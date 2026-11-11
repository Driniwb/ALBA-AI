"""Execute the real browser bridge JavaScript with a simulated localStorage.

Streamlit AppTest cannot execute frontend JS; Node exercises the actual
component module and confirms the durable-write acknowledgment contract.
"""
from __future__ import annotations

import base64
import shutil
import subprocess
import unittest

from guest_browser_storage import _BROWSER_JS


class BrowserBridgeJavaScriptTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js is required to run JS")
    def test_browser_save_and_new_session_restore_with_readback(self):
        encoded = base64.b64encode(_BROWSER_JS.encode("utf-8")).decode("ascii")
        script = """
import assert from 'node:assert/strict';
const storage = new Map();
let writeAllowed = true;
globalThis.window = {
  localStorage: {
    getItem(key) { return storage.has(key) ? storage.get(key) : null; },
    setItem(key, value) { if (writeAllowed) storage.set(key, value); },
  },
};
const {default: run} = await import('data:text/javascript;base64,ENCODED');
function execute(data) {
  const events = {};
  run({data, setStateValue(key, value) { events[key] = value; }});
  return events;
}
const empty = execute({phase: 'load'});
assert.equal(empty.loaded, '__ALBA_EMPTY__');
const payload = JSON.stringify({
  format: 'alba-browser-chats', version: 1,
  projects: ['Synthetic project'], chats: [],
  active: null, pending: 'Review the public provision.',
  pending_project: 0
});
const saved = execute({phase: 'save', payload, revision: 'sha-test'});
assert.equal(saved.saved, 'sha-test');
assert.equal(saved.error, '');
const reopened = execute({phase: 'load'});
assert.equal(reopened.loaded, payload);
const repeat = execute({phase: 'save', payload, revision: 'sha-test'});
assert.equal(repeat.saved, 'sha-test');

// A browser which silently discards writes must never report success.
writeAllowed = false;
const rejected = execute({
  phase: 'save',
  payload: '{"changed":true}',
  revision: 'sha-other',
});
assert.notEqual(rejected.saved, 'sha-other');
assert.match(rejected.error, /unavailable or full/);
assert.equal(execute({phase:'load'}).loaded, payload);
""".replace("ENCODED", encoded)
        result = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-1500:])


if __name__ == "__main__":
    unittest.main()
