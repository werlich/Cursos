# Como testar o processo completo (live.signau.cc)

Produção usa PIX real (`LIVEPIX_DEMO=false`). Para testar sem gastar, use o **Caminho A** (atalho no admin).

## Fluxo

```text
Admin prepara curso → Cadastro → PIX LivePix → Área do aluno
                                      → Entrar na Aula (Meet)
                                      → Widget doação
                                      → Material / Gravação
```

## 1) Testes automatizados

```bash
cd /home/claudio/Desktop/Cursos
.venv/bin/python manage.py test cliente -v 2
```

Cobre: janela Meet, ACL, redirect `/sala/` → área do aluno, widget, materiais/gravações, providers.

## 2) Preparar curso no admin

`https://live.signau.cc/admin/`

1. Título, descrição, professor  
2. Data/hora ≈ daqui a 10 minutos  
3. Duração 120 (ou 30)  
4. Link Google Meet  
5. Material (URL) e Gravação (URL) nos inlines  
6. Widget global já aparece sem campanha

## 3) Caminho A — sem pagar (recomendado)

1. [Cadastro](https://live.signau.cc/cadastro/) com e-mail novo + curso de teste  
2. Na tela de pagamento, **não pague**  
3. Admin → Inscrições → status **Pago** (ou Confirmado)  
4. Copie `token_acesso`  
5. Abra:
   - `/aluno/<token>/`
   - `/aluno/<token>/aula/<live_id>/`
   - `/sala/<token>/` → deve redirecionar para o detalhe  

| Item | Esperado |
|------|----------|
| Meet (>5 min antes) | Bloqueado: “Disponível 5 minutos antes…” |
| Meet (na janela) | **Entrar na Aula** abre em nova aba |
| Meet (após duração / Encerrada) | **Aula Encerrada** |
| Material / Gravação | Abrem o link |
| LivePix | Iframe `widget.livepix.gg/embed/ffe2e2ee-…` |

## 4) Caminho B — PIX real

1. Cadastro → pagamento com QR/checkout **real** (não “PIX DEMO”)  
2. Pague (~R$ 29,90)  
3. Retorno/webhook deve liberar a área do aluno  
4. Admin: inscrição Pago/Confirmado, pagamento Confirmado, `livepix_payment_id` preenchido  

Webhook: `https://live.signau.cc/webhooks/livepix/`

## 5) Janela Meet (3 momentos)

No mesmo curso, só mude `data_hora` e recarregue a área do aluno:

1. +1 hora → bloqueado  
2. agora − 1 min → liberado  
3. agora − 3 h (duração 120) ou status Encerrada → “Aula Encerrada”

## 6) ACL

- Token A acessando curso de outro aluno → 404  
- Inscrição Pendente em `/aluno/<token>/` → redirect pagamento  
- Token inventado → 404  

## 7) Widget

Na página da aula, contribuir pelo iframe e conferir no painel LivePix (doação ≠ matrícula).

## Ordem sugerida

1. Testes automatizados  
2. Caminho A  
3. Ajustes Meet  
4. Caminho B (1 PIX)  
5. Widget (opcional)

## Fora desta etapa

Chat, presença, Asaas, APIs Google Meet.
