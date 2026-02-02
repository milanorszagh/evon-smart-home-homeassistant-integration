# Release Process

This document describes how to create releases for the Evon Smart Home integration.

## Prerequisites

- GitHub CLI (`gh`) installed and authenticated
- Push access to the repository

## Regular Release (from main)

Use this for planned releases where all changes are already on `main`.

```bash
# 1. Update version in manifest.json
edit custom_components/evon/manifest.json  # Change "version": "X.Y.Z"

# 2. Commit the version bump
git add custom_components/evon/manifest.json
git commit -m "Release vX.Y.Z"
git push origin main

# 3. Create and push tag
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z

# 4. Create GitHub release
gh release create vX.Y.Z --title "vX.Y.Z - Title" --notes "Release notes here"
```

## Hotfix Release (from previous tag)

Use this when you need to release a fix without including unreleased changes from `main`.

```bash
# 1. Create release branch from the previous tag
git checkout -b release/vX.Y.Z vX.Y.(Z-1)

# 2. Make your fixes or cherry-pick commits
git cherry-pick <commit-hash>
# or make changes directly

# 3. Update version in manifest.json
edit custom_components/evon/manifest.json  # Change "version": "X.Y.Z"

# 4. Commit
git add -A
git commit -m "Fix description (vX.Y.Z)"

# 5. Create and push tag (NOT the branch)
git tag -a vX.Y.Z -m "Fix description"
git push origin vX.Y.Z

# 6. Create GitHub release
gh release create vX.Y.Z --title "vX.Y.Z - Title" --notes "Release notes here"

# 7. Switch back to main and DELETE the release branch
git checkout main
git branch -D release/vX.Y.Z

# 8. Apply the same fix to main (if not already there)
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
- [ ] All tests pass (`python3 -m pytest tests/`)
- [ ] Version updated in `manifest.json`
- [ ] Changes tested on real hardware (if applicable)

After releasing:
- [ ] GitHub release created with release notes
- [ ] Release branch deleted (for hotfixes)
- [ ] Verify release appears in HACS
