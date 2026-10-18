# Profile data pipeline

Technical maintenance notes. These details are intentionally not included in the public README.

## What gets updated

- `README.md`, between the `AUTO-PUBLICATIONS` comments: combines **hand-reviewed bibliographic references** from `data/publications.json` with new public works linked to **ORCID `0009-0002-2907-8998`** via OpenAlex. Direct ORCID public API access is optional. Existing hand-reviewed papers remain present even when scholarly APIs are slow or incomplete.
- `assets/github-activity.svg`: contribution calendar and aggregate commit/PR/issue counts via GitHub GraphQL (previous 12 months, subject to token visibility).
- `assets/github-languages.svg`: languages determined by byte counts from public, owned, non-fork, non-archived repositories. **Private repositories are explicitly excluded**, including when a more privileged token is configured.

The `assets/profile-header.svg`, project descriptions and About section are maintained manually and are never rewritten by the job. All SVG is self-contained; no third-party card-hosting service is needed.

## Enabling the scheduled workflow

1. Copy all files including the hidden `.github` directory to the profile repository `AlessandroRongoni/AlessandroRongoni` on a feature branch and open a pull request.
2. Merge the branch into `main` (scheduled GitHub Actions run from the **default** branch).
3. Ensure repository **Settings → Actions → General** permits Actions, with workflow write permissions where needed; branch protection/rulesets can block a workflow push.
4. Open **Actions → Update profile data → Run workflow** to populate cards without waiting for the schedule.
5. The job is scheduled daily at 03:17 UTC (12:17 JST). GitHub can delay schedules or disable schedules for inactive public repositories.

## Optional secrets

Configure **Settings → Secrets and variables → Actions** as needed:

| Secret | Purpose | Required |
|---|---|---|
| `PROFILE_STATS_TOKEN` | More complete authenticated GraphQL contribution visibility | No |
| `ORCID_PUBLIC_TOKEN` | ORCID public `/read-public` access token | No |
| `ORCID_CLIENT_ID` + `ORCID_CLIENT_SECRET` | ORCID public API client credentials, used instead of a fixed access token | No |
| `OPENALEX_API_KEY` | Increased OpenAlex API budget | No |

Basic GitHub statistics use the workflow's `GITHUB_TOKEN`; the OpenAlex query can run without an API key. A personal token is **not** embedded in SVG or README. If you set `PROFILE_STATS_TOKEN`, apply the minimum permissions required and review access to organization resources carefully.

To count qualifying **private contributions anonymously on GitHub's own calendar**, enable **Profile → Contribution settings → Private contributions**. With the Actions-provided `GITHUB_TOKEN`, the embedded custom chart may not expose all private activity from other repositories. `PROFILE_STATS_TOKEN` may extend coverage, but actual counts are governed by GitHub API permissions, organizational policies and contribution eligibility. Do not assume the private work is fully represented unless you compare the numbers.

## Manual publications

If a recent paper is missing from scholarly indexes, add it to `data/publications.json` with the accurate `title`, `year`, `venue` and either `doi` or an `https://` `url`. Optional `note` can specify `First author`, etc. Never add a paper solely on the basis of an unverified title.

## Local verification

```bash
python3 -m unittest discover -s tests -v
python3 scripts/sync_profile.py  # uses live public APIs; optional GitHub token
```

Changes in the generated data are committed only when the actual content changes. Errors preserve existing SVGs and publication content; no fake activity counts are generated.
