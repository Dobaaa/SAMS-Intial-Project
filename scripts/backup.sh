#!/usr/bin/env bash
set -euo pipefail
cd /tmp

BACKUP_DIR="/backups"
DB_NAME="sams_db"
DB_USER="${DB_USER:-postgres}"
DATE_TAG="$(date +%F_%H-%M-%S)"
OUTPUT_FILE="${BACKUP_DIR}/sams_${DATE_TAG}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "Creating PostgreSQL backup: ${OUTPUT_FILE}"
pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$OUTPUT_FILE"

echo "Cleaning backups older than 30 days..."
find "$BACKUP_DIR" -name "sams_*.sql.gz" -type f -mtime +30 -delete

echo "Backup completed successfully."

# Suggested cron (daily at 2am):
# 0 2 * * * /bin/bash /var/www/sams/scripts/backup.sh >> /var/log/sams/backup.log 2>&1
