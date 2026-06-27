#!/bin/bash
# Backup script for Dimentos AI Studio OS
# Backs up: PostgreSQL database + Obsidian vault

set -e
BACKUP_DIR="/opt/dimentos-ai/backups"
DATE=$(date +%Y-%m-%d_%H-%M)
mkdir -p "$BACKUP_DIR"

source /opt/dimentos-ai/.env 2>/dev/null || true

echo "📦 Dimentos AI - Backup $DATE"

# PostgreSQL backup
if docker compose -f /opt/dimentos-ai/docker-compose.yml ps postgres | grep -q "Up"; then
  docker compose -f /opt/dimentos-ai/docker-compose.yml exec -T postgres \
    pg_dump -U "${POSTGRES_USER:-dimentos}" "${POSTGRES_DB:-dimentos_ai}" \
    > "$BACKUP_DIR/db_$DATE.sql"
  echo "✓ Database backed up: db_$DATE.sql"
fi

# Obsidian vault backup
tar -czf "$BACKUP_DIR/vault_$DATE.tar.gz" -C /opt/dimentos-ai obsidian-vault/
echo "✓ Vault backed up: vault_$DATE.tar.gz"

# Cleanup: keep last 7 days
find "$BACKUP_DIR" -name "*.sql" -mtime +7 -delete
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +7 -delete
echo "✓ Old backups cleaned"

echo "✅ Backup complete: $BACKUP_DIR"
