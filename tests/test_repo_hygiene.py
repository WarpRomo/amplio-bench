import unittest
from pathlib import Path


class RepoHygieneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]

    def test_license_present(self):
        license_path = self.root / "LICENSE"
        self.assertTrue(license_path.is_file())
        text = license_path.read_text()
        self.assertIn("Apache License", text)
        self.assertIn("Version 2.0", text)

    def test_readme_declares_license(self):
        text = (self.root / "README.md").read_text()
        self.assertIn("## License", text)
        self.assertIn("Apache-2.0", text)

    def test_no_legacy_pilot_config(self):
        self.assertFalse(
            (
                self.root
                / "configs/evocode_pilot_legacy.toml"
            ).exists()
        )

    def test_no_actual_dotenv(self):
        self.assertFalse(
            (self.root / ".env").exists()
        )
        self.assertTrue(
            (self.root / ".env.example").exists()
        )

    def test_no_machine_specific_public_content(self):
        # Build the forbidden strings from fragments so the
        # regression test does not itself introduce them.
        forbidden = [
            "uc" + "la",
            "lab" + "02",
            "yt" + "lab" + "02",
            "/big" + "temp/",
            "/u/" + "ritik",
            "ritik" + "@",
        ]

        hits = []
        for path in self.root.rglob("*"):
            if (
                not path.is_file()
                or ".git" in path.parts
                or "__pycache__" in path.parts
                or path.suffix == ".pyc"
            ):
                continue

            text = path.read_text(
                errors="replace"
            ).lower()
            for token in forbidden:
                if token in text:
                    hits.append(
                        (
                            str(
                                path.relative_to(
                                    self.root
                                )
                            ),
                            token,
                        )
                    )

        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
