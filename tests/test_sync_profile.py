import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "scripts"))
import sync_profile as sp


class SyncProfileTests(unittest.TestCase):
    def test_publications_deduplicated_and_escaped(self):
        paper = {"title": "AI & <Plants>", "doi": "10.1234/abc", "year": 2026, "venue": "ACM & IEEE", "url": "https://doi.org/10.1234/abc"}
        output = sp.render_papers([paper, paper])
        self.assertEqual(output.count("10.1234/abc"), 1)
        self.assertIn("AI &amp; &lt;Plants&gt;", output)

    def test_openalex_filters_nonmatching_name(self):
        data = {"results": [
            {"title": "A validated paper", "doi": "https://doi.org/10.1/a", "publication_year": 2026, "authorships": [{"author": {"display_name": "Alessandro Rongoni"}}]},
            {"title": "Unrelated", "doi": "https://doi.org/10.1/b", "authorships": [{"author": {"display_name": "Someone Else"}}]},
        ]}
        with patch.object(sp, "get_json", return_value=data):
            result = sp.openalex_works()
        self.assertEqual([x["title"] for x in result], ["A validated paper"])

    def test_publication_sync_retains_curated_content(self):
        with tempfile.TemporaryDirectory() as folder:
            readme = pathlib.Path(folder) / "README.md"
            readme.write_text("CURATED\n" + sp.START + "\nold\n" + sp.END + "\nOTHER", encoding="utf-8")
            paper = {"title": "Research Paper", "doi": "10.1234/test", "year": 2026, "venue": "Research", "url": "https://doi.org/10.1234/test"}
            with patch.object(sp, "README", readme), patch.object(sp, "orcid_works", return_value=[]), patch.object(sp, "openalex_works", return_value=[paper]):
                self.assertTrue(sp.update_papers())
            self.assertTrue(readme.read_text().startswith("CURATED\n"))
            self.assertIn("OTHER", readme.read_text())
            self.assertIn("Research Paper", readme.read_text())

    def test_api_failure_does_not_erase_publication_list(self):
        with tempfile.TemporaryDirectory() as folder:
            readme = pathlib.Path(folder) / "README.md"
            original = sp.START + "\nOriginal publication\n" + sp.END
            readme.write_text(original, encoding="utf-8")
            with patch.object(sp, "README", readme), patch.object(sp, "orcid_works", side_effect=OSError("offline")), patch.object(sp, "openalex_works", side_effect=OSError("offline")):
                self.assertFalse(sp.update_papers())
            self.assertEqual(readme.read_text(), original)

    def test_svg_keeps_repos_private(self):
        payload = {"data": {"user": {"contributionsCollection": {
            "restrictedContributionsCount": 1, "totalCommitContributions": 42, "totalPullRequestContributions": 3,
            "totalIssueContributions": 2, "contributionCalendar": {"totalContributions": 55, "weeks": [{"contributionDays": [{"date": "2026-10-18", "contributionCount": 4}]}]}
        }}}}
        with tempfile.TemporaryDirectory() as folder, patch.dict("os.environ", {"GITHUB_TOKEN": "dummy-test-token"}):
            with patch.object(sp, "SVG", pathlib.Path(folder) / "activity.svg"), patch.object(sp, "get_json", return_value=payload):
                self.assertTrue(sp.github_activity())
                content = (pathlib.Path(folder) / "activity.svg").read_text()
            self.assertIn("55", content)
            self.assertIn("42", content)
            self.assertNotIn("dummy-test-token", content)
            self.assertNotIn("repository", content.lower().split("svg")[0])


if __name__ == "__main__":
    unittest.main()
