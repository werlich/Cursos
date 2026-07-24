from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cliente", "0006_depoimento"),
    ]

    operations = [
        migrations.AddField(
            model_name="depoimento",
            name="cidade",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="depoimento",
            name="estado",
            field=models.CharField(
                blank=True,
                choices=[
                    ("AC", "AC"),
                    ("AL", "AL"),
                    ("AP", "AP"),
                    ("AM", "AM"),
                    ("BA", "BA"),
                    ("CE", "CE"),
                    ("DF", "DF"),
                    ("ES", "ES"),
                    ("GO", "GO"),
                    ("MA", "MA"),
                    ("MT", "MT"),
                    ("MS", "MS"),
                    ("MG", "MG"),
                    ("PA", "PA"),
                    ("PB", "PB"),
                    ("PR", "PR"),
                    ("PE", "PE"),
                    ("PI", "PI"),
                    ("RJ", "RJ"),
                    ("RN", "RN"),
                    ("RS", "RS"),
                    ("RO", "RO"),
                    ("RR", "RR"),
                    ("SC", "SC"),
                    ("SP", "SP"),
                    ("SE", "SE"),
                    ("TO", "TO"),
                ],
                max_length=2,
            ),
        ),
    ]
