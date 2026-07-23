"""Envio de confirmação WhatsApp ao aluno (e aviso à escola)."""

from __future__ import annotations

import logging
from urllib.parse import quote

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def digits_only(phone: str) -> str:
    d = "".join(c for c in (phone or "") if c.isdigit())
    if d and not d.startswith("55"):
        d = "55" + d
    return d


def school_whatsapp_digits() -> str:
    return digits_only(getattr(settings, "WHATSAPP_SCHOOL_NUMBER", "47933835108"))


def school_whatsapp_link(text: str = "") -> str:
    phone = school_whatsapp_digits()
    url = f"https://wa.me/{phone}"
    if text:
        url += f"?text={quote(text)}"
    return url


def mensagem_confirmacao(inscricao) -> str:
    live = inscricao.live
    cliente = inscricao.cliente
    when = live.data_hora.astimezone().strftime("%d/%m/%Y às %H:%M")
    return (
        f"Olá, {cliente.nome}! ✅ Inscrição confirmada na SIGNAU Cursos.\n\n"
        f"Curso: {live.curso.nome}\n"
        f"Live: {live.titulo}\n"
        f"Data: {when}\n"
        f"Valor: R$ {inscricao.pagamento.valor if hasattr(inscricao, 'pagamento') else live.curso.preco}\n\n"
        f"Guarde o link da sala (enviado no site). "
        f"Dúvidas: {school_whatsapp_link()}"
    )


def enviar_whatsapp(phone: str, text: str) -> bool:
    """
    Envia mensagem via WhatsApp Cloud API (Meta) se configurado.
    Retorna True se enviou com sucesso.
    """
    token = (getattr(settings, "WHATSAPP_ACCESS_TOKEN", "") or "").strip()
    phone_id = (getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "") or "").strip()
    to = digits_only(phone)
    if not to or not text:
        return False

    if token and phone_id:
        url = f"https://graph.facebook.com/v19.0/{phone_id}/messages"
        try:
            resp = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": "text",
                    "text": {"body": text[:4096]},
                },
                timeout=20,
            )
            if resp.status_code < 300:
                return True
            logger.warning("WhatsApp Cloud API %s: %s", resp.status_code, resp.text[:300])
        except requests.RequestException as exc:
            logger.exception("Falha WhatsApp Cloud API: %s", exc)

    # Fallback Evolution API (opcional)
    evo_url = (getattr(settings, "WHATSAPP_EVOLUTION_URL", "") or "").strip()
    evo_key = (getattr(settings, "WHATSAPP_EVOLUTION_KEY", "") or "").strip()
    if evo_url:
        try:
            headers = {"Content-Type": "application/json"}
            if evo_key:
                headers["apikey"] = evo_key
            resp = requests.post(
                evo_url,
                headers=headers,
                json={"number": to, "text": text},
                timeout=20,
            )
            if resp.status_code < 300:
                return True
            logger.warning("Evolution WhatsApp %s: %s", resp.status_code, resp.text[:300])
        except requests.RequestException as exc:
            logger.exception("Falha Evolution WhatsApp: %s", exc)

    logger.info("WhatsApp não enviado (API não configurada) para %s", to)
    return False


def enviar_confirmacao_inscricao(inscricao) -> bool:
    text = mensagem_confirmacao(inscricao)
    ok = enviar_whatsapp(inscricao.cliente.whatsapp, text)
    # Avisa a escola também
    aviso = (
        f"Nova inscrição SIGNAU Cursos\n"
        f"{inscricao.cliente.nome} | {inscricao.cliente.email} | {inscricao.cliente.whatsapp}\n"
        f"{inscricao.live.curso.nome} — {inscricao.live.titulo}"
    )
    enviar_whatsapp(school_whatsapp_digits(), aviso)
    return ok


def aluno_wa_me_link(inscricao) -> str:
    """Link wa.me para o aluno (fallback no browser — Message yourself / rascunho)."""
    phone = digits_only(inscricao.cliente.whatsapp)
    return f"https://wa.me/{phone}?text={quote(mensagem_confirmacao(inscricao))}"
