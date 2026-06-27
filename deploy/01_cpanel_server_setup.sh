#!/bin/bash
# Server setup for cPanel/WHM VPS
# Run in WHM Terminal OR via SSH after enabling it
# Compatible with cPanel CSF firewall

set -e
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

log "=== Dimentos AI — cPanel VPS Setup ==="

# ── Timezone ──────────────────────────────────────────────────────────────
log "STEP 1: Timezone"
timedatectl set-timezone Asia/Tashkent
log "Timezone: $(timedatectl | grep 'Time zone')"

# ── System update ─────────────────────────────────────────────────────────
log "STEP 2: System packages"
yum install -y curl wget git unzip 2>/dev/null || \
apt-get install -y curl wget git unzip 2>/dev/null || true

# ── Docker ────────────────────────────────────────────────────────────────
log "STEP 3: Docker"
if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi
docker --version

# ── Docker Compose ────────────────────────────────────────────────────────
log "STEP 4: Docker Compose"
if ! command -v docker-compose &>/dev/null; then
    curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
         -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi
docker compose version

# ── CSF Firewall — open ports ─────────────────────────────────────────────
log "STEP 5: Firewall (CSF)"
if command -v csf &>/dev/null; then
    # Allow ports in CSF
    csf -a 127.0.0.1 "loopback" 2>/dev/null || true
    # Verify TCP_IN has 80,443
    grep "^TCP_IN" /etc/csf/csf.conf || true
    log "CSF is active. Make sure ports 80,443 are in TCP_IN in /etc/csf/csf.conf"
else
    warn "CSF not found, assuming firewall managed elsewhere"
fi

# ── Create directories ────────────────────────────────────────────────────
log "STEP 6: Create /opt/dimentosai"
mkdir -p /opt/dimentosai/{n8n,logs}
chmod 750 /opt/dimentosai

log "=== DONE. Next: run 04_n8n_setup.sh ==="
log "=== Then configure Nginx/Apache from WHM for subdomains ==="
