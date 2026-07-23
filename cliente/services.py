"""Regras de negócio: inscrição, confirmação de turma e créditos."""

from __future__ import annotations

import logging
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .asaas import AsaasClient, AsaasError
from .models import Credito, Inscricao, Live, Pagamento

logger = logging.getLogger(__name__)


def criar_pagamento_pix(inscricao: Inscricao, valor: Decimal | None = None) -> Pagamento:
    """Cria cobrança PIX no Asaas (ou DEMO) vinculada à inscrição."""
    existing = Pagamento.objects.filter(inscricao=inscricao).first()
    if existing:
        return existing

    valor = valor if valor is not None else inscricao.live.curso.preco
    client = AsaasClient()
    customer_id = client.ensure_customer(
        nome=inscricao.cliente.nome,
        email=inscricao.cliente.email,
        whatsapp=inscricao.cliente.whatsapp,
    )
    charge = client.create_pix_charge(
        customer_id=customer_id,
        valor=valor,
        descricao=f"SIGNAU Live — {inscricao.live.curso.nome} — {inscricao.live.titulo}",
        external_reference=f"insc-{inscricao.pk}",
    )
    return Pagamento.objects.create(
        inscricao=inscricao,
        valor=valor,
        asaas_payment_id=charge["payment_id"],
        asaas_customer_id=customer_id,
        pix_qr_code=charge["pix_qr_code"],
        pix_copia_cola=charge["pix_copia_cola"],
        invoice_url=charge.get("invoice_url") or "",
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
    Política padrão (briefing): crédito para próxima live; estorno manual via admin.
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
            "asaas_payment_id": f"credito-{credito.pk}",
        },
    )
    avaliar_turma(live)
    return insc


def estornar_pagamento(pagamento: Pagamento) -> None:
    client = AsaasClient()
    try:
        if pagamento.asaas_payment_id:
            client.refund(pagamento.asaas_payment_id, valor=pagamento.valor)
    except AsaasError as exc:
        logger.exception("Falha ao estornar no Asaas: %s", exc)
        raise
    pagamento.status = Pagamento.Status.ESTORNADO
    pagamento.save(update_fields=["status"])
    insc = pagamento.inscricao
    insc.status = Inscricao.Status.ESTORNADO
    insc.save(update_fields=["status"])


def min_alunos_default() -> int:
    return int(getattr(settings, "MIN_ALUNOS_TURMA", 10))
