#!/usr/bin/env python3
"""Update public publication listings and privacy-safe GitHub profile graphics.

Standard-library only; requires no credentials for the scholarly fallback data.
"""
from __future__ import annotations

from collections import Counter
import datetime as dt
import html
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib import error, parse, request

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
CURATED = ROOT / "data" / "publications.json"
ACTIVITY = ROOT / "assets" / "github-activity.svg"
LANGUAGES = ROOT / "assets" / "github-languages.svg"
ORCID = "0009-0002-2907-8998"
USER = "AlessandroRongoni"
START = "<!-- AUTO-PUBLICATIONS:START -->"
END = "<!-- AUTO-PUBLICATIONS:END -->"


def get_json(url: str, headers: dict | None = None, payload: bytes | None = None):
    h = {"User-Agent": "rongoni-github-profile/3.0", "Accept": "application/json", **(headers or {})}
    req = request.Request(url, data=payload, headers=h)
    for attempt in range(3):
        try:
            with request.urlopen(req, timeout=22) as response:
                return json.load(response)
        except error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("Unreachable API retry state")


def canonical_doi(raw) -> str:
    raw = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)\s*", "", str(raw or "").strip(), flags=re.I)
    return raw.lower() if re.match(r"^10\.\d{4,9}/\S+$", raw, re.I) else ""


