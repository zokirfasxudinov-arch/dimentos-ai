#!/bin/bash
# Dimentos AI Studio OS - First-time setup script
# Run once after cloning the repo

set -e

echo "🚀 Dimentos AI Studio OS — Setup"
echo "=================================="

# 1. Create .env from example
if [ ! -f .env ]; then
  cp .env.example .env
  echo "✓ Created .env from .env.example"
  echo ""
  echo "⚠️  IMPORTANT: Fill in your credentials in .env:"
  echo "   - TELEGRAM_OWNER_ID (your Telegram user ID)"
  echo "   - GITHUB_TOKEN (Personal Access Token from github.com/settings/tokens)"
  echo "   - API_SECRET_KEY (run: openssl rand -hex 32)"
  echo "   - Any AI provider keys you want to use"
  echo ""
else
  echo "⚠️  .env already exists, skipping"
fi

# 2. Install git pre-commit hook
if [ -d .git ]; then
  cp scripts/check_secrets.sh .git/hooks/pre-commit
  chmod +x .git/hooks/pre-commit
  echo "✓ Pre-commit security hook installed"
fi

# 3. Create log directories
mkdir -p logs backups
echo "✓ Log directories ready"

# 4. Generate API secret key if empty
if grep -q "API_SECRET_KEY=$" .env 2>/dev/null; then
  SECRET=$(openssl rand -hex 32 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(32))")
  sed -i "s/API_SECRET_KEY=/API_SECRET_KEY=$SECRET/" .env
  echo "✓ Generated API_SECRET_KEY"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit .env with your credentials"
echo "  2. docker compose up -d"
echo "  3. Check health: curl http://localhost:8000/health"
echo "  4. Open web panel: http://localhost:3000"
echo "  5. Start Telegram bot: /start in @DimentosControlBot"
echo ""
