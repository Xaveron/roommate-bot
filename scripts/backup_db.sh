#!/usr/bin/env bash
# Dump the production PostgreSQL database (docker-compose.prod.yml) into backups/.
# Keeps the newest $KEEP dumps (default 14). Safe to run by hand or from cron.
set -euo pipefail

cd "$(dirname "$0")/.."
BACKUP_DIR="${BACKUP_DIR:-$PWD/backups}"
KEEP="${KEEP:-14}"
compose=(docker compose -f docker-compose.prod.yml)

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
target="$BACKUP_DIR/roommate-$(date -u +%Y%m%d-%H%M%S).dump"
partial="$target.partial"
trap 'rm -f "$partial"' EXIT

# Custom format: compressed, restorable table by table with pg_restore.
"${compose[@]}" exec -T postgres pg_dump -U roommate -d roommate --format=custom --no-owner >"$partial"
# Make sure the archive is readable before it replaces anything.
"${compose[@]}" exec -T postgres pg_restore --list <"$partial" >/dev/null
mv "$partial" "$target"
chmod 600 "$target"

# Rotation: drop everything but the newest $KEEP dumps.
find "$BACKUP_DIR" -maxdepth 1 -name 'roommate-*.dump' -printf '%T@ %p\n' \
  | sort -rn | tail -n +"$((KEEP + 1))" | cut -d' ' -f2- | xargs -r rm --

echo "$(date -Is) backup ok: $target ($(du -h "$target" | cut -f1))"
