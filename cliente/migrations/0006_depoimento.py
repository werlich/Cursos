# Generated manually for Depoimento model

from django.db import migrations, models
from django.utils import timezone


def seed_depoimentos(apps, schema_editor):
    Depoimento = apps.get_model("cliente", "Depoimento")
    if Depoimento.objects.exists():
        return
    now = timezone.now()
    seeds = [
        (
            "Ana Paula",
            "Arrais-Amador",
            "A live foi objetiva e direta ao ponto. Passei no exame na primeira tentativa.",
            5,
        ),
        (
            "Ricardo M.",
            "Motonauta",
            "Didática excelente, com exemplos práticos de navegação. Recomendo demais.",
            5,
        ),
        (
            "Fernanda S.",
            "Mestre-Amador",
            "Conteúdo completo e suporte pelo WhatsApp. Valeu cada minuto da aula.",
            5,
        ),
    ]
    for nome, curso, texto, nota in seeds:
        Depoimento.objects.create(
            nome=nome,
            curso=curso,
            texto=texto,
            nota=nota,
            status="aprovado",
            revisado_em=now,
        )


def unseed_depoimentos(apps, schema_editor):
    Depoimento = apps.get_model("cliente", "Depoimento")
    Depoimento.objects.filter(
        nome__in=["Ana Paula", "Ricardo M.", "Fernanda S."],
        status="aprovado",
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("cliente", "0005_curso_tipo_arrais_motonauta"),
    ]

    operations = [
        migrations.CreateModel(
            name="Depoimento",
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
                ("nome", models.CharField(max_length=80)),
                (
                    "curso",
                    models.CharField(
                        help_text="Ex.: Arrais-Amador, Motonauta…",
                        max_length=80,
                    ),
                ),
                ("texto", models.TextField(max_length=600)),
                (
                    "nota",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        help_text="Nota de 1 a 5 (opcional)",
                        null=True,
                    ),
                ),
                ("email", models.EmailField(blank=True, max_length=254)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pendente", "Aguardando análise"),
                            ("aprovado", "Aprovado (publicado)"),
                            ("rejeitado", "Rejeitado"),
                        ],
                        db_index=True,
                        default="pendente",
                        max_length=20,
                    ),
                ),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("revisado_em", models.DateTimeField(blank=True, null=True)),
                ("observacao_interna", models.CharField(blank=True, max_length=255)),
            ],
            options={
                "verbose_name": "Depoimento",
                "verbose_name_plural": "Depoimentos",
                "ordering": ["-criado_em"],
            },
        ),
        migrations.RunPython(seed_depoimentos, unseed_depoimentos),
    ]
