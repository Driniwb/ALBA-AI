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
        # The source drawer starts closed to keep the chat uncluttered.
        self.assertFalse(any("SOURCES & CITATIONS" in str(item.value)
                             for item in app.markdown))
        self.assertTrue(any(
            item.key == "alba_sources_toggle" for item in app.button
        ))
        app.button(key="alba_sources_toggle").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(app.session_state["alba_sources_open"])
        self.assertTrue(any("SOURCES & CITATIONS" in str(item.value)
                            for item in app.markdown))
        app.button(key="alba_sources_toggle").click().run()
        self.assertFalse(app.session_state["alba_sources_open"])
        app.button(key="alba_sources_toggle").click().run()
        self.assertTrue(app.session_state["alba_sources_open"])
        self.assertTrue(any(
            "not yet been independently verified" in str(item.value)
            for item in app.caption
        ))

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
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(
            app.session_state["alba_active_conversation"], first
        )
        app.button(key="alba_open_" + second).click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(
            app.session_state["alba_active_conversation"], second
        )
        app.button(key="alba_sources_toggle").click().run()
        self.assertTrue(any(
            "No official document links" in str(c.value) for c in app.caption
        ))
        self.assertEqual(len(app.chat_message), 2)

    def test_search_filters_visible_chats_without_deleting_stored_history(self):
        app = AppTest.from_file(
            str(ROOT / "pages" / "5_Chat_Workspace.py"),
            default_timeout=25,
        ).run()
        owner = app.session_state["alba_demo_owner"]
        store = app.session_state["alba_demo_store"]
        one = store.create_conversation(owner, title="Directive research")
        another = store.create_conversation(owner, title="Rail capacity note")
        app.run()
        app.text_input(key="alba_sidebar_chat_search").set_value("Rail").run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any(
            item.key == "alba_open_" + another for item in app.button
        ))
        self.assertFalse(any(
            item.key == "alba_open_" + one for item in app.button
        ))
        self.assertEqual(len(store.list_conversations(owner)), 2)
        app.text_input(key="alba_sidebar_chat_search").set_value("").run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any(
            item.key == "alba_open_" + one for item in app.button
        ))

    def test_empty_home_has_one_clean_chat_surface_without_tool_shortcuts(self):
        app = AppTest.from_file(
            str(ROOT / "pages" / "5_Chat_Workspace.py"),
            default_timeout=25,
        ).run()
        self.assertEqual(len(app.exception), 0)
        keys = {item.key for item in app.button}
        self.assertIn("alba_new_chat", keys)
        self.assertFalse(any(str(key).startswith("alba_shortcut_") for key in keys))
        self.assertTrue(any("How can ALBA help?" in str(item.value)
                            for item in app.markdown))

    def test_single_registered_page_replaces_specialist_shortcuts(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("st.Page("), 1)
        self.assertNotIn('pages/1_ToC_Builder.py', source)
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=25).run()
        self.assertEqual(len(app.exception), 0)

    def test_uploaded_excerpt_name_appears_in_document_tab(self):
        app = AppTest.from_file(
            str(ROOT / "pages" / "5_Chat_Workspace.py"),
            default_timeout=25,
        ).run()
        owner = app.session_state["alba_demo_owner"]
        store = app.session_state["alba_demo_store"]
        chat_id = store.create_conversation(owner, title="Public sample")
        store.append_exchange(
            owner, chat_id,
            "Check this public act.\n\n[PUBLIC DOCUMENT EXCERPT: Public sample.pdf]\n"
            "This is a synthetic public test excerpt.\n[/PUBLIC DOCUMENT EXCERPT]",
            "The excerpt was reviewed without external retrieval.",
        )
        app.session_state["alba_active_conversation"] = chat_id
        app.run()
        self.assertEqual(len(app.exception), 0)
        app.button(key="alba_sources_toggle").click().run()
        self.assertTrue(any(
            "Public sample.pdf" in str(item.value)
            for item in app.markdown
        ))


if __name__ == "__main__":
    unittest.main()
