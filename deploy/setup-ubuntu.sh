#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# setup-ubuntu.sh — APS Goianira
# Provisionamento completo para Ubuntu 22.04 / 24.04
# Execute como root ou com sudo
# ============================================================

REPO_URL="https://github.com/seu-usuario/aps-goianira.git"   # <-- ALTERE AQUI
INSTALL_DIR="/opt/aps-goianira"
BACKEND_DIR="$INSTALL_DIR/backend"
FRONTEND_DIR="$INSTALL_DIR/frontend"

echo "=== 1. Atualizando pacotes ==="
apt update && apt upgrade -y

echo "=== 2. Instalando dependências do sistema ==="
apt install -y \
    python3 python3-pip python3-venv \
    nodejs npm \
    nginx \
    git \
    postgresql-client

echo "=== 3. Clonando repositório ==="
if [ -d "$INSTALL_DIR" ]; then
    echo "Diretório $INSTALL_DIR já existe — fazendo pull..."
    cd "$INSTALL_DIR" && git pull
else
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

echo "=== 4. Configurando ambiente Python ==="
python3 -m venv "$BACKEND_DIR/venv"
source "$BACKEND_DIR/venv/bin/activate"
pip install --upgrade pip
pip install -r "$BACKEND_DIR/requirements.txt"
deactivate

echo "=== 5. Criando .env ==="
if [ ! -f "$BACKEND_DIR/.env" ]; then
    cat > "$BACKEND_DIR/.env" << 'ENVEOF'
# === APS Goianira — Configuração do Banco e-SUS ===
ESUS_DB_HOST=192.168.0.229
ESUS_DB_PORT=5433
ESUS_DB_NAME=esus
ESUS_DB_USER=postgres
ESUS_DB_PASSWORD=SUA_SENHA_AQUI
ENVEOF
    echo ".env criado em $BACKEND_DIR/.env — EDITE A SENHA!"
else
    echo ".env já existe — mantendo atual"
fi

echo "=== 6. Compilando frontend ==="
cd "$FRONTEND_DIR"
npm install
npm run build

echo "=== 7. Ajustando permissões ==="
chown -R www-data:www-data "$INSTALL_DIR"

echo "=== 8. Instalando systemd services ==="
cp "$INSTALL_DIR/deploy/aps-backend.service" /etc/systemd/system/
cp "$INSTALL_DIR/deploy/aps-etl.service" /etc/systemd/system/
cp "$INSTALL_DIR/deploy/aps-etl.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable aps-backend.service aps-etl.timer
systemctl start aps-backend.service aps-etl.timer

echo "=== 9. Configurando nginx ==="
cp "$INSTALL_DIR/deploy/nginx-aps.conf" /etc/nginx/sites-available/aps-goianira
if [ -f /etc/nginx/sites-enabled/default ]; then
    rm /etc/nginx/sites-enabled/default
fi
ln -sf /etc/nginx/sites-available/aps-goianira /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

echo ""
echo "============================================"
echo "  ✅  Provisionamento concluído!"
echo ""
echo "  Acesse: http://$(hostname -I | awk '{print $1}')"
echo ""
echo "  Serviços:"
echo "    systemctl status aps-backend   # API"
echo "    systemctl status aps-etl.timer # ETL 04:00"
echo "    systemctl status nginx         # Frontend"
echo ""
echo "  Logs:"
echo "    journalctl -u aps-backend -f"
echo "============================================"
