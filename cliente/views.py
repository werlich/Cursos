"""Views públicas e webhook LivePix."""

from __future__ import annotations

import json
import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import CadastroInscricaoForm
from .models import Curso, Inscricao, Live, Pagamento
from .services import (
    aplicar_credito,
    buscar_pagamento_livepix,
    confirmar_pagamento,
    criar_pagamento_pix,
    sincronizar_status_livepix,
)

logger = logging.getLogger(__name__)


def _lives_abertas():
    from django.utils import timezone

    return (
        Live.objects.filter(
            status__in=[Live.Status.ABERTA, Live.Status.CONFIRMADA],
            curso__ativo=True,
            data_hora__gte=timezone.now() - timezone.timedelta(hours=2),
        )
        .select_related("curso")
        .order_by("data_hora")
    )


@require_GET
def home(request: HttpRequest) -> HttpResponse:
    cursos = Curso.objects.filter(ativo=True)
    lives = _lives_abertas()
    form = CadastroInscricaoForm(lives_qs=lives)
    return render(
        request,
        "cliente/home.html",
        {
            "cursos": cursos,
            "lives": lives,
            "form": form,
            "dias_live": "Segundas, quartas e sextas",
        },
    )


@require_http_methods(["GET", "POST"])
def cadastro(request: HttpRequest) -> HttpResponse:
    lives = _lives_abertas()
    if request.method == "POST":
        form = CadastroInscricaoForm(request.POST, lives_qs=lives)
        if form.is_valid():
            cliente = form.save_cliente()
            live = form.cleaned_data["live"]
            usar_credito = form.cleaned_data.get("usar_credito")

            if usar_credito:
                insc = aplicar_credito(cliente, live)
                if insc:
                    return redirect("cliente:sala", token=insc.token_acesso)

            try:
                with transaction.atomic():
                    insc, created = Inscricao.objects.get_or_create(
                        cliente=cliente,
                        live=live,
                        defaults={"status": Inscricao.Status.PENDENTE},
                    )
                    if not created and insc.status in (
                        Inscricao.Status.PAGO,
                        Inscricao.Status.CONFIRMADO,
                    ):
                        return redirect("cliente:sala", token=insc.token_acesso)
                    if not created and hasattr(insc, "pagamento"):
                        return redirect("cliente:pagamento", token=insc.token_acesso)
                    criar_pagamento_pix(insc, request=request)
            except IntegrityError:
                form.add_error(None, "Já existe inscrição para este e-mail nesta live.")
            except Exception as exc:
                logger.exception("Erro ao criar pagamento: %s", exc)
                form.add_error(None, f"Não foi possível gerar o PIX: {exc}")
            else:
                return redirect("cliente:pagamento", token=insc.token_acesso)
    else:
        initial = {}
        live_id = request.GET.get("live")
        if live_id:
            initial["live"] = live_id
        form = CadastroInscricaoForm(initial=initial, lives_qs=lives)

    return render(
        request,
        "cliente/cadastro.html",
        {"form": form, "lives": lives},
    )


@require_GET
def pagamento(request: HttpRequest, token: str) -> HttpResponse:
    insc = get_object_or_404(Inscricao.objects.select_related("live", "cliente"), token_acesso=token)
    if insc.status in (Inscricao.Status.PAGO, Inscricao.Status.CONFIRMADO):
        return redirect("cliente:sala", token=token)
    pagamento_obj = getattr(insc, "pagamento", None)
    if pagamento_obj is None:
        pagamento_obj = criar_pagamento_pix(insc, request=request)
    return render(
        request,
        "cliente/pagamento.html",
        {
            "inscricao": insc,
            "pagamento": pagamento_obj,
            "demo": getattr(settings, "LIVEPIX_DEMO", True),
        },
    )


@require_GET
def pagamento_retorno(request: HttpRequest, token: str) -> HttpResponse:
    """Retorno do checkout LivePix — tenta sincronizar e manda para sala ou pagamento."""
    insc = get_object_or_404(Inscricao, token_acesso=token)
    pag = getattr(insc, "pagamento", None)
    if pag:
        sincronizar_status_livepix(pag)
        insc.refresh_from_db()
    if insc.status in (Inscricao.Status.PAGO, Inscricao.Status.CONFIRMADO):
        return redirect("cliente:sala", token=token)
    return redirect("cliente:pagamento", token=token)


@require_POST
def pagamento_demo_confirmar(request: HttpRequest, token: str) -> HttpResponse:
    """Somente em LIVEPIX_DEMO: simula confirmação PIX."""
    if not getattr(settings, "LIVEPIX_DEMO", True):
        return HttpResponseForbidden("Disponível apenas em modo DEMO")
    insc = get_object_or_404(Inscricao, token_acesso=token)
    pag = get_object_or_404(Pagamento, inscricao=insc)
    confirmar_pagamento(pag)
    return redirect("cliente:sala", token=token)


@require_GET
def status_pagamento(request: HttpRequest, token: str) -> JsonResponse:
    insc = get_object_or_404(Inscricao, token_acesso=token)
    pago = insc.status in (Inscricao.Status.PAGO, Inscricao.Status.CONFIRMADO)
    return JsonResponse({"pago": pago, "status": insc.status})


@require_GET
def sala(request: HttpRequest, token: str) -> HttpResponse:
    insc = get_object_or_404(
        Inscricao.objects.select_related("live", "live__curso", "cliente"),
        token_acesso=token,
    )
    if insc.status not in (
        Inscricao.Status.PAGO,
        Inscricao.Status.CONFIRMADO,
    ):
        return redirect("cliente:pagamento", token=token)
    live = insc.live
    liberado = live.status in (Live.Status.CONFIRMADA, Live.Status.ABERTA, Live.Status.ENCERRADA)
    return render(
        request,
        "cliente/sala.html",
        {
            "inscricao": insc,
            "live": live,
            "liberado": liberado,
            "stream_url": live.stream_url,
            "faltam": live.vagas_restantes,
            "min_alunos": live.min_alunos,
            "inscritos": live.inscritos_pagos,
        },
    )


@csrf_exempt
@require_POST
def livepix_webhook(request: HttpRequest) -> HttpResponse:
    """
    Webhook LivePix — evento new + resource.type payment.
    Payload mínimo: { event, resource: { id, reference, type } }
    """
    try:
        payload = json.loads(request.body.decode() or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "json"}, status=400)

    event = payload.get("event") or ""
    resource = payload.get("resource") or {}
    rtype = resource.get("type") or ""
    payment_id = resource.get("id") or ""
    reference = resource.get("reference") or ""

    if rtype and rtype != "payment":
        return JsonResponse({"ok": True, "ignored": True, "reason": "not_payment"})

    if event and event not in ("new", "payment", "PAYMENT_RECEIVED"):
        # aceitar "new" (doc) e variações
        if event not in ("new",):
            logger.info("Webhook LivePix evento ignorado: %s", event)
            return JsonResponse({"ok": True, "ignored": True, "event": event})

    pag = buscar_pagamento_livepix(payment_id=payment_id, reference=reference)
    if not pag:
        logger.warning(
            "Webhook LivePix pagamento desconhecido id=%s ref=%s", payment_id, reference
        )
        return JsonResponse({"ok": True, "unknown": True})

    if payment_id and not pag.livepix_payment_id:
        pag.livepix_payment_id = payment_id
        pag.save(update_fields=["livepix_payment_id"])

    confirmar_pagamento(pag)
    return JsonResponse({"ok": True})
