# SIGNAU Cursos Live

Plataforma de aulas online em **live.signau.cc**: cadastro de interessados, pagamento PIX (Asaas) e sala com link OBS.

## Stack

- Django + Jazzmin
- App **Cliente** (cadastro, lives, pagamentos, créditos)
- Asaas PIX QR (modo `ASAAS_DEMO=true` para desenvolvimento)
- Deploy VPS no padrão SIGNAU (Apache + Gunicorn + MySQL)

## Cursos e preço

| Curso | Preço |
|-------|-------|
| Arrais-Amador | R$ 29,90 |
| Motonauta | R$ 29,90 |
| Mestre-Amador | R$ 29,90 |
| Capitão-Amador | R$ 29,90 |

Lives: **segundas, quartas e sextas**. Turma mínima: **10** pagamentos. Se não fechar, o valor vira **crédito** para a próxima live (estorno manual no admin via Asaas).

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
2. Na VPS (após push do código):

```bash
scp deploy/provision_cursos.sh root@37.60.251.181:/root/
ssh root@37.60.251.181 'bash /root/provision_cursos.sh live live.signau.cc 8003 "Cursos Live"'
```

3. Deploys seguintes:

```bash
git push origin main
./deploy_vps.sh --client live
```

4. Asaas: preencha `ASAAS_API_KEY` no `.env` da VPS, `ASAAS_DEMO=false`, configure o webhook `https://live.signau.cc/webhooks/asaas/` com o token gerado.

## Fluxo do aluno

1. Acessa `https://live.signau.cc`
2. Informa nome, e-mail, WhatsApp e escolhe a live
3. Paga via QR PIX Asaas
4. Recebe acesso à sala (link OBS quando o admin publicar `stream_url`)
