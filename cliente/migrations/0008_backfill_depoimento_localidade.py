from django.db import migrations


def backfill_locais(apps, schema_editor):
    Depoimento = apps.get_model("cliente", "Depoimento")
    defaults = {
        "Ana Paula": ("Florianópolis", "SC"),
        "Ricardo M.": ("Itajaí", "SC"),
        "Fernanda S.": ("Joinville", "SC"),
    }
    for nome, (cidade, estado) in defaults.items():
        Depoimento.objects.filter(nome=nome, cidade="").update(
            cidade=cidade, estado=estado
        )


class Migration(migrations.Migration):

    dependencies = [
        ("cliente", "0007_depoimento_cidade_estado"),
    ]

    operations = [
        migrations.RunPython(backfill_locais, migrations.RunPython.noop),
    ]
