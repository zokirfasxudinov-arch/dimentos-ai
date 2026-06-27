#!/bin/bash
# Server initial setup for 185.196.212.52
# Run as root: bash 01_server_setup.sh

set -e

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log() { echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

log "=== STEP 1: System Update ==="
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y curl wget git unzip software-properties-common apt-transport-https ca-certificates gnupg lsb-release

log "=== STEP 2: Timezone ==="
timedatectl set-timezone Asia/Tashkent
log "Timezone: $(timedatectl | grep 'Time zone')"

log "=== STEP 3: Nginx ==="
apt-get install -y nginx
systemctl enable nginx
systemctl start nginx

log "=== STEP 4: Certbot ==="
apt-get install -y certbot python3-certbot-nginx

log "=== STEP 5: Docker ==="
if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | sh
fi
systemctl enable docker
systemctl start docker
docker --version

log "=== STEP 6: Docker Compose ==="
if ! command -v docker-compose &>/dev/null; then
    curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi
docker compose version

log "=== STEP 7: UFW Firewall ==="
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'
ufw --force enable
ufw status

log "=== STEP 8: Create directories ==="
mkdir -p /opt/dimentosai/{n8n,nginx,logs,ssl}
chmod 750 /opt/dimentosai

log "=== Setup complete! Next: run 02_nginx_setup.sh ==="
