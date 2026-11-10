"""Professional synthetic QA cases for ALBA legal and EU-reporting workflows.

Fixtures are deliberately synthetic and public-safe. These tests exercise
prompt requirements and red-flag heuristics; they cannot certify AI prose.
"""
import unittest

from legal_drafting import build_legal_messages, legal_review_flags
from communication_studio import build_messages, load_library, qa_flags


SYNTHETIC_VKM = (
    "Neni 4\n"
    "Transporti i mallrave të rrezikshme lejohet sipas kërkesave teknike "
    "të përcaktuara në aneksin I dhe aneksin II.\n"
    "[Tekst demonstrues, jo dispozitë në fuqi.]"
)
EU_CASE = (
    "Directive 2008/68/EC, Article 3(1), demonstration excerpt: "
    "Without prejudice to Article 6, dangerous goods shall not be transported "
    "where prohibited under Annex I, Annex II or Annex III."
)

SYNTHETIC_CAPACITY = (
    "Synthetic demonstrator: the Transport Oversight Unit has 6 authorised "
    "positions, 4 occupied and 2 vacancies (4 FTE in active posts). "
    "In Q2 2026 it carried out 12 inspections and identified 3 "
    "irregularities. A draft implementing measure is awaiting approval. "
    "An IT system is installed but not yet operational. Training and "
    "operational enforcement procedures remain incomplete."
)


class ProfessionalScenarioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources, cls.rules, cls.albanian = load_library()

    def test_vkm_literal_first_transposition_source_integrity(self):
        messages = build_legal_messages(
            act_type="vkm", mode="transpose", source_text=SYNTHETIC_VKM,
            eu_source=EU_CASE, enabling_basis="",
            drafting_goal="Review only the target clause; do not invent a delegation.",
        )
        system, request = (item["content"] for item in messages)
        self.assertIn("PËRAFRIM SA MË LITERAL", request)
        self.assertIn("Annex III", request)
        self.assertIn(SYNTHETIC_VKM, request)
        self.assertIn("VENDOSI", system)
        self.assertIn("[nuk është dhënë]", request)
        self.assertIn("Mos shpik", system)
        self.assertIn("anëtarësimit", system)

    def test_vkm_amendment_has_distinct_old_new_requirements(self):
        messages = build_legal_messages(
            act_type="vkm", mode="amend", source_text=SYNTHETIC_VKM,
            drafting_goal="Change only neni 4, preserve untouched provisions.",
        )
        system, request = (item["content"] for item in messages)
        self.assertIn("AMENDIM MINIMAL", request)
        self.assertIn("tekstin ekzistues", system)
        self.assertIn("tekstin e propozuar", system)
        self.assertIn("Mos ndrysho nene të paprekura", system)

    def test_vkm_qa_detects_annex_missing_even_if_in_review_notes(self):
        defective = (
            "### Projektteksti normativ\n"
            "Neni 4. Transporti sipas aneksit I dhe aneksit II.\n"
            "### Çështje për verifikim dhe arsyetim\n"
            "Annex III is not reproduced; check national applicability."
        )
        flags = legal_review_flags(EU_CASE, defective, "transpose")
        self.assertTrue(any("Annex III" in item for item in flags), flags)
        complete = defective.replace("aneksit II.", "aneksit II dhe aneksit III.")
        complete_flags = legal_review_flags(EU_CASE, complete, "transpose")
        self.assertFalse(any("Annex III" in item for item in complete_flags), complete_flags)

    def test_eu_capacity_prompt_keeps_status_and_evidence(self):
        messages = build_messages(
            format_id="administrative_capacity", mode="create",
            source_text=SYNTHETIC_CAPACITY, organization="Demo authority",
            audience="European Commission", objective="Report evidenced capacity",
            visual_description="", communication_rules=self.rules,
            albanian_rules=self.albanian, output_language="en",
        )
        system, request = (item["content"] for item in messages)
        self.assertIn("Output the draft in English", system)
        self.assertIn("existing staffing", system)
        self.assertIn("formal legal approximation", system)
        self.assertIn("4 FTE", request)
        self.assertIn("12 inspections", request)
        self.assertIn("not yet operational", request)
        self.assertNotIn("R17:", request)
        self.assertNotIn("C01:", request)

    def test_eu_reporting_qa_flags_unsupported_strong_claims(self):
        defective = (
            "### Draft for transmission\n"
            "The unit is fully compliant. It completed 27 inspections, "
            "and the measure was adopted.\n"
            "### Verification before submission\n"
            "Institutional sign-off is outstanding."
        )
        flags = qa_flags(SYNTHETIC_CAPACITY, defective, "administrative_capacity")
        self.assertTrue(any("numbers or dates" in x for x in flags), flags)
        self.assertTrue(any("FTE" in x for x in flags), flags)
        self.assertTrue(any("alignment or benchmark" in x for x in flags), flags)
        self.assertTrue(any("adopted" in x for x in flags), flags)

    def test_eu_reporting_qa_allows_source_grounded_narrative(self):
        grounded = (
            "### Draft for transmission\n"
            "The synthetic unit has 4 FTE in post against 6 authorised "
            "positions, with 2 vacancies. During Q2 2026 it completed "
            "12 inspections and found 3 irregularities. The implementing "
            "measure remains a draft, and the IT system is not yet operational.\n"
            "### Verification before submission\n"
            "Validate the staffing register and inspection logs."
        )
        flags = qa_flags(SYNTHETIC_CAPACITY, grounded, "administrative_capacity")
        self.assertEqual([], flags)


if __name__ == "__main__":
    unittest.main()
