import json
from pathlib import Path
import sys
import tempfile
import unittest
from collections import Counter
from unittest.mock import patch
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sync_profile as profile


class ProfileTests(unittest.TestCase):
    def test_publications_deduplicate_orcid_and_curated(self):
        curated = [{"title": "Pose-based Deep Learning", "doi": "10.1234/paper", "year": 2025, "venue": "IEEE"}]
        fetched = [{"title": "POSE based Deep-learning", "doi": "https://doi.org/10.1234/paper", "year": 2025, "venue": "Unknown"},
                   {"title": "A new result", "year": 2026, "url": "https://openalex.org/W1234"}]
        works = profile.merged_publications(curated, fetched)
        self.assertEqual(len(works), 2)
        self.assertEqual(works[0]["title"], "A new result")
        self.assertEqual(works[1]["venue"], "IEEE")

    def test_markdown_escapes_api_title(self):
        item = {"title": "AI [A] & <B>", "year": 2026, "venue": "ML *Research*", "url": "https://doi.org/10.1234/one"}
        output = profile.render_publications([item])
        self.assertIn("AI &#91;A&#93; &amp; &lt;B&gt;", output)
        self.assertNotIn("<B>", output)

    def test_openalex_requires_author_name_and_orcid_filter(self):
        payload = {"results": [
            {"title": "Valid", "publication_year": 2026, "id": "https://openalex.org/W1", "authorships": [{"author": {"display_name": "Alessandro Rongoni"}}]},
            {"title": "Invalid", "id": "https://openalex.org/W2", "authorships": [{"author": {"display_name": "Another Author"}}]},
        ]}
        with patch.object(profile, "get_json", return_value=payload) as get:
            self.assertEqual([x["title"] for x in profile.openalex_works()], ["Valid"])
            self.assertIn(profile.ORCID, get.call_args.args[0])

    def test_publications_keep_all_other_readme_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            readme = Path(tmp) / "README.md"
            curated = Path(tmp) / "pub.json"
            curated.write_text(json.dumps([{"title": "Verified result", "year": 2026, "doi": "10.1234/test", "venue": "Journal"}]))
            readme.write_text("INTRO\n" + profile.START + "\nold\n" + profile.END + "\nFOOTER")
            with patch.object(profile, "README", readme), patch.object(profile, "CURATED", curated), patch.object(profile, "openalex_works", return_value=[]), patch.object(profile, "orcid_works", return_value=[]):
                self.assertTrue(profile.update_publications())
                self.assertFalse(profile.update_publications())
            self.assertIn("INTRO", readme.read_text())
            self.assertIn("FOOTER", readme.read_text())
            self.assertIn("Verified result", readme.read_text())

    def test_activity_svg_valid_xml_and_private_identity_not_leaked(self):
        value = {"restrictedContributionsCount": 14, "totalCommitContributions": 43,
                 "totalPullRequestContributions": 8, "totalIssueContributions": 4,
                 "contributionCalendar": {"totalContributions": 79, "weeks": [
                     {"contributionDays": [{"date": "2026-01-01", "contributionCount": 3}]}]}}
        svg = profile.render_activity_svg(value)
        ET.fromstring(svg)
        self.assertIn(">79<", svg)
        self.assertIn(">43<", svg)
        self.assertNotIn("private", svg.casefold())
        self.assertNotIn("14 repositories", svg)

    def test_languages_excludes_private_forks_archived(self):
        repos = [
            {"name": "public", "owner": {"login": profile.USER}, "private": False, "fork": False, "archived": False},
            {"name": "secret", "owner": {"login": profile.USER}, "private": True, "fork": False},
            {"name": "fork", "owner": {"login": profile.USER}, "private": False, "fork": True},
            {"name": "old", "owner": {"login": profile.USER}, "private": False, "archived": True},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "languages.svg"
            def fake_json(url, headers=None):
                if "/users/" in url:
                    return repos
                self.assertIn("/public/languages", url)
                return {"Python": 800, "TypeScript": 200}
            with patch.object(profile, "LANGUAGES", out), patch.object(profile, "get_json", side_effect=fake_json):
                self.assertTrue(profile.update_languages())
                self.assertFalse(profile.update_languages())
            xml = out.read_text()
            ET.fromstring(xml)
            self.assertIn("80.0%", xml)
            self.assertNotIn("secret", xml)
            self.assertIn("1 public", xml)

    def test_failed_github_request_keeps_previous_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            svg = Path(tmp) / "activity.svg"
            svg.write_text("<svg/>")
            with patch.object(profile, "ACTIVITY", svg), patch.dict("os.environ", {"GITHUB_TOKEN": "placeholder"}), patch.object(profile, "get_json", side_effect=OSError("network unavailable")):
                with self.assertRaises(OSError):
                    profile.update_activity()
            self.assertEqual(svg.read_text(), "<svg/>")

    def test_initial_banner_is_vector_not_embedded_bitmap(self):
        svg = (Path(__file__).resolve().parents[1] / "assets" / "profile-header.svg").read_text()
        ET.fromstring(svg)
        self.assertIn("Alessandro Rongoni", svg)
        self.assertIn("SOFTWARE ENGINEER", svg)
        self.assertNotIn("data:image", svg)
        self.assertNotIn("<image", svg)


if __name__ == "__main__":
    unittest.main()
