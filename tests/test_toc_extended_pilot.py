"""Regression test for the extended ToC pilot article range."""
import unittest
from toc_units import first_n_articles


class ExtendedPilotTests(unittest.TestCase):
    def test_eight_articles_are_supported_without_nine(self):
        directive = "\n".join(
            f"Article {number}\nSubject {number}\n1. Provision {number}."
            for number in range(1, 10)
        ) + "\n"
        selected = first_n_articles(directive, count=8)
        refs = [item.reference for item in selected]
        self.assertTrue(any(item.startswith("8.") for item in refs))
        self.assertTrue(any(item.startswith("1.") for item in refs))
        self.assertFalse(any(item.startswith("9.") for item in refs))
        self.assertFalse(any(item.startswith("Neni 9") for item in refs))
        with self.assertRaisesRegex(ValueError, "1 to 8"):
            first_n_articles(directive, count=9)


if __name__ == "__main__":
    unittest.main()
