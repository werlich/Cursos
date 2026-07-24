"""Formulários públicos do app Cliente."""

from __future__ import annotations

import re

from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import Cliente, Curso, Depoimento, Live


class AdminEmailAuthenticationForm(AuthenticationForm):
    """Login administrativo por e-mail ou nome de usuário."""

    username = forms.CharField(
        label="E-mail ou usuário",
        widget=forms.TextInput(
            attrs={
                "autofocus": True,
                "autocomplete": "username",
                "placeholder": "sc7online@gmail.com",
                "class": "form-control",
            }
        ),
    )
    password = forms.CharField(
        label="Senha",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "current-password",
                "placeholder": "Senha",
                "class": "form-control",
            }
        ),
    )


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


class DepoimentoForm(forms.ModelForm):
    class Meta:
        model = Depoimento
        fields = ("nome", "curso", "nota", "texto", "email")
        widgets = {
            "nome": forms.TextInput(
                attrs={"placeholder": "Seu nome", "autocomplete": "name"}
            ),
            "curso": forms.TextInput(
                attrs={"placeholder": "Ex.: Arrais-Amador", "list": "cursos-sugeridos"}
            ),
            "nota": forms.Select(
                choices=[("", "Opcional")] + [(i, f"{i} ★") for i in range(1, 6)]
            ),
            "texto": forms.Textarea(
                attrs={
                    "placeholder": "Conte como foi a aula e o que mais te ajudou…",
                    "rows": 5,
                    "maxlength": 600,
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "placeholder": "opcional — só para contato interno",
                    "autocomplete": "email",
                }
            ),
        }
        labels = {
            "nome": "Nome",
            "curso": "Curso / aula",
            "nota": "Nota",
            "texto": "Seu depoimento",
            "email": "E-mail",
        }
        help_texts = {
            "email": "Não será publicado. Usado só se precisarmos confirmar algo.",
            "texto": "Será analisado antes de aparecer no site.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["nota"].required = False
        self.fields["email"].required = False
        self.curso_suggestions = list(
            Curso.objects.filter(ativo=True).order_by("ordem").values_list("nome", flat=True)
        )

    def clean_nome(self) -> str:
        return self.cleaned_data["nome"].strip()

    def clean_curso(self) -> str:
        return self.cleaned_data["curso"].strip()

    def clean_texto(self) -> str:
        texto = self.cleaned_data["texto"].strip()
        if len(texto) < 20:
            raise forms.ValidationError("Escreva pelo menos algumas linhas (mín. 20 caracteres).")
        return texto

    def clean_email(self) -> str:
        email = (self.cleaned_data.get("email") or "").strip().lower()
        return email

    def clean_nota(self):
        nota = self.cleaned_data.get("nota")
        if nota in ("", None):
            return None
        nota = int(nota)
        if nota < 1 or nota > 5:
            raise forms.ValidationError("A nota deve ser entre 1 e 5.")
        return nota

    def save(self, commit: bool = True) -> Depoimento:
        obj = super().save(commit=False)
        obj.status = Depoimento.Status.PENDENTE
        if commit:
            obj.save()
        return obj
