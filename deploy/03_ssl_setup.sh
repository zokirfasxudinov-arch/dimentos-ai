#!/bin/bash
# SSL certificates via Let's Encrypt for all dimentosai.uz domains
# Run AFTER DNS has propagated (check with: dig panel.dimentosai.uz)

set -e
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log() { echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

EMAIL="zokirfasxudinov@gmail.com"
DOMAIN="dimentosai.uz"

log "=== Checking DNS propagation ==="
for sub in "" "www." "panel." "api." "n8n." "bot." "admin."; do
    host="${sub}${DOMAIN}"
    ip=$(dig +short $host A | head -1)
    if [ "$ip" = "185.196.212.52" ]; then
        echo "  ✓ $host → $ip"
    else
        warn "  ✗ $host → '$ip' (expected 185.196.212.52)"
    fi
done

echo ""
read -p "DNS looks good? Continue with SSL? (y/N) " confirm
[ "$confirm" != "y" ] && echo "Aborted." && exit 0

log "=== Getting SSL certificates ==="

# Main domain + www
certbot --nginx \
    -d dimentosai.uz \
    -d www.dimentosai.uz \
    --non-interactive \
    --agree-tos \
    --email $EMAIL \
    --redirect

# panel
certbot --nginx \
    -d panel.dimentosai.uz \
    --non-interactive --agree-tos --email $EMAIL --redirect

# api
certbot --nginx \
    -d api.dimentosai.uz \
    --non-interactive --agree-tos --email $EMAIL --redirect

# n8n
certbot --nginx \
    -d n8n.dimentosai.uz \
    --non-interactive --agree-tos --email $EMAIL --redirect

# bot
certbot --nginx \
    -d bot.dimentosai.uz \
    --non-interactive --agree-tos --email $EMAIL --redirect

# admin
certbot --nginx \
    -d admin.dimentosai.uz \
    --non-interactive --agree-tos --email $EMAIL --redirect

log "=== Testing auto-renewal ==="
certbot renew --dry-run

log "=== Certificates installed ==="
certbot certificates

log "=== SSL setup complete! ==="
