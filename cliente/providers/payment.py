"""PaymentProvider — matrícula PIX e futuros gateways (Asaas, LivePix API)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import TYPE_CHECKING

from django.conf import settings

if TYPE_CHECKING:
    from cliente.models import Inscricao, Pagamento


class PaymentProvider(ABC):
    """Interface de pagamento de matrícula (não confundir com campanha de doação)."""

    @abstractmethod
    def create_enrollment_payment(
        self,
        inscricao: Inscricao,
        valor: Decimal | None = None,
        *,
        request=None,
    ) -> Pagamento:
        raise NotImplementedError

    @abstractmethod
    def sync_payment(self, pagamento: Pagamento) -> Pagamento:
        raise NotImplementedError


class LivePixPaymentProvider(PaymentProvider):
    """Wrapper do fluxo LivePix já existente em cliente.services."""

    def create_enrollment_payment(
        self,
        inscricao: Inscricao,
        valor: Decimal | None = None,
        *,
        request=None,
    ) -> Pagamento:
        from cliente.services import criar_pagamento_pix

        return criar_pagamento_pix(inscricao, valor, request=request)

    def sync_payment(self, pagamento: Pagamento) -> Pagamento:
        from cliente.services import sincronizar_status_livepix

        return sincronizar_status_livepix(pagamento)


class AsaasPaymentProvider(PaymentProvider):
    """
    Stub para integração futura com Asaas.
    Preparado para liberar acesso só após confirmação de pagamento.
    """

    def create_enrollment_payment(
        self,
        inscricao: Inscricao,
        valor: Decimal | None = None,
        *,
        request=None,
    ) -> Pagamento:
        raise NotImplementedError(
            "AsaasPaymentProvider ainda não está ativo. "
            "Configure PAYMENT_PROVIDER=livepix ou implemente a API Asaas."
        )

    def sync_payment(self, pagamento: Pagamento) -> Pagamento:
        raise NotImplementedError("AsaasPaymentProvider ainda não está ativo.")


def get_payment_provider() -> PaymentProvider:
    name = getattr(settings, "PAYMENT_PROVIDER", "livepix")
    if name == "asaas":
        return AsaasPaymentProvider()
    return LivePixPaymentProvider()


def inscricao_libera_acesso(inscricao: Inscricao) -> bool:
    """
    Gate único de acesso à aula.
    Hoje: status pago/confirmado.
    Futuro: cruzar com PaymentProvider / Asaas webhook.
    """
    return inscricao.libera_acesso()
