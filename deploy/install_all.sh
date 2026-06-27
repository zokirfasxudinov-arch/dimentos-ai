#!/bin/bash
# Full server setup for dimentosai.uz — run as root
# Usage: bash install_all.sh

set -e
cd "$(dirname "$0")"

bash 01_server_setup.sh
bash 02_nginx_setup.sh

echo ""
echo "══════════════════════════════════════════"
echo "  Nginx is ready. Now:"
echo "  1. Add DNS A-records in AHost:"
echo "     panel, api, n8n, bot, admin → 185.196.212.52"
echo "  2. Wait 5-30 minutes for DNS propagation"
echo "  3. Run: bash 03_ssl_setup.sh"
echo "  4. Run: bash 04_n8n_setup.sh"
echo "  5. Run: bash 05_verify.sh"
echo "══════════════════════════════════════════"
