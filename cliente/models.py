"""Modelos do app Cliente — cadastro, lives, pagamentos e créditos."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class Curso(models.Model):
    class Tipo(models.TextChoices):
        ARRAIS = "arrais", "Arrais-Amador"
        MOTONAUTA = "motonauta", "Motonauta"
        MESTRE = "mestre", "Mestre-Amador"
        CAPITAO = "capitao", "Capitão-Amador"

    tipo = models.CharField(max_length=20, choices=Tipo.choices, unique=True)
    nome = models.CharField(max_length=80)
    descricao = models.TextField(blank=True)
    preco = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("29.90"))
    ativo = models.BooleanField(default=True)
    ordem = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["ordem", "nome"]
        verbose_name = "Curso"
        verbose_name_plural = "Cursos"

    def __str__(self) -> str:
        return self.nome


class Live(models.Model):
    class Status(models.TextChoices):
        ABERTA = "aberta", "Aberta para inscrição"
        CONFIRMADA = "confirmada", "Turma confirmada (≥ mínimo)"
        CREDITO = "credito", "Não atingiu mínimo — créditos emitidos"
        ENCERRADA = "encerrada", "Encerrada"
        CANCELADA = "cancelada", "Cancelada"

    curso = models.ForeignKey(Curso, on_delete=models.PROTECT, related_name="lives")
    titulo = models.CharField(max_length=120)
    data_hora = models.DateTimeField()
    stream_url = models.URLField(
        blank=True,
        help_text="Link da transmissão OBS (YouTube Live, Vimeo, player próprio, etc.)",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ABERTA
    )
    min_alunos = models.PositiveSmallIntegerField(
        default=10,
        help_text="Mínimo de pagamentos confirmados para fechar a turma",
    )
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["data_hora"]
        verbose_name = "Live"
        verbose_name_plural = "Lives"

    def __str__(self) -> str:
        return f"{self.titulo} — {timezone.localtime(self.data_hora):%d/%m/%Y %H:%M}"

    @property
    def inscritos_pagos(self) -> int:
        return self.inscricoes.filter(
            status__in=[Inscricao.Status.PAGO, Inscricao.Status.CONFIRMADO]
        ).count()

    @property
    def atingiu_minimo(self) -> bool:
        return self.inscritos_pagos >= self.min_alunos

    @property
    def vagas_restantes(self) -> int:
        return max(0, self.min_alunos - self.inscritos_pagos)

    @property
    def is_segunda_quarta_sexta(self) -> bool:
        # 0=segunda … 6=domingo (Django week_day is different; use weekday())
        return timezone.localtime(self.data_hora).weekday() in (0, 2, 4)


class Cliente(models.Model):
    nome = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    whatsapp = models.CharField(max_length=20, help_text="Somente dígitos com DDD, ex: 48999999999")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"

    def __str__(self) -> str:
        return f"{self.nome} <{self.email}>"

    @property
    def whatsapp_link(self) -> str:
        digits = "".join(c for c in self.whatsapp if c.isdigit())
        if digits and not digits.startswith("55"):
            digits = "55" + digits
        return f"https://wa.me/{digits}" if digits else ""


class Inscricao(models.Model):
    class Status(models.TextChoices):
        PENDENTE = "pendente", "Aguardando pagamento"
        PAGO = "pago", "Pago"
        CONFIRMADO = "confirmado", "Confirmado na turma"
        CREDITO = "credito", "Convertido em crédito"
        CANCELADO = "cancelado", "Cancelado"
        ESTORNADO = "estornado", "Estornado"

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="inscricoes")
    live = models.ForeignKey(Live, on_delete=models.PROTECT, related_name="inscricoes")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDENTE
    )
    usou_credito = models.BooleanField(default=False)
    token_acesso = models.CharField(max_length=64, unique=True, editable=False)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criada_em"]
        verbose_name = "Inscrição"
        verbose_name_plural = "Inscrições"
        unique_together = [("cliente", "live")]

    def __str__(self) -> str:
        return f"{self.cliente.nome} → {self.live}"

    def save(self, *args, **kwargs):
        if not self.token_acesso:
            import secrets

            self.token_acesso = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)


class Pagamento(models.Model):
    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        CONFIRMADO = "confirmado", "Confirmado"
        ESTORNADO = "estornado", "Estornado"
        EXPIRADO = "expirado", "Expirado"
        FALHA = "falha", "Falha"

    inscricao = models.OneToOneField(
        Inscricao, on_delete=models.CASCADE, related_name="pagamento"
    )
    valor = models.DecimalField(max_digits=8, decimal_places=2)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDENTE
    )
    asaas_payment_id = models.CharField(max_length=64, blank=True, db_index=True)
    asaas_customer_id = models.CharField(max_length=64, blank=True)
    pix_qr_code = models.TextField(blank=True, help_text="Imagem QR em base64 ou URL")
    pix_copia_cola = models.TextField(blank=True)
    invoice_url = models.URLField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    confirmado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Pagamento"
        verbose_name_plural = "Pagamentos"

    def __str__(self) -> str:
        return f"Pagamento {self.pk} — {self.inscricao} ({self.status})"


class Credito(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="creditos")
    valor = models.DecimalField(max_digits=8, decimal_places=2)
    origem = models.ForeignKey(
        Inscricao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="creditos_gerados",
    )
    usado_em = models.ForeignKey(
        Inscricao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="creditos_usados",
    )
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    observacao = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Crédito"
        verbose_name_plural = "Créditos"

    def __str__(self) -> str:
        estado = "ativo" if self.ativo else "usado"
        return f"Crédito R$ {self.valor} — {self.cliente.nome} ({estado})"


def preco_padrao() -> Decimal:
    return Decimal(str(getattr(settings, "PRECO_PADRAO", "29.90")))
