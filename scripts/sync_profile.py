#!/usr/bin/env python3
"""Refresh ORCID-linked research highlights and aggregated GitHub activity."""
import datetime as dt
import html
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
SVG = ROOT / "assets" / "github-activity.svg"
ORCID = "0009-0002-2907-8998"
USER = "AlessandroRongoni"
START = "<!-- AUTO-PUBLICATIONS:START -->"
END = "<!-- AUTO-PUBLICATIONS:END -->"


def get_json(url, headers=None, payload=None):
    request = urllib.request.Request(url, data=payload, headers={"User-Agent": "AlessandroRongoni-profile-sync/1.0", "Accept": "application/json", **(headers or {})})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("API request failed")


def canonical_doi(raw):
    raw = (raw or "").strip()
    raw = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)\s*", "", raw, flags=re.I)
    return raw.lower() if raw.lower().startswith("10.") else ""


def openalex_works():
    query = urllib.parse.urlencode({"filter": f"authorships.author.orcid:https://orcid.org/{ORCID}", "per_page": "100", "page": "1", "sort": "publication_date:desc"})
    token = os.getenv("OPENALEX_API_KEY", "")
    if token:
        query += "&" + urllib.parse.urlencode({"api_key": token})
    data = get_json("https://api.openalex.org/works?" + query)
    results = []
    for item in data.get("results", []):
        title = (item.get("title") or "").strip()
        if not title:
            continue
        authors = item.get("authorships") or []
        # This is an ORCID-specific query; also guard against wrong-name records.
        if not any("rongoni" in (a.get("author") or {}).get("display_name", "").lower() for a in authors):
            continue
        doi = canonical_doi(item.get("doi"))
        venue = ((item.get("primary_location") or {}).get("source") or {}).get("display_name") or "Research output"
        year = item.get("publication_year") or ""
        url = "https://doi.org/" + doi if doi else item.get("id", "")
        if not url.startswith("https://"):
            continue
        results.append({"title": title, "doi": doi, "year": year, "venue": venue, "url": url})
    return results


def orcid_works():
    token = os.getenv("ORCID_PUBLIC_TOKEN")
    if not token and os.getenv("ORCID_CLIENT_ID") and os.getenv("ORCID_CLIENT_SECRET"):
        form = urllib.parse.urlencode({
            "client_id": os.environ["ORCID_CLIENT_ID"],
            "client_secret": os.environ["ORCID_CLIENT_SECRET"],
            "grant_type": "client_credentials",
            "scope": "/read-public",
        }).encode("utf-8")
        token = get_json(
            "https://orcid.org/oauth/token",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            payload=form,
        ).get("access_token")
    if not token:
        return []
    data = get_json(f"https://pub.orcid.org/v3.0/{ORCID}/works", headers={"Accept": "application/vnd.orcid+json", "Authorization": "Bearer " + token})
    results = []
    for group in data.get("group", []):
        for item in group.get("work-summary", []):
            title = (((item.get("title") or {}).get("title") or {}).get("value") or "").strip()
            if not title:
                continue
            ids = ((item.get("external-ids") or {}).get("external-id") or [])
            doi = next((canonical_doi(v.get("external-id-value")) for v in ids if (v.get("external-id-type") or "").lower() == "doi"), "")
            date = item.get("publication-date") or {}
            year = ((date.get("year") or {}).get("value") or "")
            venue = ((item.get("journal-title") or {}).get("value") or "Research output")
            url = "https://doi.org/" + doi if doi else f"https://orcid.org/{ORCID}"
            results.append({"title": title, "doi": doi, "year": year, "venue": venue, "url": url})
    return results


def normalize_title(title):
    return re.sub(r"[^a-z0-9]", "", (title or "").lower())


def render_papers(items):
    seen = set()
    rows = []
    for item in sorted(items, key=lambda p: str(p.get("year") or ""), reverse=True):
        key = item.get("doi") or normalize_title(item["title"])
        if key in seen:
            continue
        seen.add(key)
        title = html.escape(" ".join(item["title"].split()), quote=True).replace("[", "&#91;").replace("]", "&#93;")
        venue = html.escape(str(item.get("venue") or "Research output"))
        year = html.escape(str(item.get("year") or "n.d."))
        url = html.escape(item["url"], quote=True)
        rows.append(f"- **[{title}]({url})**  \n  {venue} · {year}")
        if len(rows) == 6:
            break
    return "\n\n".join(rows) if rows else "_No indexed research outputs are currently available._"


