from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cliente", "0003_curso_min_alunos"),
    ]

    operations = [
        migrations.AlterField(
            model_name="curso",
            name="tipo",
            field=models.CharField(
                choices=[
                    ("arrais", "Arrais-Amador"),
                    ("motonauta", "Motonauta"),
                    ("mestre", "Mestre-Amador"),
                    ("capitao", "Capitão-Amador"),
                ],
                max_length=20,
            ),
        ),
    ]
