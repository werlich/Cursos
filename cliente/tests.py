"""Testes do módulo de cursos — Meet, ACL, campanha e providers."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from cliente.models import (
    Cliente,
    Curso,
    Gravacao,
    Inscricao,
    Live,
    LivePixCampanha,
    Material,
)
from cliente.providers import (
    AsaasPaymentProvider,
    LivePixPaymentProvider,
    ManualUrlMeetingProvider,
    get_meeting_provider,
    get_payment_provider,
)
from cliente.providers.payment import inscricao_libera_acesso


class LiveClassroomFixtures(TestCase):
    def setUp(self):
        self.curso = Curso.objects.create(
            tipo=Curso.Tipo.ARRAIS,
            nome="Arrais-Amador",
            preco=Decimal("29.90"),
            min_alunos_padrao=2,
        )
        self.cliente = Cliente.objects.create(
            nome="Aluno Teste",
            email="aluno@teste.com",
            whatsapp="48999999999",
        )
        self.live = Live.objects.create(
            curso=self.curso,
            titulo="Curso Arrais",
            descricao="Aula preparatória",
            professor="Instrutor SIGNAU",
            data_hora=timezone.now() + timedelta(hours=2),
            duracao_minutos=120,
            stream_url="https://meet.google.com/abc-defg-hij",
            status=Live.Status.ABERTA,
            min_alunos=2,
        )
        self.insc = Inscricao.objects.create(
            cliente=self.cliente,
            live=self.live,
            status=Inscricao.Status.PAGO,
        )


class MeetWindowTests(LiveClassroomFixtures):
    def test_meet_antes_bloqueado(self):
        self.live.data_hora = timezone.now() + timedelta(hours=1)
        self.live.save(update_fields=["data_hora"])
        info = ManualUrlMeetingProvider().join_info(self.live)
        self.assertEqual(info.status, Live.MeetStatus.ANTES)
        self.assertFalse(info.pode_entrar)
        self.assertIn("5 minutos", info.label)

    def test_meet_aberto_na_janela(self):
        self.live.data_hora = timezone.now() - timedelta(minutes=1)
        self.live.save(update_fields=["data_hora"])
        info = ManualUrlMeetingProvider().join_info(self.live)
        self.assertEqual(info.status, Live.MeetStatus.ABERTA)
        self.assertTrue(info.pode_entrar)
        self.assertEqual(info.label, "Entrar na Aula")

    def test_meet_encerrado_apos_duracao(self):
        self.live.data_hora = timezone.now() - timedelta(hours=3)
        self.live.duracao_minutos = 120
        self.live.save(update_fields=["data_hora", "duracao_minutos"])
        info = ManualUrlMeetingProvider().join_info(self.live)
        self.assertEqual(info.status, Live.MeetStatus.ENCERRADA)
        self.assertFalse(info.pode_entrar)
        self.assertEqual(info.label, "Aula Encerrada")

    def test_meet_encerrado_por_status_live(self):
        self.live.data_hora = timezone.now() - timedelta(minutes=1)
        self.live.status = Live.Status.ENCERRADA
        self.live.save(update_fields=["data_hora", "status"])
        info = ManualUrlMeetingProvider().join_info(self.live)
        self.assertEqual(info.status, Live.MeetStatus.ENCERRADA)


class AccessControlTests(LiveClassroomFixtures):
    def test_inscricao_paga_libera(self):
        self.assertTrue(inscricao_libera_acesso(self.insc))

    def test_inscricao_pendente_bloqueia(self):
        self.insc.status = Inscricao.Status.PENDENTE
        self.insc.save(update_fields=["status"])
        self.assertFalse(inscricao_libera_acesso(self.insc))

    def test_sala_redirect_para_aula(self):
        url = reverse("cliente:sala", kwargs={"token": self.insc.token_acesso})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn(
            reverse(
                "cliente:aluno_aula",
                kwargs={"token": self.insc.token_acesso, "live_id": self.live.pk},
            ),
            resp.url,
        )

    def test_pendente_vai_para_pagamento(self):
        self.insc.status = Inscricao.Status.PENDENTE
        self.insc.save(update_fields=["status"])
        url = reverse("cliente:aluno_aulas", kwargs={"token": self.insc.token_acesso})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/pagamento/", resp.url)

    def test_area_aluno_so_proprias_aulas(self):
        outro = Cliente.objects.create(
            nome="Outro", email="outro@teste.com", whatsapp="48988888888"
        )
        live2 = Live.objects.create(
            curso=self.curso,
            titulo="Outro curso",
            data_hora=timezone.now() + timedelta(days=1),
            stream_url="https://meet.google.com/xyz",
            min_alunos=2,
        )
        Inscricao.objects.create(
            cliente=outro, live=live2, status=Inscricao.Status.PAGO
        )
        url = reverse("cliente:aluno_aulas", kwargs={"token": self.insc.token_acesso})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Curso Arrais")
        self.assertNotContains(resp, "Outro curso")

    def test_detalhe_aula_alheia_404(self):
        outro = Cliente.objects.create(
            nome="Outro", email="outro2@teste.com", whatsapp="48977777777"
        )
        live2 = Live.objects.create(
            curso=self.curso,
            titulo="Curso secreto",
            data_hora=timezone.now() + timedelta(days=2),
            min_alunos=2,
        )
        Inscricao.objects.create(
            cliente=outro, live=live2, status=Inscricao.Status.PAGO
        )
        url = reverse(
            "cliente:aluno_aula",
            kwargs={"token": self.insc.token_acesso, "live_id": live2.pk},
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)


class CampanhaLivePixTests(LiveClassroomFixtures):
    def test_campanha_ativa_aparece_no_detalhe(self):
        LivePixCampanha.objects.create(
            live=self.live,
            nome_campanha="Apoie a turma",
            link_pagamento="https://livepix.gg/demo",
            qr_code_url="https://example.com/qr.png",
            meta_financeira=Decimal("500.00"),
            valor_arrecadado=Decimal("120.00"),
            ativo=True,
        )
        # Dentro da janela Meet para não confundir asserts
        self.live.data_hora = timezone.now() - timedelta(minutes=2)
        self.live.save(update_fields=["data_hora"])
        url = reverse(
            "cliente:aluno_aula",
            kwargs={"token": self.insc.token_acesso, "live_id": self.live.pk},
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Apoie esta aula pelo LivePix")
        self.assertContains(resp, "Apoie a turma")
        self.assertContains(resp, "Contribuir")

    @override_settings(
        LIVEPIX_WIDGET_URL="https://widget.livepix.gg/embed/ffe2e2ee-e6df-45cc-89e0-4475b54b7e9a"
    )
    def test_widget_livepix_embed(self):
        url = reverse(
            "cliente:aluno_aula",
            kwargs={"token": self.insc.token_acesso, "live_id": self.live.pk},
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "widget.livepix.gg/embed/ffe2e2ee-e6df-45cc-89e0-4475b54b7e9a")
        self.assertContains(resp, "Apoie esta aula pelo LivePix")

    @override_settings(LIVEPIX_WIDGET_URL="")
    def test_campanha_inativa_nao_aparece(self):
        LivePixCampanha.objects.create(
            live=self.live,
            nome_campanha="Oculta",
            link_pagamento="https://livepix.gg/demo",
            ativo=False,
        )
        url = reverse(
            "cliente:aluno_aula",
            kwargs={"token": self.insc.token_acesso, "live_id": self.live.pk},
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "Oculta")
        self.assertNotContains(resp, "Apoie esta aula pelo LivePix")


class MaterialGravacaoTests(LiveClassroomFixtures):
    def test_material_download_redirect(self):
        mat = Material.objects.create(
            live=self.live,
            titulo="Apostila",
            url="https://example.com/apostila.pdf",
            ativo=True,
        )
        url = reverse(
            "cliente:aluno_material",
            kwargs={"token": self.insc.token_acesso, "material_id": mat.pk},
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, "https://example.com/apostila.pdf")

    def test_gravacao_redirect(self):
        grav = Gravacao.objects.create(
            live=self.live,
            titulo="Replay",
            url="https://youtube.com/watch?v=demo",
            ativo=True,
        )
        url = reverse(
            "cliente:aluno_gravacao",
            kwargs={"token": self.insc.token_acesso, "gravacao_id": grav.pk},
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, "https://youtube.com/watch?v=demo")


class ProviderFactoryTests(TestCase):
    def test_default_meeting_provider(self):
        self.assertIsInstance(get_meeting_provider(), ManualUrlMeetingProvider)

    def test_default_payment_provider(self):
        self.assertIsInstance(get_payment_provider(), LivePixPaymentProvider)

    @override_settings(PAYMENT_PROVIDER="asaas")
    def test_asaas_stub_selected(self):
        self.assertIsInstance(get_payment_provider(), AsaasPaymentProvider)

    @override_settings(PAYMENT_PROVIDER="asaas")
    def test_asaas_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            get_payment_provider().create_enrollment_payment(None)
