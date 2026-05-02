# Backup Process

Read `AGENTS.md` and `CURRENT_STATE.md` first; no code changes without my approval.

This repository uses a simple backup convention before meaningful change work:

- create a timestamped zip archive inside `backups/`
- create a matching changelog markdown file beside it
- do this before code changes, auth changes, schema changes, or landing-page rework

## Naming Convention

- Zip: `backups/optionbot_backup_YYYYMMDD_HHMMSS.zip`
- Changelog: `backups/optionbot_backup_YYYYMMDD_HHMMSS_changelog.md`

## What to Exclude

Exclude transient or generated files where practical:

- `.git/`
- previous `backups/`
- `__pycache__/`
- `.pytest_cache/`
- `frontend/.next/`
- `frontend/node_modules/`
- `bot.log`
- `bot.pid`

## Minimal Changelog Template

```md
# OptionBot Backup Changelog
# Backup: optionbot_backup_YYYYMMDD_HHMMSS.zip
# Date: YYYY-MM-DD HH:MM

## Description
Short reason for the backup.

## Intended Follow-Up Work
- Item 1
- Item 2

## Notes
- Anything important about scope or exclusions
```

## Example Command

Run from project root:

```bash
ts=$(date +%Y%m%d_%H%M%S)
zip_path="backups/optionbot_backup_${ts}.zip"
changelog_path="backups/optionbot_backup_${ts}_changelog.md"

zip -r "$zip_path" . \
  -x "./backups/*" "./.git/*" "./__pycache__/*" "./.pytest_cache/*" \
     "./bot.log" "./bot.pid" "./frontend/.next/*" "./frontend/node_modules/*" \
     "./backend/__pycache__/*" "./core/__pycache__/*" "./data/__pycache__/*" \
     "./output/__pycache__/*" "./strategies/__pycache__/*"
```

Then create the matching changelog markdown file.

## Current Latest Backup

At the time this file was added, the latest backup created for current work was:

- `backups/optionbot_backup_20260502_182441.zip`
- `backups/optionbot_backup_20260502_182441_changelog.md`

