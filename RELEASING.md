# Release Process

This document describes how to create releases for the Evon Smart Home integration.

## Prerequisites

- GitHub CLI (`gh`) installed and authenticated
- Push access to the repository

## Regular Release (from main)

Use this for planned releases where all changes are already on `main`.

```bash
# 1. Update version in ALL FOUR files (they must match!)
#    - custom_components/evon/manifest.json
#    - pyproject.toml
#    - package.json
#    - package-lock.json (run: npm install --package-lock-only)
edit custom_components/evon/manifest.json  # Change "version": "X.Y.Z"
edit pyproject.toml                         # Change version = "X.Y.Z"
edit package.json                           # Change "version": "X.Y.Z"
npm install --package-lock-only             # Sync package-lock.json

# 2. Commit the version bump AND the changelog entries
#    - CHANGELOG.md: the version's section must exist; replace "Unreleased" in its
#      heading with today's date and point its compare link at the tag
#    - README.md: one row in the Version History table (version, date, highlights)
#    (the release tag must contain both — HACS renders README from the tag)
git add custom_components/evon/manifest.json pyproject.toml package.json package-lock.json CHANGELOG.md README.md
git commit -m "Release vX.Y.Z"
git push origin main

# 3. Create and push tag
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z

# 4. Create GitHub release — notes are the version's CHANGELOG.md section
awk '/^## \[X.Y.Z\]/{flag=1;next} /^## \[/{flag=0} flag' CHANGELOG.md > /tmp/release-notes.md
gh release create vX.Y.Z --title "Descriptive title here" --notes-file /tmp/release-notes.md
# NOTE: Do NOT include the version in the title — HACS auto-prepends the tag.
```

## Hotfix Release (from previous tag)

Use this when you need to release a fix without including unreleased changes from `main`.

```bash
# 1. Create release branch from the previous tag
git checkout -b release/vX.Y.Z vX.Y.(Z-1)

# 2. Make your fixes or cherry-pick commits
git cherry-pick <commit-hash>
# or make changes directly

# 3. Update version in ALL FOUR files
edit custom_components/evon/manifest.json  # Change "version": "X.Y.Z"
edit pyproject.toml                         # Change version = "X.Y.Z"
edit package.json                           # Change "version": "X.Y.Z"
npm install --package-lock-only             # Sync package-lock.json

# 4. Commit the version bump AND the changelog entries, as in a regular release
#    - CHANGELOG.md: add a dated section for X.Y.Z with its compare link
#      (vX.Y.(Z-1)...vX.Y.Z); the release notes are taken from it in step 6
#    - README.md: one row in the Version History table (version, date, highlights)
#    (the release tag must contain both — HACS renders README from the tag)
git add custom_components/evon/manifest.json pyproject.toml package.json package-lock.json CHANGELOG.md README.md
git add <any fix files not already committed>
git commit -m "Release vX.Y.Z"

# 5. Create and push tag (NOT the branch)
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z

# 6. Create GitHub release — notes are the version's CHANGELOG.md section
awk '/^## \[X.Y.Z\]/{flag=1;next} /^## \[/{flag=0} flag' CHANGELOG.md > /tmp/release-notes.md
gh release create vX.Y.Z --title "Descriptive title here" --notes-file /tmp/release-notes.md
# NOTE: Do NOT include the version in the title — HACS auto-prepends the tag.

# 7. Switch back to main and DELETE the release branch
git checkout main
git branch -D release/vX.Y.Z

# 8. Apply the same fix to main (if not already there), including the CHANGELOG.md
#    section and the README row, so main's history stays complete
# Either cherry-pick or manually apply the changes
```

## HACS Compatibility

HACS automatically picks up releases based on:
- **GitHub releases** (not branches)
- **Tags** matching the version in `manifest.json`

The `hacs.json` file in the repo root configures HACS behavior.

## Version Numbering

We use semantic versioning: `MAJOR.MINOR.PATCH`

- **MAJOR**: Breaking changes
- **MINOR**: New features (backwards compatible)
- **PATCH**: Bug fixes (backwards compatible)

Examples:
- `1.14.0` → `1.15.0` (new feature)
- `1.14.0` → `1.14.1` (bug fix)
- `1.14.1` → `1.14.2` (another bug fix)

## Checklist

Before releasing:
- [ ] All tests pass (`python3.14 -m pytest tests/` — 3.14 is required, see DEVELOPMENT.md)
- [ ] Version updated in ALL FOUR files: `manifest.json`, `pyproject.toml`, `package.json`, `package-lock.json`
- [ ] Linting passes (`ruff check custom_components/evon/ tests/ && ruff format --check custom_components/evon/ tests/ && npm run lint`)
- [ ] TypeScript builds (`npm run build`)
- [ ] MCP tests pass (`npm run test:mcp`)
- [ ] Mypy passes or errors are tracked (`mypy custom_components/evon/ --ignore-missing-imports`)
- [ ] `npm audit --audit-level=moderate` clean. CI only fails the build at `--audit-level=high`;
      the stricter local threshold is recommended so moderate advisories are dealt with
      before they escalate.
- [ ] hassfest passes locally, as it does in CI
      (`docker run --rm --platform linux/amd64 -v "$PWD":/github/workspace ghcr.io/home-assistant/hassfest`)
- [ ] `pip-audit -r requirements-test.txt` reviewed. Advisory only, like the CI step:
      Home Assistant hard-pins its dependencies (e.g. `cryptography==48.0.1`), so
      findings there usually cannot be fixed downstream and clear when HA bumps them.
      Check that each finding is HA-pinned rather than something we actually control.
- [ ] Changes tested on real hardware (if applicable)
- [ ] Documentation updated (CHANGELOG.md section with date, README.md version row, DEVELOPMENT.md / AGENTS.md as needed)

After releasing:
- [ ] GitHub release created with release notes
- [ ] Release branch deleted (for hotfixes)
- [ ] Verify release appears in HACS