def update_papers():
    items = []
    failures = []
    for provider in (orcid_works, openalex_works):
        try:
            items.extend(provider())
        except Exception as exc:
            failures.append(f"{getattr(provider, '__name__', 'source')}: {exc}")
    if not items:
        print("Publication sync skipped: no verified records. " + "; ".join(failures), file=sys.stderr)
        return False
    content = README.read_text(encoding="utf-8")
    if content.count(START) != 1 or content.count(END) != 1:
        raise ValueError("README publication markers missing or ambiguous")
    block = START + "\n" + render_papers(items) + "\n" + END
    content = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: block, content, count=1, flags=re.S)
    README.write_text(content, encoding="utf-8")
    print(f"Publication sync: {len(items)} source records, {len(failures)} provider errors")
    return True


def github_activity():
    token = os.getenv("PROFILE_STATS_TOKEN") or os.getenv("GITHUB_TOKEN")
    if not token:
        print("GitHub activity skipped: no token", file=sys.stderr)
        return False
    gql = """query($login: String!) { user(login: $login) { contributionsCollection { restrictedContributionsCount totalCommitContributions totalPullRequestContributions totalIssueContributions contributionCalendar { totalContributions weeks { contributionDays { date contributionCount } } } } } }"""
    data = get_json("https://api.github.com/graphql", headers={"Authorization": "Bearer " + token}, payload=json.dumps({"query": gql, "variables": {"login": USER}}).encode())
    if data.get("errors") or not data.get("data", {}).get("user"):
        raise ValueError("GitHub GraphQL returned no usable contribution data")
    c = data["data"]["user"]["contributionsCollection"]
    cal = c["contributionCalendar"]
    today = dt.date.today().isoformat()
    counts = [int(cal.get("totalContributions") or 0), int(c.get("totalCommitContributions") or 0), int(c.get("totalPullRequestContributions") or 0), int(c.get("totalIssueContributions") or 0)]
    labels = ["TOTAL CONTRIBUTIONS", "COMMITS", "PULL REQUESTS", "ISSUES"]
    weeks = cal.get("weeks", [])[-31:]
    parts = [f'''<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="GitHub contributions overview" width="980" height="316" viewBox="0 0 980 316"><defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#0B1223"/><stop offset="1" stop-color="#153452"/></linearGradient></defs><rect width="980" height="316" fill="url(#bg)" rx="19"/><text x="36" y="43" fill="#E2E8F0" font-family="Arial,sans-serif" font-size="22" font-weight="bold">GitHub • Research &amp; Engineering Activity</text><text x="36" y="67" fill="#93C5FD" font-family="Arial,sans-serif" font-size="12">Rolling 12 months · synced {today} UTC · GitHub API visibility</text>''']
    for i, (val, label) in enumerate(zip(counts, labels)):
        x = 36 + 239 * i
        parts.append(f'<text x="{x}" y="121" font-family="Arial,sans-serif" fill="#F8FAFC" font-weight="bold" font-size="32">{val:,}</text><text x="{x}" y="145" font-family="Arial,sans-serif" fill="#94A3B8" font-size="11">{label}</text>')
    colors = ["#22334B", "#155E75", "#0891B2", "#06B6D4", "#67E8F9"]
    parts.append('<text x="36" y="190" fill="#CBD5E1" font-family="Arial,sans-serif" font-size="12">Recent contribution history</text>')
    for ix, week in enumerate(weeks):
        for iy, day in enumerate(week.get("contributionDays", [])):
            n = int(day.get("contributionCount") or 0)
            level = 0 if not n else (1 if n < 3 else 2 if n < 6 else 3 if n < 11 else 4)
            parts.append(f'<rect x="{36 + ix * 29}" y="{204 + iy * 13}" width="22" height="9" rx="2" fill="{colors[level]}"/>')
    parts.append('<text x="36" y="304" fill="#64748B" font-family="Arial,sans-serif" font-size="10">Aggregate counts only — no private repository names or code are published.</text></svg>')
    SVG.parent.mkdir(parents=True, exist_ok=True)
    SVG.write_text("".join(parts), encoding="utf-8")
    print(f"GitHub activity sync: {counts[0]} visible contributions; restricted reported: {c.get('restrictedContributionsCount', 0)}")
    return True


def main():
    successes = 0
    for func in (update_papers, github_activity):
        try:
            successes += bool(func())
        except Exception as exc:
            print(f"{func.__name__} failed (previous output retained): {exc}", file=sys.stderr)
    if not successes:
        sys.exit("Nothing updated; check API availability / workflow secrets")


if __name__ == "__main__":
    main()
