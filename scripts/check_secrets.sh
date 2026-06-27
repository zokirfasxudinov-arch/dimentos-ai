#!/bin/bash
# Pre-commit hook: scan staged files for leaked secrets/tokens
# Install: cp scripts/check_secrets.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit

set -e

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

echo "🔐 Dimentos AI - Security check..."

STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM 2>/dev/null || true)

if [ -z "$STAGED_FILES" ]; then
  echo -e "${GREEN}✓ No staged files to check${NC}"
  exit 0
fi

FOUND=0

# Patterns that indicate leaked secrets
PATTERNS=(
  "TELEGRAM_BOT_TOKEN\s*=\s*[0-9]"
  "bot_token\s*=\s*['\"][0-9]"
  "AAG[A-Za-z0-9_-]{30}"
  "sk-[A-Za-z0-9]{40,}"
  "sk-or-v1-[A-Za-z0-9]"
  "AIzaSy[A-Za-z0-9_-]{33}"
  "ANTHROPIC_API_KEY\s*=\s*sk-"
  "OPENAI_API_KEY\s*=\s*sk-"
  "GITHUB_TOKEN\s*=\s*gh[pousr]_"
  "ghp_[A-Za-z0-9]{36}"
  "gho_[A-Za-z0-9]{36}"
  "password\s*=\s*['\"][^'\"]{8,}"
  "BEGIN (RSA|EC|OPENSSH) PRIVATE"
  "BEGIN PRIVATE KEY"
)

BLOCKED_FILES=(
  "\.env$"
  "\.key$"
  "\.pem$"
  "\.pfx$"
  "\.p12$"
  "secrets/"
  "private/"
  "credentials/"
  "tokens/"
)

# Check for blocked file types
for file in $STAGED_FILES; do
  for pattern in "${BLOCKED_FILES[@]}"; do
    if echo "$file" | grep -qE "$pattern"; then
      echo -e "${RED}✗ BLOCKED: Sensitive file type staged: $file${NC}"
      FOUND=1
    fi
  done
done

# Check file contents for secret patterns
for file in $STAGED_FILES; do
  if [ ! -f "$file" ]; then continue; fi
  # Skip binary files
  if file "$file" | grep -q "binary"; then continue; fi
  # Skip example/template files
  if echo "$file" | grep -qE "(\.example|\.template|\.sample)$"; then continue; fi
  # Skip the scanner itself (contains patterns as literal strings, not actual secrets)
  if echo "$file" | grep -qE "check_secrets\.sh$"; then continue; fi

  for pattern in "${PATTERNS[@]}"; do
    if git show ":$file" 2>/dev/null | grep -qE "$pattern"; then
      echo -e "${RED}✗ POTENTIAL SECRET in $file (pattern: $pattern)${NC}"
      FOUND=1
    fi
  done
done

if [ $FOUND -ne 0 ]; then
  echo ""
  echo -e "${RED}════════════════════════════════════════${NC}"
  echo -e "${RED}  COMMIT BLOCKED: Potential secrets found${NC}"
  echo -e "${RED}════════════════════════════════════════${NC}"
  echo ""
  echo "Remove secrets from staged files before committing."
  echo "Secrets belong only in .env (which is gitignored)."
  echo ""
  exit 1
fi

echo -e "${GREEN}✓ No secrets detected. Proceeding with commit.${NC}"
exit 0
