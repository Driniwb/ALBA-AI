"""Static checks for ALBA AI 3.1: no API calls or sensitive data."""
import ast
import csv
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "reference_library"


def csv_rows(filename):
    with (LIB / filename).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


class AlbaReferenceChecks(unittest.TestCase):
    def test_app_python_compiles(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        ast.parse(source, filename="app.py")

    def test_sources_and_rules_have_unique_ids(self):
        sources = csv_rows("sources.csv")
        rules = csv_rows("rules.csv")
        self.assertGreaterEqual(len(sources), 2)
        self.assertGreaterEqual(len(rules), 16)
        source_ids = [r["source_id"] for r in sources]
        rule_ids = [r["rule_id"] for r in rules]
        self.assertEqual(len(source_ids), len(set(source_ids)))
        self.assertEqual(len(rule_ids), len(set(rule_ids)))
        self.assertTrue(all(item.startswith("R") for item in rule_ids))

    def test_every_rule_has_valid_source_and_location(self):
        sources = {r["source_id"] for r in csv_rows("sources.csv")}
        for rule in csv_rows("rules.csv"):
            self.assertIn(rule["source_id"], sources)
            self.assertTrue(rule["source_location"].strip())
            self.assertTrue(rule["guidance"].strip())
            self.assertTrue(rule["keywords"].strip())
            self.assertEqual(rule["status"], "editorial_draft")

    def test_glossary_is_not_pretended_approved(self):
        sources = {r["source_id"] for r in csv_rows("sources.csv")}
        for term in csv_rows("glossary.csv"):
            self.assertIn(term["source_id"], sources)
            self.assertTrue(term["english"].strip())
            self.assertTrue(term["albanian"].strip())
            self.assertEqual(term["status"], "candidate")

    def test_editorial_workflow_rules_are_clearly_non_authoritative(self):
        sources = {item["source_id"]: item for item in csv_rows("sources.csv")}
        editorial = sources["ALBA-EDITORIAL-2026"]
        self.assertIn("not_official", editorial["verification"])
        self.assertIn("not_external_authority", editorial["verification"])
        self.assertEqual(editorial["expert_approval"], "pending")
        rules = {rule["rule_id"]: rule for rule in csv_rows("rules.csv")}
        for number in range(38, 46):
            rule = rules[f"R{number}"]
            self.assertEqual(rule["source_id"], "ALBA-EDITORIAL-2026")
            self.assertEqual(rule["status"], "editorial_draft")
            self.assertIn(f"R{number}", rule["source_location"])
        note = LIB / "editorial_guidelines_2026-11.md"
        self.assertTrue(note.is_file())
        text = note.read_text(encoding="utf-8")
        self.assertIn("Nuk është manual zyrtar", text)

    def test_specialized_document_types_exist(self):
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('"Table of Concordance (ToC)":', app)
        self.assertIn('"Memo / internal briefing note":', app)
        self.assertIn("Shënimet e ALBA-s nuk janë udhëzime zyrtare.", app)

    def test_public_sources_remain_pending_expert_review(self):
        for source in csv_rows("sources.csv"):
            self.assertTrue(source["url"].startswith("https://"))
            self.assertEqual(source["expert_approval"], "pending")


if __name__ == "__main__":
    unittest.main()
