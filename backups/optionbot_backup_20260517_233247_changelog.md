# OptionBot Backup Changelog
# Backup: optionbot_backup_20260517_233247.zip
# Date: 2026-05-17 23:32

## Description
Backup before attempting the full public-launch promotion package that includes
the new landing/auth/contact work plus previously built billing and portfolio
work that has not gone live.

## Intended Follow-Up Work
- Reconcile preserved billing and portfolio work with the current landing/auth
  shadow changes.
- Run full local checks before any production deployment.
- Prepare rollback notes and smoke checks for the combined release.

## Notes
- Production remains untouched at backup time.
- This package may touch frontend, backend API, billing, portfolio workflow, and
  database migration `007`.
