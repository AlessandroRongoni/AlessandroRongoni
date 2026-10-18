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

    def test_banner_is_exact_png_asset(self):
        import struct
        banner = Path(__file__).resolve().parents[1] / "assets" / "profile-header.png"
        with banner.open("rb") as fh:
            header = fh.read(24)
        self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
        self.assertGreaterEqual(struct.unpack(">I", header[16:20])[0], 2000)

    def test_original_profile_sections_and_stats_are_retained(self):
        readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
        sections = ["About Me", "Featured Projects", "Publications", "Education", "Experience", "Achievements", "GitHub Stats"]
        for sec in sections:
            self.assertIn(sec, readme)
        for technology in ["Python", "C++", "PHP", "React", "Firebase", "Arduino", "ESP32", "YOLO", "TensorFlow", "Rasa"]:
            self.assertIn(technology, readme)
        for suffix in ["api?username=AlessandroRongoni", "api/top-langs/?username=AlessandroRongoni", "github-profile-trophy.vercel.app"]:
            self.assertIn(suffix, readme)
        self.assertIn('src="./assets/profile-header.png"', readme)

    def test_sync_preserves_badges_projects_emojis_and_stats(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            tmp_readme = Path(tmp) / "README.md"
            original = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
            tmp_readme.write_text(original, encoding="utf-8")
            data_path = Path(__file__).resolve().parents[1] / "data" / "publications.json"
            with patch.object(profile, "README", tmp_readme), patch.object(profile, "CURATED", data_path), patch.object(profile, "openalex_works", return_value=[]), patch.object(profile, "orcid_works", return_value=[]):
                profile.update_publications()
            updated = tmp_readme.read_text(encoding="utf-8")
            a = original.split(profile.START)[0], original.split(profile.END)[1]
            b = updated.split(profile.START)[0], updated.split(profile.END)[1]
            self.assertEqual(a, b)
            for item in ("🏆 Achievements", "🎨 Beyond Code", "![Arduino]", "![TensorFlow]", "github-profile-trophy.vercel.app"):
                self.assertIn(item, updated)

    def test_publication_authors_retained(self):
        out = profile.render_publications([{"title": "Example", "year": 2026, "venue": "Venue", "doi": "10.1234/example", "url": "https://doi.org/10.1234/example", "authors": "C. Researcher; A. Rongoni; et al.", "note": "First author"}])
        self.assertIn('**A. Rongoni**', out)
        self.assertIn('⭐ *First author*', out)
        self.assertIn('[DOI](https://doi.org/10.1234/example)', out)


if __name__ == "__main__":
    unittest.main()
