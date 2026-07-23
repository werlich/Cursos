#!/usr/bin/env bash
# Deploy na VPS (rodar dentro de /var/www/cursos ou /var/www/live)
set -euo pipefail

cd "$(dirname "$0")"

if [[ -f client.env ]]; then
  # shellcheck disable=SC1091
  source client.env
fi

if [[ ! -f venv/bin/activate ]]; then
  echo "Erro: virtualenv não encontrado em $(pwd)/venv"
  exit 1
fi

source venv/bin/activate

if git remote get-url origin >/dev/null 2>&1; then
  git config --global --add safe.directory "$(pwd)" 2>/dev/null || true
  export GIT_SSH_COMMAND="${GIT_SSH_COMMAND:-ssh -i /root/.ssh/signau_deploy -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new}"
  git fetch origin
  git checkout main
  git pull --ff-only origin main
fi

pip install -r requirements.txt gunicorn
python manage.py migrate --noinput
python manage.py collectstatic --clear --noinput

GUNICORN_SERVICE="${GUNICORN_SERVICE:-gunicorn-cursos}"
systemctl restart "${GUNICORN_SERVICE}"
systemctl reload apache2 2>/dev/null || systemctl reload nginx 2>/dev/null || true

echo "Deploy Cursos concluído (${GUNICORN_SERVICE}): $(date -u +%Y-%m-%dT%H:%M:%SZ)"
