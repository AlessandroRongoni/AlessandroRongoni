# Deploy this GitHub profile

This ZIP contains the **contents of the root of** `AlessandroRongoni/AlessandroRongoni`. Do not put the files inside another `github-profile-v3/` folder.

## Recommended: feature branch and pull request

Clone the **profile** repository into a clean directory, then:

```bash
git clone https://github.com/AlessandroRongoni/AlessandroRongoni.git
cd AlessandroRongoni
git switch -c feat/profile-v3
unzip /path/to/AlessandroRongoni-github-profile-v3.zip -d .
git add -A
git commit -m "feat: redesign profile and automate publications and stats"
git push --set-upstream origin feat/profile-v3
```

In GitHub, open a PR from `feat/profile-v3` into `main`, inspect the rendered README, then merge. The ZIP includes a hidden `.github/workflows/` directory; **do not omit that directory**. If the repository already contains user-made changes, review the diff before committing.

## After the merge

1. Open **Actions** and find **Update profile data**.
2. Click **Run workflow** (branch `main`) to request the first refresh. The two SVG statistic cards contain navigation text until a successful first refresh; they do not fabricate counts.
3. Check the workflow log and verify both SVG cards and the publications section.
4. Optional: **Contribution settings → Private contributions** on your GitHub profile to show qualifying anonymized private contributions. See `AUTOMATION.md` for token scope and limitations.

The action refreshes public publication metadata, GitHub contributions and public repository language composition daily. Its output is committed only if content changed. Source code of private repositories is never published.
