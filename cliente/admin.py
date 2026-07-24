"""Admin Jazzmin — Cliente, Lives, Pagamentos e ações de turma."""

from __future__ import annotations

from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html

from .models import Cliente, Credito, Curso, Depoimento, Inscricao, Live, Pagamento
from .services import emitir_creditos_se_nao_atingiu, estornar_pagamento


@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ("nome", "tipo", "preco", "min_alunos_padrao", "ativo", "ordem")
    list_editable = ("preco", "min_alunos_padrao", "ativo", "ordem")
    list_filter = ("ativo", "tipo")
    fields = (
        "nome",
        "tipo",
        "descricao",
        "preco",
        "min_alunos_padrao",
        "ativo",
        "ordem",
    )


class InscricaoInline(admin.TabularInline):
    model = Inscricao
    extra = 0
    readonly_fields = ("cliente", "status", "usou_credito", "token_acesso", "criada_em")
    can_delete = False


@admin.register(Live)
class LiveAdmin(admin.ModelAdmin):
    list_display = (
        "titulo",
        "curso",
        "data_hora",
        "status",
        "inscritos_display",
        "min_alunos",
        "tem_stream",
    )
    list_editable = ("min_alunos", "status")
    list_filter = ("status", "curso")
    search_fields = ("titulo",)
    fields = (
        "curso",
        "titulo",
        "data_hora",
        "min_alunos",
        "status",
        "stream_url",
    )
    inlines = [InscricaoInline]
    actions = ["action_emitir_creditos", "action_marcar_confirmada", "action_encerrar"]

    @admin.display(description="Pagos")
    def inscritos_display(self, obj: Live) -> str:
        return f"{obj.inscritos_pagos}/{obj.min_alunos}"

    @admin.display(boolean=True, description="OBS")
    def tem_stream(self, obj: Live) -> bool:
        return bool(obj.stream_url)

    @admin.action(description="Emitir créditos (turma < mínimo)")
    def action_emitir_creditos(self, request, queryset):
        total = 0
        for live in queryset:
            total += emitir_creditos_se_nao_atingiu(live, forcar=True)
        self.message_user(request, f"{total} crédito(s) emitido(s).", messages.SUCCESS)

    @admin.action(description="Marcar turma como confirmada")
    def action_marcar_confirmada(self, request, queryset):
        queryset.update(status=Live.Status.CONFIRMADA)
        self.message_user(request, "Lives confirmadas.", messages.SUCCESS)

    @admin.action(description="Encerrar live")
    def action_encerrar(self, request, queryset):
        queryset.update(status=Live.Status.ENCERRADA)
        self.message_user(request, "Lives encerradas.", messages.SUCCESS)


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("nome", "email", "whatsapp", "whatsapp_btn", "criado_em")
    search_fields = ("nome", "email", "whatsapp")
    readonly_fields = ("criado_em", "atualizado_em")

    @admin.display(description="WhatsApp")
    def whatsapp_btn(self, obj: Cliente):
        if not obj.whatsapp_link:
            return "—"
        return format_html('<a href="{}" target="_blank" rel="noopener">Abrir</a>', obj.whatsapp_link)


@admin.register(Inscricao)
class InscricaoAdmin(admin.ModelAdmin):
    list_display = ("cliente", "live", "status", "usou_credito", "criada_em")
    list_filter = ("status", "usou_credito", "live__curso")
    search_fields = ("cliente__nome", "cliente__email", "token_acesso")
    readonly_fields = ("token_acesso", "criada_em")


@admin.register(Pagamento)
class PagamentoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "inscricao",
        "valor",
        "status",
        "livepix_reference",
        "confirmado_em",
    )
    list_filter = ("status",)
    search_fields = (
        "livepix_payment_id",
        "livepix_reference",
        "inscricao__cliente__email",
    )
    actions = ["action_estornar"]

    @admin.action(description="Marcar estornado (manual na LivePix)")
    def action_estornar(self, request, queryset):
        ok = 0
        for pag in queryset:
            estornar_pagamento(pag)
            ok += 1
        self.message_user(
            request,
            f"{ok} marcado(s) como estornado. Faça a devolução na carteira LivePix se necessário.",
            messages.SUCCESS,
        )


@admin.register(Credito)
class CreditoAdmin(admin.ModelAdmin):
    list_display = ("cliente", "valor", "ativo", "origem", "usado_em", "criado_em")
    list_filter = ("ativo",)
    search_fields = ("cliente__nome", "cliente__email")


@admin.register(Depoimento)
class DepoimentoAdmin(admin.ModelAdmin):
    list_display = ("nome", "curso", "nota", "status", "preview", "criado_em")
    list_filter = ("status", "curso")
    search_fields = ("nome", "curso", "texto", "email")
    list_editable = ("status",)
    readonly_fields = ("criado_em", "revisado_em")
    actions = ["action_aprovar", "action_rejeitar"]
    fields = (
        "nome",
        "curso",
        "nota",
        "texto",
        "email",
        "status",
        "observacao_interna",
        "criado_em",
        "revisado_em",
    )

    @admin.display(description="Texto")
    def preview(self, obj: Depoimento) -> str:
        t = obj.texto or ""
        return (t[:72] + "…") if len(t) > 72 else t

    def save_model(self, request, obj, form, change):
        if change and "status" in form.changed_data:
            obj.revisado_em = timezone.now()
        super().save_model(request, obj, form, change)

    @admin.action(description="Aprovar e publicar")
    def action_aprovar(self, request, queryset):
        n = queryset.update(status=Depoimento.Status.APROVADO, revisado_em=timezone.now())
        self.message_user(request, f"{n} depoimento(s) aprovado(s).", messages.SUCCESS)

    @admin.action(description="Rejeitar")
    def action_rejeitar(self, request, queryset):
        n = queryset.update(status=Depoimento.Status.REJEITADO, revisado_em=timezone.now())
        self.message_user(request, f"{n} depoimento(s) rejeitado(s).", messages.WARNING)
