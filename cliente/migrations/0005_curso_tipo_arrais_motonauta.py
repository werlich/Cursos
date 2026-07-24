from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cliente", "0004_curso_tipo_not_unique"),
    ]

    operations = [
        migrations.AlterField(
            model_name="curso",
            name="tipo",
            field=models.CharField(
                choices=[
                    ("arrais", "Arrais-Amador"),
                    ("motonauta", "Motonauta"),
                    ("arrais_motonauta", "Arrais-Amador e Motonauta"),
                    ("mestre", "Mestre-Amador"),
                    ("capitao", "Capitão-Amador"),
                ],
                max_length=20,
            ),
        ),
    ]
