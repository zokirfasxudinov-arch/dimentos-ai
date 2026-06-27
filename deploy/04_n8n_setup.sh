#!/bin/bash
# n8n setup on new server
# Run after SSL is configured

set -e
GREEN='\033[0;32m'; NC='\033[0m'
log() { echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $1"; }

mkdir -p /opt/dimentosai/n8n

# Generate secure credentials
N8N_PASS=$(openssl rand -base64 20 | tr -dc 'a-zA-Z0-9' | head -c 20)
ENCRYPTION_KEY=$(openssl rand -hex 32)

# Create .env file (600 permissions)
cat > /opt/dimentosai/n8n/.env <<EOF
N8N_BASIC_AUTH_ACTIVE=true
N8N_BASIC_AUTH_USER=dimentos
N8N_BASIC_AUTH_PASSWORD=${N8N_PASS}
N8N_HOST=n8n.dimentosai.uz
N8N_PORT=5678
N8N_PROTOCOL=https
WEBHOOK_URL=https://n8n.dimentosai.uz/
GENERIC_TIMEZONE=Asia/Tashkent
TZ=Asia/Tashkent
N8N_ENCRYPTION_KEY=${ENCRYPTION_KEY}
N8N_LOG_LEVEL=warn
N8N_SECURE_COOKIE=true
EOF
chmod 600 /opt/dimentosai/n8n/.env

# Create docker-compose
cat > /opt/dimentosai/n8n/docker-compose.yml <<'COMPOSE'
version: '3.9'

services:
  n8n:
    image: n8nio/n8n:latest
    container_name: dimentosai_n8n
    restart: unless-stopped
    ports:
      - "127.0.0.1:5678:5678"
    env_file: .env
    volumes:
      - n8n_data:/home/node/.n8n
      - ./logs:/home/node/.n8n/logs

volumes:
  n8n_data:
COMPOSE

mkdir -p /opt/dimentosai/n8n/logs

log "Starting n8n..."
cd /opt/dimentosai/n8n
docker compose up -d

sleep 5
if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5678 | grep -q "200\|401\|302"; then
    log "✓ n8n is running on 127.0.0.1:5678"
else
    log "⚠ n8n may still be starting, check: docker logs dimentosai_n8n"
fi

log ""
log "=== n8n credentials ==="
log "URL: https://n8n.dimentosai.uz"
log "User: dimentos"
log "Password: ${N8N_PASS}"
log "(saved in /opt/dimentosai/n8n/.env)"
