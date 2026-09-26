#!/usr/bin/env bash
# Restore the production database from a dump made by backup_db.sh.
#   scripts/restore_db.sh backups/roommate-20260926-033000.dump
# Takes a safety backup first, stops the bot during the restore and starts it again.
set -euo pipefail

dump="${1:?usage: scripts/restore_db.sh <file.dump>}"
[[ -f "$dump" ]] || { echo "No such file: $dump" >&2; exit 1; }
dump="$(realpath "$dump")"

cd "$(dirname "$0")/.."
compose=(docker compose -f docker-compose.prod.yml)

if [[ "${FORCE:-}" != "1" ]]; then
  read -r -p "Replace the current database with $(basename "$dump")? Type 'yes': " answer
  [[ "$answer" == "yes" ]] || { echo "Aborted."; exit 1; }
fi

echo "Safety backup of the current state..."
scripts/backup_db.sh

"${compose[@]}" stop bot
trap '"${compose[@]}" start bot' EXIT
"${compose[@]}" exec -T postgres pg_restore -U roommate -d roommate \
  --clean --if-exists --no-owner --single-transaction <"$dump"
echo "Restored from $dump. Starting the bot..."
