"""Views públicas e webhook LivePix."""

from __future__ import annotations

import calendar
import json
import logging
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import CadastroInscricaoForm, DepoimentoForm
from .models import Curso, Depoimento, Inscricao, Live, Pagamento
from .qrcode_utils import qr_data_uri
from .services import (
    aplicar_credito,
    buscar_pagamento_livepix,
    confirmar_pagamento,
    criar_pagamento_pix,
)
from .whatsapp import school_whatsapp_link

logger = logging.getLogger(__name__)

_PAID_INSCRICAO = [Inscricao.Status.PAGO, Inscricao.Status.CONFIRMADO]

FALLBACK_TESTIMONIALS = [
    {
        "nome": "Ana Paula",
        "curso": "Arrais-Amador",
        "texto": "O curso foi objetivo e direto ao ponto. Passei no exame na primeira tentativa.",
        "nota": 5,
        "cidade": "Florianópolis",
        "estado": "SC",
        "localidade": "Florianópolis/SC",
    },
    {
        "nome": "Ricardo M.",
        "curso": "Motonauta",
        "texto": "Didática excelente, com exemplos práticos de navegação. Recomendo demais.",
        "nota": 5,
        "cidade": "Itajaí",
        "estado": "SC",
        "localidade": "Itajaí/SC",
    },
    {
        "nome": "Fernanda S.",
        "curso": "Mestre-Amador",
        "texto": "Conteúdo completo e suporte pelo WhatsApp. Valeu cada minuto da aula.",
        "nota": 5,
        "cidade": "Joinville",
        "estado": "SC",
        "localidade": "Joinville/SC",
    },
]


def _lives_annotated():
    return Live.objects.select_related("curso").annotate(
        inscritos_count=Count(
            "inscricoes",
            filter=Q(inscricoes__status__in=_PAID_INSCRICAO),
            distinct=True,
        )
    )


def _lives_abertas():
    return (
        _lives_annotated()
        .filter(
            status__in=[Live.Status.ABERTA, Live.Status.CONFIRMADA],
            curso__ativo=True,
            data_hora__gte=timezone.now() - timedelta(hours=2),
        )
        .order_by("data_hora")
    )


def _parse_agenda_month(raw: str | None) -> date:
    today = timezone.localdate()
    if raw:
        try:
            year_s, month_s = raw.split("-", 1)
            year, month = int(year_s), int(month_s)
            if 1 <= month <= 12 and 2000 <= year <= 2100:
                return date(year, month, 1)
        except (TypeError, ValueError):
            pass
    return date(today.year, today.month, 1)


def _shift_month(month_start: date, delta: int) -> date:
    month = month_start.month + delta
    year = month_start.year
    while month > 12:
        month -= 12
        year += 1
    while month < 1:
        month += 12
        year -= 1
    return date(year, month, 1)


def _local_day_bounds(day: date):
    """Inclusive start / exclusive end of a local calendar day (avoids MySQL __date TZ bugs)."""
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(day, time.min), tz)
    end = timezone.make_aware(datetime.combine(day + timedelta(days=1), time.min), tz)
    return start, end


def _agenda_month_context(month_start: date) -> dict:
    today = timezone.localdate()
    next_month = _shift_month(month_start, 1)
    prev_month = _shift_month(month_start, -1)
    range_start, _ = _local_day_bounds(month_start)
    range_end, _ = _local_day_bounds(next_month)

    lives_mes = list(
        _lives_annotated()
        .filter(
            status__in=[Live.Status.ABERTA, Live.Status.CONFIRMADA],
            curso__ativo=True,
            data_hora__gte=range_start,
            data_hora__lt=range_end,
        )
        .order_by("data_hora")
    )

    now = timezone.now()
    by_day: dict[date, list] = defaultdict(list)
    for live in lives_mes:
        local_dt = timezone.localtime(live.data_hora)
        live.is_past = local_dt < now
        by_day[local_dt.date()].append(live)

    cal = calendar.Calendar(firstweekday=calendar.MONDAY)
    weeks = []
    for week in cal.monthdatescalendar(month_start.year, month_start.month):
        weeks.append(
            [
                {
                    "date": day,
                    "in_month": day.month == month_start.month,
                    "is_today": day == today,
                    "is_past": day < today,
                    "is_weekend": day.weekday() >= 5,
                    "lives": by_day.get(day, []),
                }
                for day in week
            ]
        )

    return {
        "agenda_weeks": weeks,
        "agenda_month_label": date_format(month_start, "F Y"),
        "agenda_month_iso": month_start.strftime("%Y-%m"),
        "agenda_prev_mes": prev_month.strftime("%Y-%m"),
        "agenda_next_mes": next_month.strftime("%Y-%m"),
        "agenda_has_events": bool(lives_mes),
        "agenda_weekdays": ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"],
    }


