#!/usr/bin/env bash
# Dispara deploy remoto do projeto Cursos (padrão SIGNAU deploy_vps).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
CLIENT_ENV="${ROOT}/deploy/clients/live.env"
VPS_HOST="${SIGNAU_VPS_HOST:-root@37.60.251.181}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --client)
      CLIENT_ENV="${ROOT}/deploy/clients/${2}.env"
      shift 2
      ;;
    *)
      echo "Uso: $0 [--client live]"
      exit 1
      ;;
  esac
done

if [[ ! -f "${CLIENT_ENV}" ]]; then
  echo "Arquivo não encontrado: ${CLIENT_ENV}"
  exit 1
fi

# shellcheck disable=SC1090
source "${CLIENT_ENV}"

MODE="${SIGNAU_DEPLOY_MODE:-git}"

if [[ "${MODE}" == "git" ]]; then
  if [[ -n "$(git -C "${ROOT}" status --porcelain)" ]]; then
    echo "Working tree suja. Faça commit/push antes do deploy git."
    exit 1
  fi
  git -C "${ROOT}" fetch origin
  LOCAL=$(git -C "${ROOT}" rev-parse HEAD)
  REMOTE=$(git -C "${ROOT}" rev-parse origin/main)
  if [[ "${LOCAL}" != "${REMOTE}" ]]; then
    echo "main local != origin/main. Faça push primeiro."
    exit 1
  fi
  ssh "${VPS_HOST}" "cd '${SIGNAU_VPS_PATH}' && bash deploy.sh"
else
  rsync -az --delete \
    --exclude '.venv' --exclude 'venv' --exclude '.git' --exclude 'db.sqlite3' \
    --exclude '.env' --exclude 'media' --exclude 'staticfiles' --exclude '__pycache__' \
    "${ROOT}/" "${VPS_HOST}:${SIGNAU_VPS_PATH}/"
  ssh "${VPS_HOST}" "cd '${SIGNAU_VPS_PATH}' && bash deploy.sh"
fi

echo "Healthcheck ${SIGNAU_VPS_URL} …"
curl -fsS -o /dev/null -w "%{http_code}\n" "${SIGNAU_VPS_URL}/" || true
