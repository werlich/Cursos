# SIGNAU Cursos Live

Plataforma de aulas online em **live.signau.cc**: cadastro de interessados, pagamento PIX (**LivePix**) e sala com link OBS.

## Stack

- Django + Jazzmin
- App **Cliente** (cadastro, lives, pagamentos, créditos)
- LivePix checkout PIX (`LIVEPIX_DEMO=true` para desenvolvimento)
- Deploy VPS no padrão SIGNAU (Nginx + Gunicorn + MySQL)

## Cursos e preço

| Curso | Preço |
|-------|-------|
| Arrais-Amador | R$ 29,90 |
| Motonauta | R$ 29,90 |
| Mestre-Amador | R$ 29,90 |
| Capitão-Amador | R$ 29,90 |

Lives: **segundas, quartas e sextas**. Turma mínima: **10** pagamentos. Se não fechar, o valor vira **crédito** para a próxima live (estorno manual no admin / carteira LivePix).

## Local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_cursos
python manage.py createsuperuser
python manage.py runserver
```

## Produção (VPS)

1. DNS `live.signau.cc` → VPS
2. Provision (primeira vez) via `deploy/provision_cursos.sh`
3. Deploys:

```bash
git push origin main
./deploy_vps.sh --client live
```

4. LivePix: em `/var/www/cursos/.env` preencha `LIVEPIX_CLIENT_ID`, `LIVEPIX_CLIENT_SECRET`, `LIVEPIX_DEMO=false`.
5. Webhook: `https://live.signau.cc/webhooks/livepix/` (painel LivePix ou `POST /v2/webhooks`).

## Fluxo do aluno

1. Acessa `https://live.signau.cc`
2. Informa nome, e-mail, WhatsApp e escolhe a live
3. É redirecionado ao checkout LivePix (PIX)
4. Após pagamento, volta à sala (link OBS quando o admin publicar `stream_url`)
