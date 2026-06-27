#!/bin/bash
# Setup Nginx vhosts on cPanel server via WHM API or direct file
# cPanel uses Apache by default. If WHM has Nginx (via cpnginx), use that.
# Otherwise: use Apache .htaccess + ProxyPass OR configure Nginx as reverse proxy

set -e
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

# Detect web server
if systemctl is-active nginx &>/dev/null; then
    WEB=nginx
    log "Web server: Nginx"
elif systemctl is-active httpd &>/dev/null || systemctl is-active apache2 &>/dev/null; then
    WEB=apache
    log "Web server: Apache"
else
    warn "Could not detect web server"
    WEB=nginx
fi

DOMAIN="dimentosai.uz"

if [ "$WEB" = "nginx" ]; then
    # ── Nginx configs ──────────────────────────────────────────────────────

    # Landing page
    mkdir -p /var/www/dimentosai
    cat > /var/www/dimentosai/index.html <<'HTML'
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dimentos AI</title>
<style>
  body{min-height:100vh;display:flex;align-items:center;justify-content:center;
       background:linear-gradient(135deg,#0f0f23,#1a1a3e,#0f1a0f);font-family:'Segoe UI',sans-serif;color:#fff;margin:0}
  .card{text-align:center;padding:60px 40px;max-width:600px;
        background:rgba(255,255,255,.05);border-radius:24px;border:1px solid rgba(255,255,255,.1)}
  h1{font-size:2.4em;background:linear-gradient(90deg,#00d4aa,#0088ff,#7c3aed);
     -webkit-background-clip:text;-webkit-text-fill-color:transparent}
  .dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#00d4aa;
       margin-right:8px;animation:pulse 2s infinite}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
</style>
</head>
<body>
<div class="card">
  <div style="font-size:56px">🤖</div>
  <h1>Dimentos AI</h1>
  <p style="color:#94a3b8;margin:16px 0 32px">AI-powered automation platform.<br>
  Сервер успешно подключен к домену dimentosai.uz</p>
  <span style="padding:8px 20px;border-radius:50px;background:rgba(0,212,170,.15);
        border:1px solid rgba(0,212,170,.3);color:#00d4aa;font-size:.9em">
    <span class="dot"></span>Platform Online
  </span>
</div>
</body>
</html>
HTML

    # Write nginx site configs
    NGINX_SITES=/etc/nginx/sites-available
    [ -d /etc/nginx/conf.d ] && NGINX_SITES=/etc/nginx/conf.d && EXT=".conf" || EXT=""

    for sub in panel api bot admin; do
        cat > ${NGINX_SITES}/dimentosai_${sub}${EXT} <<NGINX
server {
    listen 80;
    server_name ${sub}.${DOMAIN};
    location /.well-known/acme-challenge/ { root /var/www/html; }
    location / {
        return 200 '{"service":"${sub}","status":"coming_soon"}';
        add_header Content-Type application/json;
    }
}
NGINX
    done

    # n8n with WebSocket support
    cat > ${NGINX_SITES}/dimentosai_n8n${EXT} <<'NGINX'
server {
    listen 80;
    server_name n8n.dimentosai.uz;
    location /.well-known/acme-challenge/ { root /var/www/html; }
    location / {
        proxy_pass http://127.0.0.1:5678;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 300;
    }
}
NGINX

    cat > ${NGINX_SITES}/dimentosai_main${EXT} <<NGINX
server {
    listen 80;
    server_name ${DOMAIN} www.${DOMAIN};
    root /var/www/dimentosai;
    index index.html;
    location /.well-known/acme-challenge/ { root /var/www/html; }
    location / { try_files \$uri \$uri/ =404; }
}
NGINX

    # Enable sites (if sites-available/enabled pattern)
    if [ -d /etc/nginx/sites-enabled ]; then
        for site in dimentosai_main dimentosai_panel dimentosai_api dimentosai_n8n dimentosai_bot dimentosai_admin; do
            ln -sf /etc/nginx/sites-available/$site /etc/nginx/sites-enabled/$site 2>/dev/null || true
        done
        rm -f /etc/nginx/sites-enabled/default
    fi

    nginx -t && systemctl reload nginx
    log "Nginx configured"

elif [ "$WEB" = "apache" ]; then
    warn "Apache detected. You need to:"
    warn "1. In WHM: use Apache vhosts"
    warn "2. OR install nginx as reverse proxy from WHM plugins"
    warn "3. OR: install standalone nginx on port 8080, then proxy"
fi

log "=== Now run: bash 03_ssl_setup.sh ==="
