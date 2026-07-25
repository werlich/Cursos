from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cliente", "0009_live_classroom"),
    ]

    operations = [
        migrations.AddField(
            model_name="livepixcampanha",
            name="widget_url",
            field=models.URLField(
                blank=True,
                help_text="Embed LivePix, ex.: https://widget.livepix.gg/embed/…",
            ),
        ),
    ]
