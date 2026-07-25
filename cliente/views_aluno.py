"""Área do aluno — Class Based Views (acesso por token de inscrição)."""

from __future__ import annotations

from django.conf import settings
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import DetailView, ListView, View

from .models import Gravacao, Inscricao, Live, Material
from .providers import get_meeting_provider
from .providers.payment import inscricao_libera_acesso


def _livepix_widget_url(campanha=None) -> str:
    if campanha is not None:
        url = campanha.widget_embed_url
        if url:
            return url
    return (getattr(settings, "LIVEPIX_WIDGET_URL", "") or "").strip()


def _inscricao_por_token(token: str) -> Inscricao:
    return get_object_or_404(
        Inscricao.objects.select_related("cliente", "live", "live__curso"),
        token_acesso=token,
    )


def _exige_acesso(inscricao: Inscricao) -> None:
    if not inscricao_libera_acesso(inscricao):
        raise PermissionError("pagamento")


class AlunoTokenMixin:
    """Resolve inscrição pelo token e bloqueia se não liberada."""

    inscricao: Inscricao

    def dispatch(self, request, *args, **kwargs):
        self.inscricao = _inscricao_por_token(kwargs["token"])
        try:
            _exige_acesso(self.inscricao)
        except PermissionError:
            return redirect("cliente:pagamento", token=self.inscricao.token_acesso)
        return super().dispatch(request, *args, **kwargs)

    def get_cliente(self):
        return self.inscricao.cliente


class AlunoAulasView(AlunoTokenMixin, ListView):
    """Lista aulas (lives) com inscrição paga/confirmada do mesmo cliente."""

    template_name = "cliente/aluno_aulas.html"
    context_object_name = "aulas"

    def get_queryset(self):
        cliente = self.get_cliente()
        return (
            Inscricao.objects.filter(
                cliente=cliente,
                status__in=[Inscricao.Status.PAGO, Inscricao.Status.CONFIRMADO],
            )
            .select_related("live", "live__curso", "live__livepix_campanha")
            .prefetch_related("live__materiais", "live__gravacoes")
            .order_by("live__data_hora")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        meeting = get_meeting_provider()
        cards = []
        for insc in ctx["aulas"]:
            live = insc.live
            join = meeting.join_info(live)
            material = live.materiais.filter(ativo=True).first()
            gravacao = live.gravacoes.filter(ativo=True).first()
            campanha = getattr(live, "livepix_campanha", None)
            if campanha and not campanha.ativo:
                campanha = None
            cards.append(
                {
                    "inscricao": insc,
                    "live": live,
                    "join": join,
                    "material": material,
                    "gravacao": gravacao,
                    "campanha": campanha,
                    "livepix_widget_url": _livepix_widget_url(campanha),
                }
            )
        ctx["cards"] = cards
        ctx["token"] = self.inscricao.token_acesso
        ctx["cliente"] = self.get_cliente()
        return ctx


class AlunoAulaDetailView(AlunoTokenMixin, DetailView):
    """Detalhe da aula: Meet, materiais, gravação e campanha LivePix."""

    template_name = "cliente/aluno_aula.html"
    context_object_name = "live"
    pk_url_kwarg = "live_id"

    def get_queryset(self):
        return Live.objects.select_related("curso", "livepix_campanha").prefetch_related(
            "materiais", "gravacoes"
        )

    def get_object(self, queryset=None):
        live = super().get_object(queryset)
        cliente = self.get_cliente()
        insc = (
            Inscricao.objects.filter(
                cliente=cliente,
                live=live,
                status__in=[Inscricao.Status.PAGO, Inscricao.Status.CONFIRMADO],
            )
            .select_related("live")
            .first()
        )
        if insc is None or not inscricao_libera_acesso(insc):
            raise Http404("Aula não disponível para este aluno.")
        self.aula_inscricao = insc
        return live

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        live = self.object
        join = get_meeting_provider().join_info(live)
        campanha = getattr(live, "livepix_campanha", None)
        if campanha and not campanha.ativo:
            campanha = None
        widget_url = _livepix_widget_url(campanha)
        ctx.update(
            {
                "token": self.inscricao.token_acesso,
                "cliente": self.get_cliente(),
                "inscricao": self.aula_inscricao,
                "join": join,
                "materiais": live.materiais.filter(ativo=True),
                "gravacoes": live.gravacoes.filter(ativo=True),
                "campanha": campanha,
                "livepix_widget_url": widget_url,
                "alunos": (
                    live.inscricoes.select_related("cliente")
                    .filter(
                        status__in=[
                            Inscricao.Status.PAGO,
                            Inscricao.Status.CONFIRMADO,
                        ]
                    )
                    .order_by("criada_em")
                ),
            }
        )
        return ctx


class MaterialDownloadView(AlunoTokenMixin, View):
    """Download/redirecionamento de material — só aluno matriculado na live."""

    def get(self, request, token: str, material_id: int):
        material = get_object_or_404(Material, pk=material_id, ativo=True)
        cliente = self.get_cliente()
        ok = Inscricao.objects.filter(
            cliente=cliente,
            live=material.live,
            status__in=[Inscricao.Status.PAGO, Inscricao.Status.CONFIRMADO],
        ).exists()
        if not ok:
            return HttpResponseForbidden("Material disponível apenas para matriculados.")
        url = material.resolve_url()
        if not url:
            raise Http404("Material sem arquivo/URL.")
        return redirect(url)


class GravacaoRedirectView(AlunoTokenMixin, View):
    def get(self, request, token: str, gravacao_id: int):
        gravacao = get_object_or_404(Gravacao, pk=gravacao_id, ativo=True)
        cliente = self.get_cliente()
        ok = Inscricao.objects.filter(
            cliente=cliente,
            live=gravacao.live,
            status__in=[Inscricao.Status.PAGO, Inscricao.Status.CONFIRMADO],
        ).exists()
        if not ok:
            return HttpResponseForbidden("Gravação disponível apenas para matriculados.")
        return redirect(gravacao.url)
