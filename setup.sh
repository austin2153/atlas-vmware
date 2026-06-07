#!/usr/bin/env bash
set -euo pipefail

echo "==> Creating Python virtual environment..."
python3 -m venv .venv

echo "==> Installing Python dependencies..."
.venv/bin/pip install --upgrade pip --quiet
.venv/bin/pip install -r requirements.txt --quiet

echo "==> Installing Ansible collections..."
SSL_CERT_FILE=$(.venv/bin/python3 -c "import certifi; print(certifi.where())") \
  .venv/bin/ansible-galaxy collection install -r requirements.yml

echo ""
echo "Setup complete. Activate the environment with:"
echo "  source .venv/bin/activate"
