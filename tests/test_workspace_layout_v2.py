"""ALBA v2's compact chat-first layout and optional source panel.

Streamlit AppTest uses synthetic public content and no network/API calls.
"""
from pathlib import Path
import unittest

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


class WorkspaceLayoutTests(unittest.TestCase):
    def test_sources_panel_opens_and_closes_without_ai_credentials(self):
        app = AppTest.from_file(
            str(ROOT / "pages" / "5_Chat_Workspace.py"),
            default_timeout=25,
        ).run()
        self.assertEqual(len(app.exception), 0)
        self.assertFalse(app.session_state.get("alba_sources_open", False))
        self.assertTrue(any(
            item.key == "alba_sources_toggle" for item in app.button
        ))
        app.button(key="alba_sources_toggle").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(app.session_state["alba_sources_open"])
        self.assertTrue(any(
            "not yet been independently verified" in str(item.value)
            for item in app.caption
        ))
        app.button(key="alba_sources_toggle").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertFalse(app.session_state["alba_sources_open"])

    def test_source_panel_does_not_mix_chat_histories(self):
        app = AppTest.from_file(
            str(ROOT / "pages" / "5_Chat_Workspace.py"),
            default_timeout=25,
        ).run()
        owner = app.session_state["alba_demo_owner"]
        store = app.session_state["alba_demo_store"]
        first = store.create_conversation(owner, title="Example A")
        store.append_exchange(
            owner, first,
            "Check https://qbz.gov.al/eli/ligj/2012/06/21/69",
            "I have not verified this document.",
        )
        second = store.create_conversation(owner, title="Example B")
        store.append_exchange(
            owner, second,
            "Please explain a synthetic public legal concept.",
            "This answer uses no retrieved legal sources.",
        )
        app.session_state["alba_active_conversation"] = first
        app.run()
        app.button(key="alba_sources_toggle").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(
            app.session_state["alba_active_conversation"], first
        )
        app.button(key="alba_open_" + second).click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(
            app.session_state["alba_active_conversation"], second
        )
        self.assertTrue(any(
            "No official document links" in str(c.value) for c in app.caption
        ))
        self.assertEqual(len(app.chat_message), 2)


if __name__ == "__main__":
    unittest.main()
