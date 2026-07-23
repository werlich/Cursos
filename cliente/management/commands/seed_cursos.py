from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.timezone import make_aware

from cliente.models import Curso, Live


# tipo, nome, descricao, ordem, preco, min_alunos, ativo
CURSOS = [
    (
        Curso.Tipo.ARRAIS,
        "Arrais-Amador",
        "Preparatório ao vivo para o exame de Arrais-Amador (NORMAM-211).",
        0,
        Decimal("29.90"),
        5,
        True,
    ),
    (
        Curso.Tipo.MOTONAUTA,
        "Motonauta",
        "Preparatório ao vivo para o exame de Motonauta (NORMAM-212).",
        1,
        Decimal("29.90"),
        5,
        True,
    ),
    (
        Curso.Tipo.MESTRE,
        "Mestre-Amador",
        "Preparatório ao vivo para o exame de Mestre-Amador.",
        2,
        Decimal("150.00"),
        2,
        True,
    ),
    (
        Curso.Tipo.CAPITAO,
        "Capitão-Amador",
        "Preparatório live para exame de Capitão-Amador.",
        3,
        Decimal("29.90"),
        10,
        False,
    ),
]


class Command(BaseCommand):
    help = "Sincroniza catálogo de cursos, preços, mínimos e próximas lives"

    def handle(self, *args, **options):
        for tipo, nome, desc, ordem, preco, min_alunos, ativo in CURSOS:
            curso, _ = Curso.objects.update_or_create(
                tipo=tipo,
                defaults={
                    "nome": nome,
                    "descricao": desc,
                    "preco": preco,
                    "min_alunos_padrao": min_alunos,
                    "ativo": ativo,
                    "ordem": ordem,
                },
            )
            # Atualiza lives abertas deste curso
            Live.objects.filter(
                curso=curso,
                status__in=[Live.Status.ABERTA, Live.Status.CONFIRMADA],
            ).update(min_alunos=min_alunos)
            if not ativo:
                Live.objects.filter(
                    curso=curso,
                    status=Live.Status.ABERTA,
                ).update(status=Live.Status.CANCELADA)
            self.stdout.write(f"Curso OK: {nome} (ativo={ativo}, R${preco}, min={min_alunos})")

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
            obj, created = Live.objects.get_or_create(
                curso=curso,
                data_hora=dt,
                defaults={
                    "titulo": f"Live {curso.nome}",
                    "status": Live.Status.ABERTA,
                    "min_alunos": curso.min_alunos_padrao,
                    "stream_url": "",
                },
            )
            if created:
                criadas += 1
                self.stdout.write(f"Live criada: {obj}")
            else:
                if obj.min_alunos != curso.min_alunos_padrao and obj.status == Live.Status.ABERTA:
                    obj.min_alunos = curso.min_alunos_padrao
                    obj.save(update_fields=["min_alunos"])

        self.stdout.write(self.style.SUCCESS(f"Catálogo sincronizado. {criadas} live(s) nova(s)."))
