# Generated manually on 2026-07-25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cliente', '0014_curso_mostrar_aproveite'),
    ]

    operations = [
        migrations.AlterField(
            model_name='curso',
            name='mostrar_aproveite',
            field=models.BooleanField(
                default=False,
                help_text='Exibe o selo “Promocional” acima do preço na página de cursos.',
                verbose_name='Banner Promocional',
            ),
        ),
    ]
