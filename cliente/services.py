"""Regras de negócio: inscrição, confirmação de turma e créditos."""

from __future__ import annotations

import logging
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .livepix import LivePixClient, LivePixError
from .models import Credito, Inscricao, Live, Pagamento

logger = logging.getLogger(__name__)


def _absolute_retorno_url(request, token: str) -> str:
    path = reverse("cliente:pagamento_retorno", kwargs={"token": token})
    if request is not None:
        return request.build_absolute_uri(path)
    base = getattr(settings, "SITE_URL", "https://live.signau.cc").rstrip("/")
    return f"{base}{path}"


def criar_pagamento_pix(
    inscricao: Inscricao,
    valor: Decimal | None = None,
    *,
    request=None,
) -> Pagamento:
    """Cria cobrança PIX no LivePix (ou DEMO) vinculada à inscrição."""
    existing = Pagamento.objects.filter(inscricao=inscricao).first()
    if existing:
        return existing

    valor = valor if valor is not None else inscricao.live.curso.preco
    client = LivePixClient()
    retorno = _absolute_retorno_url(request, inscricao.token_acesso)
    charge = client.create_payment(amount=valor, redirect_url=retorno)

    checkout = charge.get("checkout_url") or ""
    if client.demo and not checkout:
        checkout = reverse(
            "cliente:pagamento_demo_confirmar",
            kwargs={"token": inscricao.token_acesso},
        )
        if request is not None:
            # demo confirma via POST na própria página; invoice aponta para a página de pagamento
            checkout = request.build_absolute_uri(
                reverse("cliente:pagamento", kwargs={"token": inscricao.token_acesso})
            )

    return Pagamento.objects.create(
        inscricao=inscricao,
        valor=valor,
        livepix_payment_id=charge["payment_id"],
        livepix_reference=charge["reference"],
        invoice_url=checkout,
        status=Pagamento.Status.PENDENTE,
    )


@transaction.atomic
def confirmar_pagamento(pagamento: Pagamento) -> None:
    if pagamento.status == Pagamento.Status.CONFIRMADO:
        return
    pagamento.status = Pagamento.Status.CONFIRMADO
    pagamento.confirmado_em = timezone.now()
    pagamento.save(update_fields=["status", "confirmado_em"])

    insc = pagamento.inscricao
    insc.status = Inscricao.Status.PAGO
    insc.save(update_fields=["status"])

    avaliar_turma(insc.live)

    try:
        from .whatsapp import enviar_confirmacao_inscricao

        enviar_confirmacao_inscricao(insc)
    except Exception:
        logger.exception("Falha ao enviar confirmação WhatsApp")


@transaction.atomic
def avaliar_turma(live: Live) -> None:
    """Confirma turma se ≥ min_alunos; não emite créditos automaticamente aqui."""
    if live.status in (Live.Status.ENCERRADA, Live.Status.CANCELADA, Live.Status.CREDITO):
        return
    if live.atingiu_minimo:
        live.status = Live.Status.CONFIRMADA
        live.save(update_fields=["status"])
        live.inscricoes.filter(status=Inscricao.Status.PAGO).update(
            status=Inscricao.Status.CONFIRMADO
        )


@transaction.atomic
def emitir_creditos_se_nao_atingiu(live: Live, *, forcar: bool = False) -> int:
    """
    Se a live não atingiu o mínimo, converte pagamentos em créditos para a próxima live.
    Retorna quantidade de créditos emitidos.
    Política padrão: crédito para próxima live; estorno manual via admin.
    """
    if live.status == Live.Status.CREDITO and not forcar:
        return 0
    if live.atingiu_minimo and not forcar:
        avaliar_turma(live)
        return 0

    count = 0
    inscricoes = live.inscricoes.select_related("cliente", "pagamento").filter(
        status__in=[Inscricao.Status.PAGO, Inscricao.Status.CONFIRMADO]
    )
    for insc in inscricoes:
        if Credito.objects.filter(origem=insc, ativo=True).exists():
            continue
        valor = insc.pagamento.valor if hasattr(insc, "pagamento") else live.curso.preco
        Credito.objects.create(
            cliente=insc.cliente,
            valor=valor,
            origem=insc,
            ativo=True,
            observacao=f"Turma {live} não atingiu mínimo de {live.min_alunos} alunos",
        )
        insc.status = Inscricao.Status.CREDITO
        insc.save(update_fields=["status"])
        count += 1

    live.status = Live.Status.CREDITO
    live.save(update_fields=["status"])
    return count


@transaction.atomic
def aplicar_credito(cliente, live: Live) -> Inscricao | None:
    credito = (
        Credito.objects.select_for_update()
        .filter(cliente=cliente, ativo=True, valor__gte=live.curso.preco)
        .order_by("criado_em")
        .first()
    )
    if not credito:
        return None
    insc, created = Inscricao.objects.get_or_create(
        cliente=cliente,
        live=live,
        defaults={"status": Inscricao.Status.PAGO, "usou_credito": True},
    )
    if not created and insc.status not in (
        Inscricao.Status.PENDENTE,
        Inscricao.Status.CANCELADO,
    ):
        return insc
    insc.status = Inscricao.Status.PAGO
    insc.usou_credito = True
    insc.save(update_fields=["status", "usou_credito"])
    credito.ativo = False
    credito.usado_em = insc
    credito.save(update_fields=["ativo", "usado_em"])
    Pagamento.objects.update_or_create(
        inscricao=insc,
        defaults={
            "valor": Decimal("0.00"),
            "status": Pagamento.Status.CONFIRMADO,
            "confirmado_em": timezone.now(),
            "pix_copia_cola": "CRÉDITO",
            "livepix_payment_id": f"credito-{credito.pk}",
            "livepix_reference": f"credito-{credito.pk}",
        },
    )
    avaliar_turma(live)
    return insc


def estornar_pagamento(pagamento: Pagamento) -> None:
    """Marca estorno local. Devolução na carteira LivePix é manual."""
    pagamento.status = Pagamento.Status.ESTORNADO
    pagamento.save(update_fields=["status"])
    insc = pagamento.inscricao
    insc.status = Inscricao.Status.ESTORNADO
    insc.save(update_fields=["status"])


def buscar_pagamento_livepix(*, payment_id: str = "", reference: str = "") -> Pagamento | None:
    qs = Pagamento.objects.select_related("inscricao")
    if payment_id:
        pag = qs.filter(livepix_payment_id=payment_id).first()
        if pag:
            return pag
        pag = qs.filter(livepix_reference=payment_id).first()
        if pag:
            return pag
    if reference:
        pag = qs.filter(livepix_reference=reference).first()
        if pag:
            return pag
        return qs.filter(livepix_payment_id=reference).first()
    return None


def sincronizar_status_livepix(pagamento: Pagamento) -> bool:
    """Consulta API LivePix; se pagamento existir/confirmado, confirma localmente."""
    if pagamento.status == Pagamento.Status.CONFIRMADO:
        return True
    pid = pagamento.livepix_payment_id or pagamento.livepix_reference
    if not pid or pid.startswith("demo_") or pid.startswith("credito-"):
        return False
    try:
        data = LivePixClient().get_payment(pid)
    except LivePixError as exc:
        logger.warning("Falha ao consultar LivePix %s: %s", pid, exc)
        return False
    if data:
        # Pagamento recebido existe na API → considerar pago
        confirmar_pagamento(pagamento)
        return True
    return False


def min_alunos_default() -> int:
    return int(getattr(settings, "MIN_ALUNOS_TURMA", 10))