@require_GET
def home(request: HttpRequest) -> HttpResponse:
    lives = _lives_abertas()
    proxima_por_curso = {}
    for live in lives:
        if live.curso_id not in proxima_por_curso:
            proxima_por_curso[live.curso_id] = live

    cursos = list(Curso.objects.filter(ativo=True))
    for curso in cursos:
        live = proxima_por_curso.get(curso.pk)
        if live:
            curso.proxima_live = live
            curso.inscritos = live.inscritos_pagos
            curso.meta_alunos = live.min_alunos
            curso.progress_pct = live.progresso_pct
        else:
            curso.proxima_live = None
            curso.inscritos = 0
            curso.meta_alunos = curso.min_alunos_padrao
            curso.progress_pct = 0

    form = CadastroInscricaoForm(lives_qs=lives)
    agenda = _agenda_month_context(_parse_agenda_month(request.GET.get("mes")))
    aprovados = list(
        Depoimento.objects.filter(status=Depoimento.Status.APROVADO).order_by("-revisado_em", "-criado_em")[:12]
    )
    testimonials = (
        [
            {
                "nome": d.nome,
                "curso": d.curso,
                "texto": d.texto,
                "nota": d.nota,
                "cidade": d.cidade,
                "estado": d.estado,
                "localidade": d.localidade,
            }
            for d in aprovados
        ]
        if aprovados
        else FALLBACK_TESTIMONIALS
    )
    avaliacao_url = request.build_absolute_uri(reverse("cliente:avaliacao"))
    return render(
        request,
        "cliente/home.html",
        {
            "cursos": cursos,
            "form": form,
            "dias_live": "Segundas, quartas e sextas",
            "testimonials": testimonials,
            "avaliacao_url": avaliacao_url,
            "avaliacao_qr": qr_data_uri(avaliacao_url),
            "whatsapp_url": school_whatsapp_link(
                "Olá! Vim pelo site cursos.signau.cc e quero saber mais sobre os cursos."
            ),
            **agenda,
        },
    )


@require_http_methods(["GET", "POST"])
def avaliacao(request: HttpRequest) -> HttpResponse:
    enviado = False
    if request.method == "POST":
        form = DepoimentoForm(request.POST)
        if form.is_valid():
            form.save()
            enviado = True
            form = DepoimentoForm()
    else:
        form = DepoimentoForm()
    return render(
        request,
        "cliente/avaliacao.html",
        {
            "form": form,
            "enviado": enviado,
            "curso_suggestions": getattr(form, "curso_suggestions", []),
        },
    )


@require_GET
def quem_sou(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "cliente/quem_sou.html",
        {
            "whatsapp_url": school_whatsapp_link(
                "Olá! Vi a página Quem sou e gostaria de conversar."
            ),
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
                form.add_error(None, "Já existe inscrição para este e-mail neste curso.")
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
        from .providers import get_payment_provider

        pagamento_obj = get_payment_provider().create_enrollment_payment(
            insc, request=request
        )
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
        from .providers import get_payment_provider

        get_payment_provider().sync_payment(pag)
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
    """Compatibilidade: redireciona a sala antiga para a área do aluno."""
    insc = get_object_or_404(
        Inscricao.objects.select_related("live", "cliente"),
        token_acesso=token,
    )
    if not insc.libera_acesso():
        return redirect("cliente:pagamento", token=token)
    return redirect(
        "cliente:aluno_aula",
        token=token,
        live_id=insc.live_id,
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
