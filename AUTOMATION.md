# Profile maintenance and scholarly-data integration

These are maintainer notes, not part of the rendered GitHub profile.

## What updates automatically

- **Publications:** the block between `<!-- AUTO-PUBLICATIONS:START -->` and `<!-- AUTO-PUBLICATIONS:END -->` in `README.md` is regenerated from **hand-reviewed** `data/publications.json` plus newly discovered public works associated with ORCID `0009-0002-2907-8998` through OpenAlex (and optionally ORCID's API). The curated works take precedence, so the complete author names and publication links you've entered are never overwritten by lower-quality metadata. Projects, badge sections, hobbies, education, experience and achievements are **never changed** by the script.
- **Additional contribution graph:** `assets/github-activity.svg` is regenerated from GitHub GraphQL when a usable token is available. Calendar counts and commits/PRs/issues reflect visibility and attribution rules; names and code of private repositories are never written.
- **Additional languages graph:** `assets/github-languages.svg` collects byte counts from **public**, owned, non-fork, non-archived repositories. This does not measure coding proficiency and deliberately omits private repo language composition.

The **classic Github Readme Stats cards**, the **Top Languages card** and **GitHub Trophies** are intentionally restored, embedded by URL in `README.md` and independent of Actions. Their public endpoints may occasionally be unavailable because of third-party hosting or GitHub API rate limits. Self-hosting those services separately is required if you need stronger availability guarantees.

## First setup

1. Merge the branch into the default branch, `main`.
2. Ensure Actions are enabled and workflow token has `contents: write` permissions. Branch rules can block automated commits.
3. Actions → **Update profile data** → **Run workflow**. Inspect logs and resulting diff.
4. The schedule is `17 3 * * *`, or **12:17 JST daily**; GitHub may delay or disable scheduled workflows on inactive repositories.

## Optional GitHub Actions secrets

| Secret | Purpose |
|---|---|
| `PROFILE_STATS_TOKEN` | Optional permissioned token for activity collection. Use least privilege; do not paste into README. |
| `ORCID_PUBLIC_TOKEN` | Optional read-public API access token for ORCID. |
| `ORCID_CLIENT_ID` and `ORCID_CLIENT_SECRET` | Optional ORCID public API client credentials, used to obtain `/read-public`. |
| `OPENALEX_API_KEY` | Optional OpenAlex key; improves quota reliability. |

OpenAlex can handle small-scale public queries without a key. ORCID is linked visibly in README regardless of whether its optional direct API token is configured. Without a direct ORCID token, newly discovered papers can still enter via OpenAlex indexing.

## Private contributions

- On your GitHub profile, enable **Contribution settings → Private contributions** to display eligible private contributions **anonymously** on GitHub's native calendar.
- The two external `github-readme-stats` cards are public-data cards by default; they do **not** magically acquire access to your private repos from GitHub Actions secrets.
- The custom contribution graph can receive broader counts if the token has access, but does not guarantee all private/organization contributions; GitHub's contribution eligibility, SSO and visibility affect totals. Check against your actual profile.
- Private repository names, code, languages and file details are never published in this package.

## Add or correct a paper

Edit `data/publications.json`. Each entry uses `title`, `year`, `venue`, `authors` (semicolon-separated), and a `doi` or an `https://` `url`. An optional `note: "First author"` adds a first-author highlight. Curated records are shown even if ORCID/OpenAlex are temporarily unavailable. For new public items indexed by ORCID/OpenAlex, the script appends them (deduplicated by title and DOI).

To verify locally:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/sync_profile.py   # live network required for source updates
```

## Safety

- The generator writes only the controlled publications block and the two SVG data assets.
- API error cases preserve previous assets and bibliographic information.
- No fictional activity counts, private repo names or credentials appear in README or image assets.
- No dependency installation is required; only Python 3.12 standard library.
