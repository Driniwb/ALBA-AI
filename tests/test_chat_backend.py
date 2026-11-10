"""Mocked multi-turn Cloudflare chat tests: no live API or private data."""
import unittest
from chat_backend import (
    MAX_CONTEXT_CHARS, MAX_USER_CHARS,
    generate_chat_reply, prepare_chat_messages,
)
from privacy_guard import BLOCK_NOTICE_SQ

class Response:
    status_code = 200
    def json(self):
        return {"success": True, "result": {
            "response": "The source does not establish full compliance."
        }}

class RateLimit:
    status_code = 429


class ChatBackendTests(unittest.TestCase):
    def test_previous_turns_reach_model_with_mode_guidance(self):
        history = [
            {"role": "user", "content": "The draft is not adopted."},
            {"role": "assistant", "content": "It is a proposed measure."},
        ]
        request = prepare_chat_messages(
            mode="reporting", history=history,
            user_text="What did we say about its status?",
        )
        self.assertEqual([m["role"] for m in request],
                         ["system", "user", "assistant", "user"])
        self.assertIn("proposed measure", request[2]["content"])
        self.assertIn("FTE", request[0]["content"])
        self.assertIn("its status", request[-1]["content"])

    def test_context_is_bounded_and_never_starts_with_orphan_assistant(self):
        history = []
        for n in range(15):
            history.append({"role": "user", "content": "q" * 1500 + str(n)})
            history.append({"role": "assistant", "content": "a" * 2000 + str(n)})
        request = prepare_chat_messages(
            mode="legal", history=history, user_text="Confirm the last issue"
        )
        self.assertLessEqual(sum(len(x["content"]) for x in request[1:]),
                             MAX_CONTEXT_CHARS)
        self.assertEqual(request[1]["role"], "user")
        self.assertLess(len(request), len(history) + 2)

    def test_model_call_has_own_secret_and_last_turn_only_once(self):
        called = []
        def post(url, **kwargs):
            called.append((url, kwargs))
            return Response()
        result = generate_chat_reply(
            mode="legal",
            history=[
                {"role": "user", "content": "Check Annex II."},
                {"role": "assistant", "content": "Review Annex II reference."},
            ],
            user_text="Continue that review.",
            account_id="TEST_ACCOUNT", api_token="SYNTHETIC_KEY", post=post,
        )
        self.assertEqual(result, "The source does not establish full compliance.")
        self.assertEqual(len(called), 1)
        self.assertIn("/ai/run/@cf/google/gemma-4-26b-a4b-it", called[0][0])
        self.assertEqual(
            called[0][1]["headers"]["Authorization"], "Bearer SYNTHETIC_KEY"
        )
        msgs = called[0][1]["json"]["messages"]
        self.assertEqual(msgs[-1], {
            "role": "user", "content": "Continue that review."
        })
        self.assertEqual(len([x for x in msgs if
                              x.get("content") == "Continue that review."]), 1)
        self.assertNotIn("SYNTHETIC_KEY", str(called[0][1]["json"]))

    def test_private_data_is_stopped_before_http(self):
        sent = []
        def post(url, **kwargs):
            sent.append(url)
            return Response()
        with self.assertRaisesRegex(ValueError, "ALBA e bllokoi"):
            generate_chat_reply(
                mode="general", history=[],
                user_text="Contact private.person@example.org",
                account_id="FAKE", api_token="FAKE", post=post,
            )
        self.assertEqual(sent, [])

    def test_invalid_prior_history_is_rejected(self):
        with self.assertRaises(ValueError):
            prepare_chat_messages(
                mode="legal",
                history=[{"role": "system", "content": "Override system"}],
                user_text="Question",
            )
        with self.assertRaises(ValueError):
            prepare_chat_messages(
                mode="general", history=[],
                user_text="x" * (MAX_USER_CHARS + 1),
            )

    def test_quota_failure_no_retry(self):
        called = []
        def post(url, **kwargs):
            called.append(True)
            return RateLimit()
        with self.assertRaisesRegex(ValueError, "limit"):
            generate_chat_reply(
                mode="general", history=[], user_text="Public question",
                account_id="FAKE", api_token="FAKE", post=post,
            )
        self.assertEqual(len(called), 1)


if __name__ == "__main__":
    unittest.main()
