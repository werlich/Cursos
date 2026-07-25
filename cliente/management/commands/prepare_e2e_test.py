"""Prepara um curso de teste e opcionalmente libera uma inscrição (Caminho A)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from cliente.models import Cliente, Curso, Gravacao, Inscricao, Live, Material, Pagamento
from cliente.services import criar_pagamento_pix


class Command(BaseCommand):
    help = (
        "Cria/atualiza um curso de teste com Meet, material e gravação. "
        "Com --email, cria inscrição e marca como PAGO (atalho sem PIX)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--minutes",
            type=int,
            default=10,
            help="Minutos até o início da aula (default: 10).",
        )
        parser.add_argument(
            "--email",
            default="",
            help="Se informado, cria Cliente/Inscrição e marca como Pago.",
        )
        parser.add_argument("--nome", default="Aluno Teste E2E")
        parser.add_argument("--whatsapp", default="48999990000")
        parser.add_argument(
            "--meet",
            default="https://meet.google.com/lookup/signau-teste",
            help="URL do Google Meet de teste.",
        )

    def handle(self, *args, **options):
        curso = (
            Curso.objects.filter(ativo=True).order_by("ordem", "pk").first()
            or Curso.objects.create(
                tipo=Curso.Tipo.ARRAIS,
                nome="Arrais-Amador",
                preco=Decimal("29.90"),
                min_alunos_padrao=2,
                ativo=True,
            )
        )
        inicio = timezone.now() + timedelta(minutes=options["minutes"])
        live, created = Live.objects.update_or_create(
            titulo="[TESTE E2E] Aula SIGNAU",
            defaults={
                "curso": curso,
                "descricao": "Curso de teste do fluxo completo (Meet, material, gravação, widget).",
                "professor": "Instrutor SIGNAU",
                "data_hora": inicio,
                "duracao_minutos": 30,
                "stream_url": options["meet"],
                "status": Live.Status.ABERTA,
                "min_alunos": 2,
            },
        )
        Material.objects.update_or_create(
            live=live,
            titulo="Apostila teste",
            defaults={
                "url": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
                "ativo": True,
            },
        )
        Gravacao.objects.update_or_create(
            live=live,
            titulo="Gravação teste",
            defaults={
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "ativo": True,
            },
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Criado' if created else 'Atualizado'} curso pk={live.pk} "
                f"em {timezone.localtime(live.data_hora):%d/%m/%Y %H:%M}"
            )
        )

        email = (options["email"] or "").strip().lower()
        if not email:
            self.stdout.write(
                "Sem --email: cadastre no site e marque a inscrição como Pago no admin."
            )
            self.stdout.write(f"Cadastro: https://live.signau.cc/cadastro/?live={live.pk}")
            return

        cliente, _ = Cliente.objects.update_or_create(
            email=email,
            defaults={"nome": options["nome"], "whatsapp": options["whatsapp"]},
        )
        insc, _ = Inscricao.objects.get_or_create(
            cliente=cliente,
            live=live,
            defaults={"status": Inscricao.Status.PAGO},
        )
        if insc.status != Inscricao.Status.PAGO:
            insc.status = Inscricao.Status.PAGO
            insc.save(update_fields=["status"])
        if not hasattr(insc, "pagamento"):
            try:
                criar_pagamento_pix(insc)
            except Exception:
                Pagamento.objects.create(
                    inscricao=insc,
                    valor=live.curso.preco,
                    status=Pagamento.Status.CONFIRMADO,
                    confirmado_em=timezone.now(),
                )
        else:
            pag = insc.pagamento
            if pag.status != Pagamento.Status.CONFIRMADO:
                pag.status = Pagamento.Status.CONFIRMADO
                pag.confirmado_em = timezone.now()
                pag.save(update_fields=["status", "confirmado_em"])

        base = "https://live.signau.cc"
        self.stdout.write(self.style.SUCCESS(f"Inscrição liberada: {insc.pk}"))
        self.stdout.write(f"Token: {insc.token_acesso}")
        self.stdout.write(f"Área aluno: {base}/aluno/{insc.token_acesso}/")
        self.stdout.write(f"Aula: {base}/aluno/{insc.token_acesso}/aula/{live.pk}/")
        self.stdout.write(f"Sala (redirect): {base}/sala/{insc.token_acesso}/")
