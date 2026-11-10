"""Synthetic legal drafting workflow checks (no actual personal documents)."""
from pathlib import Path
import ast
import unittest

from legal_drafting import (
    ACT_TYPES, DRAFT_MODES, build_legal_messages, legal_review_flags,
    generate_legal_draft,
)

ROOT = Path(__file__).resolve().parents[1]


class LegalDraftingTests(unittest.TestCase):
    def test_four_act_specific_methods(self):
        self.assertEqual(set(ACT_TYPES), {"law", "vkm", "instruction", "regulation"})
        self.assertEqual(set(DRAFT_MODES), {"new","review","amend","transpose"})
        for kind in ACT_TYPES:
            with self.subTest(kind=kind):
                messages = build_legal_messages(
                    act_type=kind, mode="new",
                    source_text="A public synthetic policy objective about transport.",
                    enabling_basis="", drafting_goal="Clarity and consistency",
                )
                self.assertEqual(len(messages), 2)
                self.assertIn(ACT_TYPES[kind]["instructions"], messages[1]["content"])
                self.assertIn("teknikës legjislative", messages[0]["content"])

    def test_transposition_requires_actual_eu_source(self):
        base = dict(
            act_type="vkm", mode="transpose",
            source_text="Neni 1 rregullat e transportit të mallrave.",
            enabling_basis="Act supplied by user",
        )
        with self.assertRaisesRegex(ValueError, "exact EU provision"):
            build_legal_messages(**base)
        messages = build_legal_messages(
            **base,
            eu_source="Article 2(1). Member States shall adopt the necessary measures.",
        )
        self.assertIn("PËRAFRIM SA MË LITERAL", messages[1]["content"])
        self.assertIn("shall/may", messages[0]["content"])
        self.assertIn("Article 2(1)", messages[1]["content"])

    def test_amendment_anchors_old_provision(self):
        with self.assertRaisesRegex(ValueError, "targeted provision"):
            build_legal_messages(
                act_type="law", mode="amend",
                source_text="An adjustment is desired.",
            )
        messages = build_legal_messages(
            act_type="law",mode="amend",
            source_text="Neni 7. Përkufizimet e transportit.",
        )
        self.assertIn("AMENDIM MINIMAL", messages[1]["content"])
        self.assertIn("Mos ndrysho nene të paprekura", messages[0]["content"])

    def test_privacy_preflight_blocks_model_calls(self):
        source = "Internal contact: somebody.private@example.org"
        with self.assertRaises(ValueError):
            build_legal_messages(act_type="instruction",mode="new",source_text=source)

    def test_legal_qa_is_explicitly_uncertified(self):
        flags = legal_review_flags(
            "Neni 1. Kërkesat e transportit.",
            "### Projektteksti normativ\nNeni 2.\n### Çështje për verifikim dhe arsyetim\nMungon baza.",
            "transpose",
        )
        self.assertTrue(any("EU obligation" in flag for flag in flags))
        self.assertTrue(any("Numbers" in flag for flag in flags))

    def test_page_compiles_and_enables_only_explicit_generate(self):
        path = ROOT / "pages" / "3_Legal_Drafting.py"
        text = path.read_text(encoding="utf-8")
        ast.parse(text)
        self.assertIn('st.button("Generate legal draft"', text)
        self.assertIn("screen_upload", text)


if __name__ == "__main__":
    unittest.main()
