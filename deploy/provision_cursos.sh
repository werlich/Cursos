#!/usr/bin/env bash
# Provisiona Cursos Live na VPS (padrão SIGNAU).
# Uso (como root na VPS):
#   bash provision_cursos.sh live live.signau.cc 8003 "Cursos Live"
set -euo pipefail

CLIENT_ID="${1:?Uso: provision_cursos.sh CLIENT_ID DOMAIN GUNICORN_PORT [NOME]}"
DOMAIN="${2:?}"
GUNICORN_PORT="${3:?}"
CLIENT_NAME="${4:-Cursos Live}"

WWW_ROOT="/var/www/cursos"
DB_NAME="cursos_db"
DB_USER="cursos_user"
GUNICORN_SERVICE="gunicorn-cursos"
GIT_SSH='ssh -i /root/.ssh/signau_deploy -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new'
REPO="git@github.com:werlich/Cursos.git"

if [[ -d "${WWW_ROOT}/venv" ]]; then
  echo "Instância já existe em ${WWW_ROOT}. Abortando."
  exit 1
fi

DB_PASS="$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)"
ADMIN_PASS="$(openssl rand -base64 18 | tr -d '/+=' | head -c 16)"

echo "=== Criando banco ${DB_NAME} ==="
mysql <<SQL
CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';
GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'localhost';
FLUSH PRIVILEGES;
SQL

echo "=== Clonando ${REPO} ==="
export GIT_SSH_COMMAND="${GIT_SSH}"
git clone "${REPO}" "${WWW_ROOT}"
cd "${WWW_ROOT}"
git checkout main

echo "=== Virtualenv ==="
python3 -m venv venv
# shellcheck disable=SC1091
source venv/bin/activate
pip install -U pip
pip install -r requirements.txt gunicorn
SECRET_KEY="$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')"

echo "=== .env e client.env ==="
cat > .env <<ENV
DJANGO_SECRET_KEY=${SECRET_KEY}
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=${DOMAIN},37.60.251.181
DJANGO_CSRF_TRUSTED_ORIGINS=https://${DOMAIN},http://${DOMAIN}
SITE_URL=https://${DOMAIN}
DJANGO_DB_NAME=${DB_NAME}
DJANGO_DB_USER=${DB_USER}
DJANGO_DB_PASSWORD=${DB_PASS}
DJANGO_DB_HOST=127.0.0.1
DJANGO_DB_PORT=3306
LIVEPIX_CLIENT_ID=
LIVEPIX_CLIENT_SECRET=
LIVEPIX_API_URL=https://api.livepix.gg
LIVEPIX_OAUTH_URL=https://oauth.livepix.gg
LIVEPIX_SCOPE=payments:write payments:read webhooks account:read
LIVEPIX_DEMO=true
MIN_ALUNOS_TURMA=10
PRECO_PADRAO=29.90
ENV
chmod 600 .env

cat > client.env <<CEOF
GUNICORN_SERVICE=${GUNICORN_SERVICE}
GUNICORN_PORT=${GUNICORN_PORT}
CEOF
chmod 640 client.env

mkdir -p media staticfiles
python manage.py migrate --noinput
python manage.py seed_cursos
python manage.py collectstatic --noinput
DJANGO_SUPERUSER_USERNAME=admin \
DJANGO_SUPERUSER_EMAIL="admin@${DOMAIN}" \
DJANGO_SUPERUSER_PASSWORD="${ADMIN_PASS}" \
python manage.py createsuperuser --noinput

echo "=== systemd ${GUNICORN_SERVICE} ==="
cat > "/etc/systemd/system/${GUNICORN_SERVICE}.service" <<UNIT
[Unit]
Description=Gunicorn SIGNAU Cursos (${CLIENT_NAME})
After=network.target mariadb.service mysql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=${WWW_ROOT}
Environment="PATH=${WWW_ROOT}/venv/bin"
ExecStart=${WWW_ROOT}/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:${GUNICORN_PORT} cursos.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
UNIT

chown -R www-data:www-data "${WWW_ROOT}"
chmod 600 "${WWW_ROOT}/.env"
systemctl daemon-reload
systemctl enable "${GUNICORN_SERVICE}"
systemctl start "${GUNICORN_SERVICE}"

echo "${ADMIN_PASS}" > "/root/.cursos_live_admin_pass"
chmod 600 /root/.cursos_live_admin_pass

echo "=== Nginx vhost ${DOMAIN} ==="
cat > "/etc/nginx/sites-available/${DOMAIN}" <<NGINX
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};

    client_max_body_size 20M;

    location /static/ {
        alias ${WWW_ROOT}/staticfiles/;
        access_log off;
        expires 30d;
    }

    location /media/ {
        alias ${WWW_ROOT}/media/;
        access_log off;
        expires 7d;
    }

    location / {
        proxy_pass http://127.0.0.1:${GUNICORN_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NGINX

ln -sfn "/etc/nginx/sites-available/${DOMAIN}" "/etc/nginx/sites-enabled/${DOMAIN}"
nginx -t
systemctl reload nginx

echo "=== HTTPS certbot ==="
certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos --redirect --register-unsafely-without-email \
  || certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos --redirect

echo ""
echo "=== ${CLIENT_NAME} provisionado ==="
echo "URL:     https://${DOMAIN}"
echo "Admin:   admin / $(cat /root/.cursos_live_admin_pass)"
echo "Webhook: https://${DOMAIN}/webhooks/livepix/"
echo "Path:    ${WWW_ROOT}"
echo "Gunicorn:${GUNICORN_SERVICE} :${GUNICORN_PORT}"
echo "Configure LIVEPIX_CLIENT_ID / LIVEPIX_CLIENT_SECRET em ${WWW_ROOT}/.env e LIVEPIX_DEMO=false."
