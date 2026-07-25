"""Modelos do app Cliente — cadastro, cursos agendados, pagamentos e créditos."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class Curso(models.Model):
    class Tipo(models.TextChoices):
        ARRAIS = "arrais", "Arrais-Amador"
        MOTONAUTA = "motonauta", "Motonauta"
        ARRAIS_MOTONAUTA = "arrais_motonauta", "Arrais-Amador e Motonauta"
        MESTRE = "mestre", "Mestre-Amador"
        CAPITAO = "capitao", "Capitão-Amador"
        OPERADOR_RADIO = "operador_radio", "Operador Radiotelefonista Geral"

    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    nome = models.CharField(max_length=80)
    descricao = models.TextField(blank=True)
    preco = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("29.90"))
    min_alunos_padrao = models.PositiveSmallIntegerField(
        default=5,
        help_text="Mínimo de alunos pagos para fechar turma neste curso (padrão das turmas)",
    )
    ativo = models.BooleanField(default=True)
    mostrar_aproveite = models.BooleanField(
        default=False,
        verbose_name="Banner Promocional",
        help_text="Exibe o selo “Promocional” acima do preço na página de cursos.",
    )
    ordem = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["ordem", "nome"]
        verbose_name = "Curso"
        verbose_name_plural = "Cursos"

    def __str__(self) -> str:
        return self.nome

    @property
    def imagem_static(self) -> str:
        """Caminho relativo em static/ para a imagem ilustrativa do curso."""
        mapping = {
            self.Tipo.ARRAIS: "img/cursos/arrais.jpg",
            self.Tipo.MOTONAUTA: "img/cursos/motonauta.jpg",
            self.Tipo.ARRAIS_MOTONAUTA: "img/cursos/arrais_motonauta.jpg",
            self.Tipo.MESTRE: "img/cursos/mestre.jpg",
            self.Tipo.CAPITAO: "img/cursos/mestre.jpg",
            self.Tipo.OPERADOR_RADIO: "img/cursos/operador_radio.jpg",
        }
        return mapping.get(self.tipo, "img/cursos/arrais.jpg")

    @property
    def imagem_alt(self) -> str:
        alts = {
            self.Tipo.ARRAIS: "Lancha — curso Arrais-Amador",
            self.Tipo.MOTONAUTA: "Jet ski — curso Motonauta",
            self.Tipo.ARRAIS_MOTONAUTA: "Lancha e jet ski — Arrais-Amador e Motonauta",
            self.Tipo.MESTRE: "Cartas náuticas — curso Mestre-Amador",
            self.Tipo.CAPITAO: "Cartas náuticas — curso Capitão-Amador",
            self.Tipo.OPERADOR_RADIO: "Rádio VHF — curso Operador Radiotelefonista Geral",
        }
        return alts.get(self.tipo, self.nome)


class Live(models.Model):
    class Status(models.TextChoices):
        ABERTA = "aberta", "Aberta para inscrição"
        CONFIRMADA = "confirmada", "Turma confirmada (≥ mínimo)"
        CREDITO = "credito", "Não atingiu mínimo — créditos emitidos"
        ENCERRADA = "encerrada", "Encerrada"
        CANCELADA = "cancelada", "Cancelada"

    class MeetStatus(models.TextChoices):
        ANTES = "antes", "Ainda não disponível"
        ABERTA = "aberta", "Aula aberta"
        ENCERRADA = "encerrada", "Aula encerrada"

    curso = models.ForeignKey(Curso, on_delete=models.PROTECT, related_name="lives")
    titulo = models.CharField(max_length=120)
    descricao = models.TextField(blank=True)
    professor = models.CharField(max_length=120, blank=True)
    data_hora = models.DateTimeField()
    duracao_minutos = models.PositiveSmallIntegerField(
        default=120,
        help_text="Duração estimada da aula (para marcar como encerrada).",
    )
    stream_url = models.URLField(
        blank=True,
        help_text="Link do Google Meet (ou outra sala). Sem API Google nesta versão.",
        verbose_name="Link Google Meet",
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
        verbose_name = "Curso agendado"
        verbose_name_plural = "Cursos agendados"

    def __str__(self) -> str:
        return f"{self.titulo} — {timezone.localtime(self.data_hora):%d/%m/%Y %H:%M}"

    @property
    def inscritos_pagos(self) -> int:
        annotated = getattr(self, "inscritos_count", None)
        if annotated is not None:
            return int(annotated)
        return self.inscricoes.filter(
            status__in=[Inscricao.Status.PAGO, Inscricao.Status.CONFIRMADO]
        ).count()

    @property
    def progresso_pct(self) -> int:
        meta = self.min_alunos or 1
        return min(100, int(round(self.inscritos_pagos * 100 / meta)))

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

    @property
    def meet_abre_em(self):
        return self.data_hora - timezone.timedelta(minutes=5)

    @property
    def meet_fecha_em(self):
        return self.data_hora + timezone.timedelta(minutes=self.duracao_minutos or 120)

    @property
    def meet_status(self) -> str:
        if self.status in (self.Status.ENCERRADA, self.Status.CANCELADA, self.Status.CREDITO):
            return self.MeetStatus.ENCERRADA
        now = timezone.now()
        if now < self.meet_abre_em:
            return self.MeetStatus.ANTES
        if now > self.meet_fecha_em:
            return self.MeetStatus.ENCERRADA
        return self.MeetStatus.ABERTA

    @property
    def meet_pode_entrar(self) -> bool:
        return bool(self.stream_url) and self.meet_status == self.MeetStatus.ABERTA


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
    live = models.ForeignKey(
        Live,
        on_delete=models.PROTECT,
        related_name="inscricoes",
        verbose_name="Curso agendado",
    )
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

    def libera_acesso(self) -> bool:
        """
        Gate de acesso à aula.
        Hoje: inscrição paga/confirmada.
        Futuro: também validar confirmação Asaas / PaymentProvider.
        """
        return self.status in (self.Status.PAGO, self.Status.CONFIRMADO)


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
    livepix_payment_id = models.CharField(max_length=64, blank=True, db_index=True)
    livepix_reference = models.CharField(max_length=64, blank=True, db_index=True)
    pix_qr_code = models.TextField(blank=True, help_text="Imagem QR em base64 ou URL")
    pix_copia_cola = models.TextField(blank=True)
    invoice_url = models.URLField(blank=True, help_text="URL do checkout LivePix")
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


class Depoimento(models.Model):
    class Status(models.TextChoices):
        PENDENTE = "pendente", "Aguardando análise"
        APROVADO = "aprovado", "Aprovado (publicado)"
        REJEITADO = "rejeitado", "Rejeitado"

    class UF(models.TextChoices):
        AC = "AC", "AC"
        AL = "AL", "AL"
        AP = "AP", "AP"
        AM = "AM", "AM"
        BA = "BA", "BA"
        CE = "CE", "CE"
        DF = "DF", "DF"
        ES = "ES", "ES"
        GO = "GO", "GO"
        MA = "MA", "MA"
        MT = "MT", "MT"
        MS = "MS", "MS"
        MG = "MG", "MG"
        PA = "PA", "PA"
        PB = "PB", "PB"
        PR = "PR", "PR"
        PE = "PE", "PE"
        PI = "PI", "PI"
        RJ = "RJ", "RJ"
        RN = "RN", "RN"
        RS = "RS", "RS"
        RO = "RO", "RO"
        RR = "RR", "RR"
        SC = "SC", "SC"
        SP = "SP", "SP"
        SE = "SE", "SE"
        TO = "TO", "TO"

    nome = models.CharField(max_length=80)
    cidade = models.CharField(max_length=80, blank=True)
    estado = models.CharField(max_length=2, choices=UF.choices, blank=True)
    curso = models.CharField(max_length=80, help_text="Ex.: Arrais-Amador, Motonauta…")
    texto = models.TextField(max_length=600)
    nota = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Nota de 1 a 5 (opcional)",
    )
    email = models.EmailField(blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDENTE, db_index=True
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    revisado_em = models.DateTimeField(null=True, blank=True)
    observacao_interna = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Depoimento"
        verbose_name_plural = "Depoimentos"

    def __str__(self) -> str:
        return f"{self.nome} — {self.get_status_display()}"

    @property
    def localidade(self) -> str:
        cidade = (self.cidade or "").strip()
        estado = (self.estado or "").strip().upper()
        if cidade and estado:
            return f"{cidade}/{estado}"
        return cidade or estado


class Material(models.Model):
    live = models.ForeignKey(
        Live,
        on_delete=models.CASCADE,
        related_name="materiais",
        verbose_name="Curso agendado",
    )
    titulo = models.CharField(max_length=120)
    arquivo = models.FileField(upload_to="materiais/%Y/%m/", blank=True)
    url = models.URLField(blank=True, help_text="Link externo (se não houver arquivo).")
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["titulo"]
        verbose_name = "Material"
        verbose_name_plural = "Materiais"

    def __str__(self) -> str:
        return f"{self.titulo} ({self.live})"

    @property
    def tem_download(self) -> bool:
        return bool(self.arquivo) or bool(self.url)

    def resolve_url(self) -> str:
        if self.arquivo:
            return self.arquivo.url
        return self.url or ""


class Gravacao(models.Model):
    live = models.ForeignKey(
        Live,
        on_delete=models.CASCADE,
        related_name="gravacoes",
        verbose_name="Curso agendado",
    )
    titulo = models.CharField(max_length=120)
    url = models.URLField(help_text="Link da gravação (YouTube, Drive, etc.)")
    publicado_em = models.DateTimeField(default=timezone.now)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ["-publicado_em"]
        verbose_name = "Gravação"
        verbose_name_plural = "Gravações"

    def __str__(self) -> str:
        return f"{self.titulo} ({self.live})"


class LivePixCampanha(models.Model):
    """Configuração de apoio/doação LivePix (somente exibição nesta versão)."""

    live = models.OneToOneField(
        Live,
        on_delete=models.CASCADE,
        related_name="livepix_campanha",
        verbose_name="Curso agendado",
    )
    nome_campanha = models.CharField(max_length=120)
    widget_url = models.URLField(
        blank=True,
        help_text="Embed LivePix, ex.: https://widget.livepix.gg/embed/…",
    )
    qr_code = models.ImageField(
        upload_to="livepix/qr/%Y/%m/",
        blank=True,
        help_text="Imagem do QR Code LivePix",
    )
    qr_code_url = models.URLField(
        blank=True, help_text="URL da imagem do QR (alternativa ao upload)."
    )
    link_pagamento = models.URLField(blank=True, help_text="Link Contribuir / checkout")
    meta_financeira = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    valor_arrecadado = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Preparar para integração futura com a API LivePix.",
    )
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Campanha LivePix"
        verbose_name_plural = "Campanhas LivePix"

    def __str__(self) -> str:
        return f"{self.nome_campanha} — {self.live}"

    @property
    def qr_display_url(self) -> str:
        if self.qr_code:
            return self.qr_code.url
        return self.qr_code_url or ""

    @property
    def widget_embed_url(self) -> str:
        url = (self.widget_url or "").strip()
        if url:
            return url
        return (getattr(settings, "LIVEPIX_WIDGET_URL", "") or "").strip()