def norm_title(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def escape_md(s: str) -> str:
    return html.escape(str(s), quote=True).replace("[", "&#91;").replace("]", "&#93;").replace("*", "&#42;")


def safe_url(s: str) -> str:
    url = str(s or "").strip()
    p = parse.urlsplit(url)
    if p.scheme != "https" or not p.netloc or p.username or p.password:
        return ""
    return url.replace("(", "%28").replace(")", "%29").replace(" ", "%20")


def openalex_works() -> list[dict]:
    args = {"filter": f"authorships.author.orcid:https://orcid.org/{ORCID}", "per_page": 100, "sort": "publication_date:desc"}
    if os.getenv("OPENALEX_API_KEY"):
        args["api_key"] = os.environ["OPENALEX_API_KEY"]
    data = get_json("https://api.openalex.org/works?" + parse.urlencode(args))
    rows = []
    for w in data.get("results", []):
        title = (w.get("title") or "").strip()
        authors = w.get("authorships") or []
        if not title or not any("rongoni" in (a.get("author") or {}).get("display_name", "").casefold() for a in authors):
            continue
        doi = canonical_doi(w.get("doi"))
        url = safe_url("https://doi.org/" + doi if doi else w.get("id", ""))
        if not url:
            continue
        source = ((w.get("primary_location") or {}).get("source") or {}).get("display_name")
        author_names = [((a.get("author") or {}).get("display_name") or "").strip() for a in authors]
        author_names = [a for a in author_names if a]
        author_string = "; ".join(author_names[:8]) + ("; et al." if len(author_names) > 8 else "")
        rows.append({"title": title, "doi": doi, "year": w.get("publication_year"), "date": w.get("publication_date") or "", "venue": source or "Research output", "url": url, "authors": author_string, "type": "journal" if (((w.get("primary_location") or {}).get("source") or {}).get("type") or "").lower() == "journal" else "other"})
    return rows


def orcid_works() -> list[dict]:
    token = os.getenv("ORCID_PUBLIC_TOKEN")
    if not token and os.getenv("ORCID_CLIENT_ID") and os.getenv("ORCID_CLIENT_SECRET"):
        form = parse.urlencode({"client_id": os.environ["ORCID_CLIENT_ID"], "client_secret": os.environ["ORCID_CLIENT_SECRET"], "grant_type": "client_credentials", "scope": "/read-public"}).encode("utf-8")
        data = get_json("https://orcid.org/oauth/token", headers={"Content-Type": "application/x-www-form-urlencoded"}, payload=form)
        token = data.get("access_token")
    if not token:
        return []
    result = get_json(f"https://pub.orcid.org/v3.0/{ORCID}/works", headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.orcid+json"})
    rows = []
    for group in result.get("group", []):
        for w in group.get("work-summary", []):
            title = (((w.get("title") or {}).get("title") or {}).get("value") or "").strip()
            if not title:
                continue
            identifiers = ((w.get("external-ids") or {}).get("external-id") or [])
            doi = next((canonical_doi(i.get("external-id-value")) for i in identifiers if (i.get("external-id-type") or "").lower() == "doi"), "")
            year = (((w.get("publication-date") or {}).get("year") or {}).get("value"))
            venue = ((w.get("journal-title") or {}).get("value")) or "Research output"
            url = "https://doi.org/" + doi if doi else f"https://orcid.org/{ORCID}"
            rows.append({"title": title, "doi": doi, "year": year, "venue": venue, "url": url})
    return rows


def merged_publications(curated: list[dict], discovered: list[dict]) -> list[dict]:
    """Prefer hand-verified metadata, retain new ORCID/OpenAlex works."""
    seen_titles, seen_dois, rows = set(), set(), []
    for w in [*curated, *discovered]:
        title = str(w.get("title") or "").strip()
        doi = canonical_doi(w.get("doi"))
        key = norm_title(title)
        if not title or not key or key in seen_titles or (doi and doi in seen_dois):
            continue
        link = safe_url("https://doi.org/" + doi if doi else w.get("url", ""))
        if not link:
            continue
        record = dict(w, title=title, doi=doi, url=link)
        rows.append(record)
        seen_titles.add(key)
        if doi:
            seen_dois.add(doi)
    return sorted(rows, key=lambda w: (int(w.get("year") or 0), str(w.get("date") or "")), reverse=True)


def format_authors(value: str) -> str:
    """Escape bibliographic author list, emphasizing the profile owner."""
    authors = [escape_md(x.strip()) for x in str(value or "").split(";") if x.strip()]
    return ", ".join(re.sub(r"(?i)\bA\.\s*Rongoni\b", "**A. Rongoni**", a) for a in authors)


def render_publications(items: list[dict], limit: int = 30) -> str:
    """Grouped publication section with stable curated information and new discoveries."""
    groups = [
        ("journal", "📰 Journal Articles"),
        ("conference", "🎤 Conference & Workshop Papers"),
        ("other", "📑 Other Research Outputs"),
    ]
    output = []
    for group_name, group_heading in groups:
        included = [x for x in items[:limit] if x.get("type", "other") == group_name]
        if not included:
            continue
        output.append("### " + group_heading)
        output.append("")
        current_year = None
        for item in included:
            year = str(item.get("year") or "Other")
            if year != current_year:
                output.append("#### " + escape_md(year))
                output.append("")
                current_year = year
            title = escape_md(" ".join(item["title"].split()))
            venue = escape_md(item.get("venue") or "Research output")
            authors = format_authors(item.get("authors") or "")
            note = str(item.get("note") or "")
            note_label = " ⭐ *First author*" if note.lower() == "first author" else ""
            record = f'- **[{title}]({item["url"]})**{note_label}'
            if authors:
                record += f"  \n  {authors}"
            record += f"  \n  *{venue}*, {year}."
            if item.get("doi"):
                record += f' · [DOI](https://doi.org/{item["doi"]})'
            elif item.get("url") and "arxiv.org" in item["url"]:
                record += f' · [arXiv]({item["url"]})'
            output.append(record)
            output.append("")
    return "\n".join(output).strip() if output else "_See publications on ORCID._"


def write_if_changed(path: Path, content: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def update_publications() -> bool:
    base = json.loads(CURATED.read_text(encoding="utf-8"))
    discovered = []
    for source in (openalex_works, orcid_works):
        try:
            current = source()
            discovered.extend(current)
            print(f"{getattr(source, '__name__', 'scholarly source')}: {len(current)} public works")
        except Exception as exc:
            print(f"{getattr(source, '__name__', 'scholarly source')} unavailable: {exc}", file=sys.stderr)
    items = merged_publications(base, discovered)
    if not items:
        print("No validated publications; keeping existing README", file=sys.stderr)
        return False
    text = README.read_text(encoding="utf-8")
    if text.count(START) != 1 or text.count(END) != 1 or text.index(START) >= text.index(END):
        raise ValueError("README publication markers are missing or duplicated")
    replacement = START + "\n" + render_publications(items) + "\n" + END
    text = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: replacement, text, count=1, flags=re.S)
    return write_if_changed(README, text)


def github_headers() -> dict:
    token = os.getenv("PROFILE_STATS_TOKEN") or os.getenv("GITHUB_TOKEN")
    return {"Authorization": "Bearer " + token} if token else {}


def render_activity_svg(c: dict) -> str:
    calendar = c["contributionCalendar"]
    totals = [calendar.get("totalContributions", 0), c.get("totalCommitContributions", 0), c.get("totalPullRequestContributions", 0), c.get("totalIssueContributions", 0)]
    labels = ["CONTRIBUTIONS", "COMMITS", "PULL REQUESTS", "ISSUES"]
    bg = '''<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="344" viewBox="0 0 1100 344" role="img" aria-label="GitHub contributions from the previous twelve months"><defs><linearGradient id="b" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#0A121D"/><stop offset="1" stop-color="#15293F"/></linearGradient></defs><rect width="1100" height="344" fill="url(#b)" rx="16"/><rect x="34" y="26" width="4" height="24" rx="2" fill="#3DCCD9"/><text x="52" y="45" fill="#F0F6FA" font-family="DejaVu Sans,Arial,sans-serif" font-size="22" font-weight="bold">GitHub activity</text><text x="1061" y="44" text-anchor="end" fill="#88A8BC" font-family="DejaVu Sans,Arial,sans-serif" font-size="12">LAST 12 MONTHS</text><path d="M36 168H1064" stroke="#36516A" opacity=".7"/>'''
    parts = [bg]
    for i, (n, label) in enumerate(zip(totals, labels)):
        x = 42 + i * 267
        count = int(n or 0)
        parts.append(f'<text x="{x}" y="106" fill="#F2FBFF" font-family="DejaVu Sans,Arial,sans-serif" font-size="35" font-weight="bold">{count:,}</text>')
        parts.append(f'<text x="{x}" y="130" fill="#8BB1C4" font-family="DejaVu Sans,Arial,sans-serif" font-size="12" letter-spacing="1.2">{label}</text>')
    parts.append('<text x="40" y="194" fill="#9DBCCE" font-family="DejaVu Sans,Arial,sans-serif" font-size="12">CONTRIBUTION CALENDAR</text>')
    colors = ["#263749", "#17617A", "#158DA6", "#16B5C6", "#64DDE6"]
    for ix, week in enumerate((calendar.get("weeks") or [])[-53:]):
        for iy, day in enumerate((week.get("contributionDays") or [])[:7]):
            value = int(day.get("contributionCount") or 0)
            level = 0 if value == 0 else 1 if value < 3 else 2 if value < 6 else 3 if value < 11 else 4
            parts.append(f'<rect x="{42 + ix * 19}" y="{209 + iy * 14}" width="14" height="10" rx="2" fill="{colors[level]}"/>')
    parts.append('<text x="844" y="329" font-family="DejaVu Sans,Arial,sans-serif" font-size="11" fill="#84A9BA">LESS</text>')
    for j, color in enumerate(colors):
        parts.append(f'<rect x="{885+j*24}" y="319" width="15" height="11" rx="2" fill="{color}"/>')
    parts.append('<text x="1015" y="329" font-family="DejaVu Sans,Arial,sans-serif" font-size="11" fill="#84A9BA">MORE</text></svg>')
    return "".join(parts) + "\n"


def update_activity() -> bool:
    headers = github_headers()
    if not headers:
        print("GitHub GraphQL skipped: no authentication token", file=sys.stderr)
        return False
    query = '''query($login:String!){user(login:$login){contributionsCollection{restrictedContributionsCount totalCommitContributions totalPullRequestContributions totalIssueContributions contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}'''
    payload = json.dumps({"query": query, "variables": {"login": USER}}).encode("utf-8")
    response = get_json("https://api.github.com/graphql", headers={**headers, "Content-Type": "application/json"}, payload=payload)
    if response.get("errors") or not (response.get("data") or {}).get("user"):
        raise ValueError("GitHub GraphQL returned no contribution information")
    collection = response["data"]["user"]["contributionsCollection"]
    if not collection.get("contributionCalendar"):
        raise ValueError("GitHub contribution calendar missing")
    print("Visible contribution total:", collection["contributionCalendar"].get("totalContributions"))
    # Note: restrictedContributionsCount depends on account preferences and API authorization.
    return write_if_changed(ACTIVITY, render_activity_svg(collection))


LANGUAGE_COLORS = {"Python": "#4F9AC9", "TypeScript": "#4E85CF", "JavaScript": "#E4BE55", "C++": "#EA7294", "Kotlin": "#AF81E8", "Java": "#C89472", "HTML": "#E47F59", "CSS": "#9A85CD", "Dart": "#55BBBE", "Jupyter Notebook": "#E59D62", "PHP": "#8F91BA", "C": "#B0B8C6", "Other": "#647A92"}


def render_languages_svg(totals: Counter, repo_count: int) -> str:
    overall = sum(totals.values())
    if not overall:
        raise ValueError("No language bytes")
    greatest = totals.most_common(6)
    parts = ['''<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="312" viewBox="0 0 1100 312" role="img" aria-label="Programming languages in owned public repositories"><defs><linearGradient id="b" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#0B1724"/><stop offset="1" stop-color="#172D44"/></linearGradient></defs><rect width="1100" height="312" fill="url(#b)" rx="16"/><rect x="34" y="26" width="4" height="24" rx="2" fill="#57BEE6"/><text x="52" y="45" fill="#F0F6FA" font-family="DejaVu Sans,Arial,sans-serif" font-size="22" font-weight="bold">Languages in public projects</text><text x="1061" y="44" text-anchor="end" fill="#88A8BC" font-family="DejaVu Sans,Arial,sans-serif" font-size="12">SOURCE CODE COMPOSITION</text>''']
    parts.append(f'<text x="42" y="74" fill="#91B0C2" font-family="DejaVu Sans,Arial,sans-serif" font-size="12">Across {repo_count} public, owned repositories · excluding forks and archived projects</text>')
    for index, (name, amount) in enumerate(greatest):
        col, row = index % 2, index // 2
        x = 42 + col * 536
        y = 113 + row * 62
        pct = amount * 100 / overall
        color = LANGUAGE_COLORS.get(name, "#5C9FB7")
        label = html.escape(name)
        parts.append(f'<circle cx="{x+4}" cy="{y-5}" r="4" fill="{color}"/>')
        parts.append(f'<text x="{x+17}" y="{y}" fill="#DDEBF2" font-family="DejaVu Sans,Arial,sans-serif" font-size="15" font-weight="bold">{label}</text>')
        parts.append(f'<text x="{x+475}" y="{y}" text-anchor="end" fill="#AACADB" font-family="DejaVu Sans,Arial,sans-serif" font-size="14">{pct:.1f}%</text>')
        parts.append(f'<rect x="{x}" y="{y+12}" width="475" height="8" rx="4" fill="#263D50"/>')
        parts.append(f'<rect x="{x}" y="{y+12}" width="{475*pct/100:.1f}" height="8" rx="4" fill="{color}"/>')
    parts.append('<text x="42" y="296" fill="#7899AC" font-family="DejaVu Sans,Arial,sans-serif" font-size="11">Repository language bytes; percentages are not a measure of skill proficiency.</text></svg>')
    return "".join(parts) + "\n"


def update_languages() -> bool:
    # /users/{name}/repos only returns public repos, even if the token can access private repositories.
    headers = github_headers()
    repos = get_json(f"https://api.github.com/users/{USER}/repos?per_page=100&type=owner", headers=headers)
    eligible = [r for r in repos if isinstance(r, dict) and not r.get("private") and not r.get("fork") and not r.get("archived") and r.get("owner", {}).get("login", "").casefold() == USER.casefold() and r.get("name") != USER]
    bytes_by_language = Counter()
    for repo in eligible[:75]:
        url = f"https://api.github.com/repos/{parse.quote(USER)}/{parse.quote(repo['name'])}/languages"
        try:
            lang = get_json(url, headers=headers)
        except Exception as exc:
            print(f"Skipping inaccessible language data for public repo: {type(exc).__name__}", file=sys.stderr)
            continue
        if isinstance(lang, dict):
            for name, amount in lang.items():
                if isinstance(amount, int) and amount > 0:
                    bytes_by_language[name] += amount
    if not bytes_by_language:
        print("No eligible language data; keeping previous graphic", file=sys.stderr)
        return False
    print(f"Public language statistics: {len(eligible)} eligible repositories")
    return write_if_changed(LANGUAGES, render_languages_svg(bytes_by_language, len(eligible)))


def main() -> int:
    failed = 0
    for func in (update_publications, update_activity, update_languages):
        try:
            changed = func()
            print(f"{func.__name__}: {'changed' if changed else 'unchanged/skipped'}")
        except Exception as exc:
            print(f"{func.__name__} failed (existing content preserved): {exc}", file=sys.stderr)
            failed += 1
    # Continue committing healthy data sources even when one optional API is down.
    # A complete outage is still reported as a failed job.
    return 1 if failed == 3 else 0


if __name__ == "__main__":
    sys.exit(main())
