"""Admin Jazzmin — Cliente, Lives, Pagamentos e ações de turma."""

from __future__ import annotations

from django.contrib import admin, messages
from django.utils.html import format_html

from .models import Cliente, Credito, Curso, Inscricao, Live, Pagamento
from .services import emitir_creditos_se_nao_atingiu, estornar_pagamento


@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ("nome", "tipo", "preco", "ativo", "ordem")
    list_editable = ("preco", "ativo", "ordem")
    list_filter = ("ativo", "tipo")


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
    list_filter = ("status", "curso")
    search_fields = ("titulo",)
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
        "asaas_payment_id",
        "confirmado_em",
    )
    list_filter = ("status",)
    search_fields = ("asaas_payment_id", "inscricao__cliente__email")
    actions = ["action_estornar"]

    @admin.action(description="Estornar no Asaas")
    def action_estornar(self, request, queryset):
        ok = 0
        for pag in queryset:
            try:
                estornar_pagamento(pag)
                ok += 1
            except Exception as exc:
                self.message_user(
                    request, f"Falha no pagamento {pag.pk}: {exc}", messages.ERROR
                )
        if ok:
            self.message_user(request, f"{ok} estorno(s) processado(s).", messages.SUCCESS)


@admin.register(Credito)
class CreditoAdmin(admin.ModelAdmin):
    list_display = ("cliente", "valor", "ativo", "origem", "usado_em", "criado_em")
    list_filter = ("ativo",)
    search_fields = ("cliente__nome", "cliente__email")
