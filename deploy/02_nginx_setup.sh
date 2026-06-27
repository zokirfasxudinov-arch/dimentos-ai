#!/bin/bash
# Nginx configuration for all dimentosai.uz domains
# Run after 01_server_setup.sh

set -e
GREEN='\033[0;32m'; NC='\033[0m'
log() { echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $1"; }

DOMAIN="dimentosai.uz"

log "=== Creating Nginx configs ==="

# ── Main domain — temporary landing page ──────────────────────────────────
cat > /etc/nginx/sites-available/dimentosai_main <<'NGINX'
server {
    listen 80;
    server_name dimentosai.uz www.dimentosai.uz;

    root /var/www/dimentosai;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
}
NGINX

# ── panel.dimentosai.uz — future web panel (stub) ─────────────────────────
cat > /etc/nginx/sites-available/dimentosai_panel <<'NGINX'
server {
    listen 80;
    server_name panel.dimentosai.uz;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        # Will proxy to port 3000 when panel is deployed
        return 200 '{"service":"panel","status":"coming_soon"}';
        add_header Content-Type application/json;
    }
}
NGINX

# ── api.dimentosai.uz — future FastAPI backend ────────────────────────────
cat > /etc/nginx/sites-available/dimentosai_api <<'NGINX'
server {
    listen 80;
    server_name api.dimentosai.uz;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        # Will proxy to port 8001 when API is deployed
        return 200 '{"service":"api","status":"coming_soon","version":"1.0"}';
        add_header Content-Type application/json;
    }
}
NGINX

# ── n8n.dimentosai.uz — n8n workflow engine ──────────────────────────────
cat > /etc/nginx/sites-available/dimentosai_n8n <<'NGINX'
server {
    listen 80;
    server_name n8n.dimentosai.uz;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        proxy_pass http://127.0.0.1:5678;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support for n8n
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 300;
    }
}
NGINX

# ── bot.dimentosai.uz — Telegram webhook ─────────────────────────────────
cat > /etc/nginx/sites-available/dimentosai_bot <<'NGINX'
server {
    listen 80;
    server_name bot.dimentosai.uz;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        # Will proxy to Telegram bot webhook when deployed
        return 200 '{"service":"bot","status":"coming_soon"}';
        add_header Content-Type application/json;
    }
}
NGINX

# ── admin.dimentosai.uz — admin panel ────────────────────────────────────
cat > /etc/nginx/sites-available/dimentosai_admin <<'NGINX'
server {
    listen 80;
    server_name admin.dimentosai.uz;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        return 200 '{"service":"admin","status":"coming_soon"}';
        add_header Content-Type application/json;
    }
}
NGINX

# Create landing page
mkdir -p /var/www/dimentosai
cat > /var/www/dimentosai/index.html <<'HTML'
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dimentos AI</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    min-height:100vh; display:flex; align-items:center; justify-content:center;
    background:linear-gradient(135deg,#0f0f23 0%,#1a1a3e 50%,#0f1a0f 100%);
    font-family:'Segoe UI',sans-serif; color:#fff;
  }
  .card {
    text-align:center; padding:60px 40px; max-width:600px;
    background:rgba(255,255,255,0.05); border-radius:24px;
    border:1px solid rgba(255,255,255,0.1);
    backdrop-filter:blur(20px);
  }
  .logo { font-size:56px; margin-bottom:16px; }
  h1 { font-size:2.4em; font-weight:700; margin-bottom:12px;
       background:linear-gradient(90deg,#00d4aa,#0088ff,#7c3aed);
       -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
  .subtitle { font-size:1.1em; color:#94a3b8; margin-bottom:32px; line-height:1.6; }
  .status {
    display:inline-block; padding:8px 20px; border-radius:50px;
    background:rgba(0,212,170,0.15); border:1px solid rgba(0,212,170,0.3);
    color:#00d4aa; font-size:0.9em; font-weight:600;
  }
  .dot { display:inline-block; width:8px; height:8px; border-radius:50%;
         background:#00d4aa; margin-right:8px;
         animation:pulse 2s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
</style>
</head>
<body>
<div class="card">
  <div class="logo">🤖</div>
  <h1>Dimentos AI</h1>
  <p class="subtitle">AI-powered automation platform.<br>Dimentos AI работает. Сервер успешно подключен к домену dimentosai.uz</p>
  <span class="status"><span class="dot"></span>Platform Online</span>
</div>
</body>
</html>
HTML

# Enable all sites
log "=== Enabling Nginx sites ==="
for site in dimentosai_main dimentosai_panel dimentosai_api dimentosai_n8n dimentosai_bot dimentosai_admin; do
    ln -sf /etc/nginx/sites-available/$site /etc/nginx/sites-enabled/$site
    log "  Enabled: $site"
done

# Remove default
rm -f /etc/nginx/sites-enabled/default

# Test and reload
nginx -t
systemctl reload nginx
log "=== Nginx configured. Run 03_ssl_setup.sh after DNS propagates ==="
