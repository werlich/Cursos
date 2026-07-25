# Generated manually for Live classroom evolution

from decimal import Decimal

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cliente", "0008_backfill_depoimento_localidade"),
    ]

    operations = [
        migrations.AddField(
            model_name="live",
            name="descricao",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="live",
            name="professor",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="live",
            name="duracao_minutos",
            field=models.PositiveSmallIntegerField(
                default=120,
                help_text="Duração estimada da aula (para marcar como encerrada).",
            ),
        ),
        migrations.AlterField(
            model_name="live",
            name="stream_url",
            field=models.URLField(
                blank=True,
                help_text="Link do Google Meet (ou outra sala). Sem API Google nesta versão.",
                verbose_name="Link Google Meet",
            ),
        ),
        migrations.CreateModel(
            name="Material",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("titulo", models.CharField(max_length=120)),
                (
                    "arquivo",
                    models.FileField(blank=True, upload_to="materiais/%Y/%m/"),
                ),
                (
                    "url",
                    models.URLField(
                        blank=True,
                        help_text="Link externo (se não houver arquivo).",
                    ),
                ),
                ("ativo", models.BooleanField(default=True)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                (
                    "live",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="materiais",
                        to="cliente.live",
                    ),
                ),
            ],
            options={
                "verbose_name": "Material",
                "verbose_name_plural": "Materiais",
                "ordering": ["titulo"],
            },
        ),
        migrations.CreateModel(
            name="Gravacao",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("titulo", models.CharField(max_length=120)),
                (
                    "url",
                    models.URLField(
                        help_text="Link da gravação (YouTube, Drive, etc.)"
                    ),
                ),
                (
                    "publicado_em",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                ("ativo", models.BooleanField(default=True)),
                (
                    "live",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="gravacoes",
                        to="cliente.live",
                    ),
                ),
            ],
            options={
                "verbose_name": "Gravação",
                "verbose_name_plural": "Gravações",
                "ordering": ["-publicado_em"],
            },
        ),
        migrations.CreateModel(
            name="LivePixCampanha",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("nome_campanha", models.CharField(max_length=120)),
                (
                    "qr_code",
                    models.ImageField(
                        blank=True,
                        help_text="Imagem do QR Code LivePix",
                        upload_to="livepix/qr/%Y/%m/",
                    ),
                ),
                (
                    "qr_code_url",
                    models.URLField(
                        blank=True,
                        help_text="URL da imagem do QR (alternativa ao upload).",
                    ),
                ),
                (
                    "link_pagamento",
                    models.URLField(
                        blank=True, help_text="Link Contribuir / checkout"
                    ),
                ),
                (
                    "meta_financeira",
                    models.DecimalField(
                        decimal_places=2, default=Decimal("0.00"), max_digits=10
                    ),
                ),
                (
                    "valor_arrecadado",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0.00"),
                        help_text="Preparar para integração futura com a API LivePix.",
                        max_digits=10,
                    ),
                ),
                ("ativo", models.BooleanField(default=True)),
                (
                    "live",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="livepix_campanha",
                        to="cliente.live",
                    ),
                ),
            ],
            options={
                "verbose_name": "Campanha LivePix",
                "verbose_name_plural": "Campanhas LivePix",
            },
        ),
    ]
