#!/bin/bash
# Final verification of all services and domains

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }

echo ""
echo "══════════════════════════════════════"
echo "  Dimentos AI — Server Verification"
echo "══════════════════════════════════════"
echo ""

echo "▶ DNS Records:"
for host in dimentosai.uz www.dimentosai.uz panel.dimentosai.uz api.dimentosai.uz n8n.dimentosai.uz bot.dimentosai.uz admin.dimentosai.uz; do
    ip=$(dig +short $host A 2>/dev/null | head -1)
    if [ "$ip" = "185.196.212.52" ]; then
        ok "$host → $ip"
    else
        fail "$host → '$ip'"
    fi
done

echo ""
echo "▶ HTTP/HTTPS:"
for url in http://dimentosai.uz https://dimentosai.uz https://www.dimentosai.uz https://n8n.dimentosai.uz; do
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 8 "$url" 2>/dev/null)
    if [[ "$code" =~ ^(200|301|302|401)$ ]]; then
        ok "$url → HTTP $code"
    else
        fail "$url → HTTP $code"
    fi
done

echo ""
echo "▶ Nginx:"
if nginx -t 2>/dev/null; then
    ok "nginx -t passed"
else
    fail "nginx config error"
fi
status=$(systemctl is-active nginx)
[ "$status" = "active" ] && ok "nginx is $status" || fail "nginx is $status"

echo ""
echo "▶ Docker:"
if docker ps &>/dev/null; then
    ok "docker running"
    docker ps --format "  • {{.Names}} — {{.Status}}" 2>/dev/null
else
    fail "docker not accessible"
fi

echo ""
echo "▶ SSL Certificates:"
certbot certificates 2>/dev/null | grep -E "(Found|Domains|Expiry|VALID)" | sed 's/^/  /'

echo ""
echo "▶ Firewall:"
ufw status | grep -E "(Status|22|80|443)" | sed 's/^/  /'

echo ""
echo "══════════════════════════════════════"
