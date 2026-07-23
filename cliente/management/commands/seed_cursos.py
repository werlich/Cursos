from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from cliente.models import Curso, Live
from cliente.services import min_alunos_default


CURSOS = [
    (Curso.Tipo.ARRAIS, "Arrais-Amador", "Preparatório live para exame de Arrais-Amador (NORMAM-211).", 0),
    (Curso.Tipo.MOTONAUTA, "Motonauta", "Preparatório live para exame de Motonauta (NORMAM-212).", 1),
    (Curso.Tipo.MESTRE, "Mestre-Amador", "Preparatório live para exame de Mestre-Amador.", 2),
    (Curso.Tipo.CAPITAO, "Capitão-Amador", "Preparatório live para exame de Capitão-Amador.", 3),
]


def next_seg_qua_sex(from_dt=None, count=6):
    """Gera próximas datas de segunda, quarta e sexta às 19:00."""
    from_dt = from_dt or timezone.localtime()
    d = from_dt.date()
    found = []
    while len(found) < count:
        d = d + timedelta(days=1)
        if d.weekday() in (0, 2, 4):
            found.append(
                timezone.make_aware(
                    timezone.datetime.combine(d, timezone.datetime.strptime("19:00", "%H:%M").time())
                )
                if hasattr(timezone, "datetime")
                else None
            )
    return found


class Command(BaseCommand):
    help = "Cria cursos padrão e próximas lives (seg/qua/sex 19h)"

    def handle(self, *args, **options):
        preco = Decimal("29.90")
        min_alunos = min_alunos_default()
        for tipo, nome, desc, ordem in CURSOS:
            Curso.objects.update_or_create(
                tipo=tipo,
                defaults={
                    "nome": nome,
                    "descricao": desc,
                    "preco": preco,
                    "ativo": True,
                    "ordem": ordem,
                },
            )
            self.stdout.write(f"Curso OK: {nome}")

        # Próximas 6 datas seg/qua/sex
        from datetime import datetime, time

        from django.utils.timezone import make_aware

        hoje = timezone.localdate()
        datas = []
        d = hoje
        while len(datas) < 6:
            d = d + timedelta(days=1)
            if d.weekday() in (0, 2, 4):
                datas.append(make_aware(datetime.combine(d, time(19, 0))))

        cursos = list(Curso.objects.filter(ativo=True).order_by("ordem"))
        criadas = 0
        for i, dt in enumerate(datas):
            curso = cursos[i % len(cursos)]
            titulo = f"Live {curso.nome}"
            obj, created = Live.objects.get_or_create(
                curso=curso,
                data_hora=dt,
                defaults={
                    "titulo": titulo,
                    "status": Live.Status.ABERTA,
                    "min_alunos": min_alunos,
                    "stream_url": "",
                },
            )
            if created:
                criadas += 1
                self.stdout.write(f"Live criada: {obj}")
        self.stdout.write(self.style.SUCCESS(f"Seed concluído. {criadas} live(s) nova(s)."))
