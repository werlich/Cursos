"""Formulários públicos do app Cliente."""

from __future__ import annotations

import re

from django import forms

from .models import Cliente, Live


class CadastroInscricaoForm(forms.Form):
    nome = forms.CharField(
        label="Nome completo",
        max_length=120,
        widget=forms.TextInput(attrs={"placeholder": "Seu nome", "autocomplete": "name"}),
    )
    email = forms.EmailField(
        label="E-mail",
        widget=forms.EmailInput(attrs={"placeholder": "voce@email.com", "autocomplete": "email"}),
    )
    whatsapp = forms.CharField(
        label="WhatsApp",
        max_length=20,
        widget=forms.TextInput(
            attrs={"placeholder": "48999999999", "inputmode": "tel", "autocomplete": "tel"}
        ),
        help_text="DDD + número, só dígitos",
    )
    live = forms.ModelChoiceField(
        label="Live / turma",
        queryset=Live.objects.none(),
        empty_label="Selecione a aula",
    )
    usar_credito = forms.BooleanField(
        label="Usar crédito disponível (se houver)",
        required=False,
        initial=False,
    )

    def __init__(self, *args, **kwargs):
        lives_qs = kwargs.pop("lives_qs", None)
        super().__init__(*args, **kwargs)
        if lives_qs is not None:
            self.fields["live"].queryset = lives_qs
        else:
            self.fields["live"].queryset = Live.objects.filter(
                status__in=[Live.Status.ABERTA, Live.Status.CONFIRMADA],
                curso__ativo=True,
            ).select_related("curso")

    def clean_whatsapp(self) -> str:
        raw = self.cleaned_data["whatsapp"]
        digits = re.sub(r"\D", "", raw)
        if len(digits) < 10 or len(digits) > 13:
            raise forms.ValidationError("Informe um WhatsApp válido com DDD.")
        return digits

    def clean_email(self) -> str:
        return self.cleaned_data["email"].strip().lower()

    def save_cliente(self) -> Cliente:
        data = self.cleaned_data
        cliente, _ = Cliente.objects.update_or_create(
            email=data["email"],
            defaults={"nome": data["nome"].strip(), "whatsapp": data["whatsapp"]},
        )
        return cliente
